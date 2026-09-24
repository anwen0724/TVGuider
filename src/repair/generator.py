import json
import re
from contextlib import suppress
from dataclasses import asdict, dataclass
from typing import Any

from llm_clients.base import LLMClient
from prompts import build_repair_prompt
from root_cause.validation import validate_tvir

from .contracts import RepairConstraints
from .knowledge import retrieval_context
from .planner import RepairPlan


@dataclass
class RepairSuggestionResult:
    suggestion: dict[str, Any]
    text: str
    strategies_used: list[str]
    raw_output: str | None = None
    parse_status: str = "parsed"
    parse_error: str | None = None
    validation_status: str = "not_run"
    repaired_rtl: str | None = None


@dataclass
class RepairSuggestionConfig:
    language: str = "en"
    allow_custom_strategy: bool = True
    enforce_json_output: bool = True
    candidates_topk_in_prompt: int = 3


class RepairSuggestionGenerator:
    def __init__(self, llm_client: LLMClient, config: RepairSuggestionConfig | None = None):
        self.llm_client = llm_client
        self.config = config or RepairSuggestionConfig()

    def generate(
        self,
        *,
        tvir: dict[str, Any],
        module2_output: dict[str, Any],
        repair_plan: RepairPlan,
        original_rtl: str,
        retrieval,
        constraints=None,
    ) -> RepairSuggestionResult:
        validate_tvir(tvir)
        if not isinstance(original_rtl, str) or not original_rtl.strip():
            raise ValueError("Original RTL must be nonempty")
        constraints = constraints or RepairConstraints()
        llm_context = self._build_llm_context_for_repair(
            tvir=tvir, module2_output=module2_output, repair_plan=repair_plan
        )
        llm_context["original_rtl"] = original_rtl
        llm_context["knowledge"] = retrieval_context(retrieval)
        llm_context["constraints"] = asdict(constraints)
        prompt = build_repair_prompt(
            llm_context,
            language=self.config.language,
            allow_custom_strategy=self.config.allow_custom_strategy,
        )
        raw = self.llm_client.generate(prompt) or ""
        parsed, parse_err = self._parse_llm_json(raw)
        suggestion = parsed if parsed is not None else {}
        chosen = suggestion.get("chosen_strategies")
        strategies = (
            [str(item["id"]) for item in chosen if isinstance(item, dict) and item.get("id")]
            if isinstance(chosen, list)
            else []
        )
        return RepairSuggestionResult(
            suggestion=suggestion,
            text=raw,
            strategies_used=strategies,
            raw_output=raw,
            parse_status="parsed" if parsed is not None else "failed",
            parse_error=parse_err or None,
            repaired_rtl=self._extract_rtl(suggestion, raw),
        )

    def _extract_rtl(self, suggestion, raw):
        rtl = suggestion.get("repaired_rtl")
        if isinstance(rtl, str) and rtl.strip():
            fenced = re.fullmatch(
                r"\s*```(?:verilog|systemverilog|sv)?\s*\n(.*?)\n```\s*",
                rtl,
                re.DOTALL | re.IGNORECASE,
            )
            return fenced.group(1) if fenced else rtl
        blocks = re.findall(
            r"```(?:verilog|systemverilog|sv)\s*\n(.*?)\n```", raw, re.DOTALL | re.IGNORECASE
        )
        if blocks:
            return "\n".join(blocks)
        if re.match(r"\s*(?:module\s|`timescale\b|`include\b|`default_nettype\b)", raw):
            return raw
        return None

    def _build_llm_context_for_repair(
        self, *, tvir: dict[str, Any], module2_output: dict[str, Any], repair_plan: RepairPlan
    ) -> dict[str, Any]:
        tvir_compact = self._compact_tvir_for_llm(tvir)
        final_root = self._get_final_root_cause(module2_output)
        explanation_text = self._get_module2_explanation_text(module2_output)
        topk = max(int(self.config.candidates_topk_in_prompt), 1)
        strategies_payload: list[dict[str, Any]] = []
        for s in list(repair_plan.selected_strategies or [])[:topk]:
            strategies_payload.append(
                {
                    "id": s.id,
                    "root_cause_label": s.root_cause_label,
                    "title": s.title,
                    "description": s.description,
                    "preconditions": list(s.preconditions),
                    "timing_gain": s.timing_gain,
                    "risk_level": s.risk_level,
                    "change_scope": s.change_scope,
                    "notes": list(s.notes),
                }
            )
        dataflow_description = self._build_dataflow_description(
            tvir_compact.get("dataflow_path", []) or []
        )
        rtl_lines = tvir_compact.get("rtl_snippet") or []
        rtl_snippet_text = self._build_rtl_snippet_text(rtl_lines)
        extra_evidence = {
            "path_metrics": tvir_compact.get("path_metrics") or {},
            "fanout_info": tvir_compact.get("fanout_info") or {},
            "hierarchy_info": tvir_compact.get("hierarchy_info") or {},
        }
        return {
            "final_root_cause": final_root,
            "root_cause_explanation": {
                "text": explanation_text or "",
                "note": "Narrative reference from Module2. Prefer structured evidence; do NOT invent unseen facts from this text.",
            },
            "tvir": {
                "context": tvir_compact.get("context") or {},
                "dataflow_description": dataflow_description,
                "rtl_snippet_text": rtl_snippet_text,
                "rtl_snippet_lines": rtl_lines,
                "extra_evidence": extra_evidence,
            },
            "candidate_set": {
                "primary_root_cause": repair_plan.primary_root_cause,
                "candidate_strategies": strategies_payload,
            },
        }

    def _compact_tvir_for_llm(self, tvir: dict[str, Any]) -> dict[str, Any]:
        keep_keys = {
            "context",
            "dataflow_path",
            "rtl_snippet",
            "path_metrics",
            "fanout_info",
            "hierarchy_info",
        }
        out: dict[str, Any] = {k: tvir.get(k) for k in keep_keys if k in tvir}
        return out

    def _get_final_root_cause(self, module2_output: dict[str, Any]) -> dict[str, Any]:
        frc = module2_output.get("final_root_cause")
        if isinstance(frc, dict):
            p = frc.get("primary") or "UNKNOWN"
            s = frc.get("secondary") or []
            if not isinstance(s, list):
                s = []
            return {"primary": str(p), "secondary": [str(x) for x in s]}
        return {"primary": "UNKNOWN", "secondary": []}

    def _get_module2_explanation_text(self, module2_output: dict[str, Any]) -> str:
        exp = module2_output.get("explanation")
        if isinstance(exp, dict):
            t = exp.get("text")
            return str(t).strip() if t else ""
        if isinstance(exp, str):
            return exp.strip()
        return ""

    def _parse_llm_json(self, raw: str) -> tuple[dict[str, Any] | None, str]:
        if not raw:
            return (None, "empty_output")
        with suppress(json.JSONDecodeError):
            obj = json.loads(raw)
            if isinstance(obj, dict):
                return (obj, "")
        extracted = self._extract_first_json_object(raw)
        if extracted is None:
            return (None, "json_not_found")
        try:
            obj = json.loads(extracted)
            if isinstance(obj, dict):
                return (obj, "")
            return (None, "json_root_not_object")
        except json.JSONDecodeError as e:
            return (None, f"json_parse_error:{type(e).__name__}")

    def _extract_first_json_object(self, s: str) -> str | None:
        m = re.search("```(?:json)?\\s*(\\{.*?\\})\\s*```", s, flags=re.DOTALL | re.IGNORECASE)
        if m:
            return m.group(1).strip()
        start = s.find("{")
        if start < 0:
            return None
        decoder = json.JSONDecoder()
        try:
            obj, _ = decoder.raw_decode(s[start:])
            return json.dumps(obj, ensure_ascii=False)
        except json.JSONDecodeError:
            depth = 0
            for i in range(start, len(s)):
                if s[i] == "{":
                    depth += 1
                elif s[i] == "}":
                    depth -= 1
                    if depth == 0:
                        return s[start : i + 1].strip()
            return None

    def _build_dataflow_description(self, dataflow_path: list[dict[str, Any]]) -> str:
        parts: list[str] = []
        for idx, node in enumerate(dataflow_path):
            if not isinstance(node, dict):
                continue
            role = node.get("role")
            if role in ("start_reg", "end_reg"):
                name = node.get("name", "UNKNOWN_REG")
                module = node.get("module")
                parts.append(f"[{idx}] {role}: {name}" + (f" (module={module})" if module else ""))
            elif role == "op":
                op_type = node.get("op_type", "UNKNOWN_OP")
                module = node.get("module")
                parts.append(f"[{idx}] op: {op_type}" + (f" (module={module})" if module else ""))
            else:
                parts.append(f"[{idx}] {role}: {node}")
        return "\n".join(parts)

    def _build_rtl_snippet_text(self, rtl_snippet_lines: list[str] | None) -> str:
        if not rtl_snippet_lines:
            return ""
        return "\n".join([str(x) for x in rtl_snippet_lines])
