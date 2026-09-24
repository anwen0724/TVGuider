import json
import re
from contextlib import suppress
from dataclasses import asdict, dataclass
from typing import Any

from llm_clients.base import LLMClient
from prompts import build_repair_prompt
from root_cause.validation import validate_setup_tvir

from .contracts import RepairConstraints, RepairOutputError, validate_repair_output
from .knowledge import retrieval_context
from .planner import RepairPlan


@dataclass
class RepairSuggestionResult:
    suggestion: dict[str, Any]
    text: str
    strategies_used: list[str]
    raw_output: str | None = None


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
        validate_setup_tvir(tvir)
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
        raw = (self.llm_client.generate(prompt) or "").strip()
        candidate_strategies = list(repair_plan.selected_strategies or [])
        allowed_ids = {s.id for s in candidate_strategies}
        parsed, parse_err = self._parse_llm_json(raw)
        summary = self._build_summary(tvir=tvir, module2_output=module2_output)
        suggestion: dict[str, Any] = {
            "summary": summary,
            "candidate_strategies": [
                {
                    "id": s.id,
                    "title": s.title,
                    "root_cause_label": s.root_cause_label,
                    "timing_gain": s.timing_gain,
                    "risk_level": s.risk_level,
                    "change_scope": s.change_scope,
                    "description": s.description,
                    "notes": list(s.notes),
                }
                for s in candidate_strategies
            ],
        }
        if parsed is not None:
            validate_repair_output(
                parsed, {hit.chunk.chunk_id for hit in retrieval.results}, constraints
            )
        if parsed is None:
            raise RepairOutputError(f"Invalid model repair JSON: {parse_err}")
        else:
            fields = {
                "chosen_strategies",
                "edit_locations",
                "engineer_advice",
                "code_hint",
                "risks",
                "repaired_rtl",
                "change_summary",
                "knowledge_used",
                "latency_change_cycles",
            }
            suggestion.update({key: value for key, value in parsed.items() if key in fields})
            val_errs = self._validate_and_fix_suggestion(
                suggestion=suggestion,
                tvir=tvir,
                allowed_strategy_ids=allowed_ids,
                allow_custom=self.config.allow_custom_strategy,
            )
            if val_errs:
                suggestion["_validation_error"] = val_errs
        suggestion["validation_status"] = "not_run"
        strategies_used = self._extract_strategies_used(suggestion)
        text_out = self._render_for_humans(suggestion=suggestion, tvir=tvir)
        return RepairSuggestionResult(
            suggestion=suggestion, text=text_out, strategies_used=strategies_used, raw_output=raw
        )

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

    def _validate_and_fix_suggestion(
        self,
        *,
        suggestion: dict[str, Any],
        tvir: dict[str, Any],
        allowed_strategy_ids: set,
        allow_custom: bool,
    ) -> list[str]:
        errs: list[str] = []
        required = ["chosen_strategies", "edit_locations", "engineer_advice", "code_hint", "risks"]
        for k in required:
            if k not in suggestion:
                errs.append(f"missing_field:{k}")
        chosen = suggestion.get("chosen_strategies") or []
        if not isinstance(chosen, list):
            errs.append("chosen_strategies_not_list")
            chosen = []
        fixed_chosen = []
        for item in chosen:
            if not isinstance(item, dict):
                continue
            src = str(item.get("source") or "library").strip().lower()
            sid = item.get("id")
            if src == "library":
                if sid not in allowed_strategy_ids:
                    errs.append(f"library_strategy_not_allowed:{sid}")
                    continue
            elif src == "custom":
                if not allow_custom:
                    errs.append("custom_not_allowed")
                    continue
                if not item.get("title"):
                    errs.append(f"custom_missing_title:{sid}")
                    item["title"] = "CUSTOM_STRATEGY"
            else:
                errs.append(f"bad_source:{src}")
                continue
            fixed_chosen.append(item)
        suggestion["chosen_strategies"] = fixed_chosen
        dflow = tvir.get("dataflow_path") or []
        snippet = tvir.get("rtl_snippet") or []
        locs = suggestion.get("edit_locations") or []
        if not isinstance(locs, list):
            errs.append("edit_locations_not_list")
            locs = []
        fixed_locs = []
        for loc in locs:
            if not isinstance(loc, dict):
                continue
            lt = loc.get("location_type")
            ref = loc.get("ref") or {}
            if lt == "dataflow_node":
                idx = ref.get("index")
                if not isinstance(idx, int) or idx < 0 or idx >= len(dflow):
                    errs.append(f"bad_dataflow_index:{idx}")
                    continue
            elif lt == "rtl_snippet_line_range":
                st, ed = (ref.get("start"), ref.get("end"))
                if not (
                    isinstance(st, int) and isinstance(ed, int) and (0 <= st <= ed < len(snippet))
                ):
                    errs.append(f"bad_snippet_range:{st}-{ed}")
                    continue
            else:
                errs.append(f"bad_location_type:{lt}")
                continue
            fixed_locs.append(loc)
        suggestion["edit_locations"] = fixed_locs
        for k in ["engineer_advice", "risks"]:
            v = suggestion.get(k)
            if isinstance(v, str):
                suggestion[k] = [v]
            elif not isinstance(v, list):
                suggestion[k] = []
        if not suggestion["engineer_advice"]:
            errs.append("empty_engineer_advice")
            suggestion["engineer_advice"] = [
                "优先按候选策略对关键组合路径做局部重构/插入流水线/处理扇出，并回归仿真与复查 STA 报告。"
            ]
        if not suggestion["risks"]:
            errs.append("empty_risks")
            suggestion["risks"] = ["可能引入额外延迟/面积/功耗副作用；需回归仿真并复查时序。"]
        ch = suggestion.get("code_hint")
        if not isinstance(ch, dict):
            suggestion["code_hint"] = {"language": "verilog", "patch_like": []}
        else:
            ch.setdefault("language", "verilog")
            if "patch_like" not in ch or not isinstance(ch["patch_like"], list):
                ch["patch_like"] = []
        return errs

    def _build_summary(
        self, *, tvir: dict[str, Any], module2_output: dict[str, Any]
    ) -> dict[str, Any]:
        ctx = tvir.get("context") or {}
        frc = self._get_final_root_cause(module2_output)
        return {
            "final_primary": frc.get("primary", "UNKNOWN"),
            "final_secondary": frc.get("secondary", []),
            "violation_type": ctx.get("violation_type"),
            "clock": ctx.get("clock") or ctx.get("launch_clock"),
            "period_ns": ctx.get("period_ns"),
            "slack_ns": ctx.get("slack_ns"),
        }

    def _extract_strategies_used(self, suggestion: dict[str, Any]) -> list[str]:
        out: list[str] = []
        for s in suggestion.get("chosen_strategies") or []:
            if isinstance(s, dict) and s.get("id"):
                out.append(str(s["id"]))
        return out

    def _render_for_humans(self, *, suggestion: dict[str, Any], tvir: dict[str, Any]) -> str:
        lines: list[str] = []
        summ = suggestion.get("summary") or {}
        lines.append("== Repair Suggestion ==")
        lines.append(f"- final_primary: {summ.get('final_primary')}")
        if summ.get("final_secondary"):
            lines.append(f"- final_secondary: {summ.get('final_secondary')}")
        lines.append(
            f"- violation_type: {summ.get('violation_type')}, clock: {summ.get('clock')}, period_ns: {summ.get('period_ns')}, slack_ns: {summ.get('slack_ns')}"
        )
        lines.append("\nCandidate strategies (planner Top-K):")
        for s in suggestion.get("candidate_strategies") or []:
            lines.append(
                f"- {s.get('id')} | {s.get('title')} | gain={s.get('timing_gain')} risk={s.get('risk_level')}"
            )
        lines.append("\nChosen strategies (LLM):")
        for item in suggestion.get("chosen_strategies") or []:
            if not isinstance(item, dict):
                continue
            src, sid = (item.get("source"), item.get("id"))
            conf, reason = (item.get("confidence"), item.get("reason"))
            title = item.get("title")
            if src == "custom" and title:
                lines.append(f"- [{src}] {sid} ({title}) | conf={conf} | {reason}")
            else:
                lines.append(f"- [{src}] {sid} | conf={conf} | {reason}")
        if suggestion.get("edit_locations"):
            lines.append("\nEdit locations:")
            for loc in suggestion.get("edit_locations") or []:
                lines.append(
                    f"- {loc.get('location_type')} {loc.get('ref')} : {loc.get('rationale')}"
                )
        lines.append("\nEngineer advice:")
        for i, a in enumerate(suggestion.get("engineer_advice") or [], start=1):
            lines.append(f"{i}. {a}")
        ch = suggestion.get("code_hint") or {}
        patch = ch.get("patch_like") or []
        if patch:
            lines.append("\nCode hint (patch-like):")
            lines.append("```verilog")
            lines.extend([str(x) for x in patch])
            lines.append("```")
        risks = suggestion.get("risks") or []
        if risks:
            lines.append("\nRisks / side effects:")
            for r in risks:
                lines.append(f"- {r}")
        if tvir.get("rtl_snippet"):
            lines.append("\nRTL snippet (for reference):")
            for ln in tvir.get("rtl_snippet") or []:
                lines.append(str(ln))
        return "\n".join(lines)

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
