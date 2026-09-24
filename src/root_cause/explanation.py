import json
from contextlib import suppress
from dataclasses import dataclass
from typing import Any

from llm_clients.base import LLMClient
from prompts import build_root_cause_prompt

from .classifier import RootCauseLabels, RootCauseResult
from .validation import validate_tvir


@dataclass
class RootCauseExplanation:
    text: str

    def to_dict(self) -> dict[str, Any]:
        return {"text": self.text}


@dataclass
class SelectionRationale:
    decision: str
    reasons: list[str]
    disagreement_with_rule: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "reasons": list(self.reasons),
            "disagreement_with_rule": list(self.disagreement_with_rule),
        }


@dataclass
class RootCauseLLMOutput:
    final_root_cause: RootCauseLabels
    explanation: RootCauseExplanation
    selection_rationale: SelectionRationale
    parse_status: str = "parsed"
    parse_error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "final_root_cause": {
                "primary": self.final_root_cause.primary,
                "secondary": list(self.final_root_cause.secondary),
            },
            "explanation": self.explanation.to_dict(),
            "selection_rationale": self.selection_rationale.to_dict(),
            "parse_status": self.parse_status,
            "parse_error": self.parse_error,
        }


@dataclass
class RootCauseExplainerConfig:
    language: str = "en"
    max_rtl_lines: int = 40
    candidates_topk: int = 3


class RootCauseExplainer:
    ALLOWED_LABELS = (
        "S1_combinational_path_too_long",
        "S2_high_fanout",
        "S3_complex_arithmetic_no_pipeline",
        "S4_cross_hierarchy_path",
        "UNKNOWN",
    )

    def __init__(self, llm_client: LLMClient, config: RootCauseExplainerConfig | None = None):
        self.llm_client = llm_client
        self.config = config or RootCauseExplainerConfig()

    def explain_and_adjust(
        self, tvir: dict[str, Any], rule_result: RootCauseResult
    ) -> RootCauseLLMOutput:
        validate_tvir(tvir)
        rule_primary = str(rule_result.root_cause.primary)
        rule_secondary = [str(x) for x in rule_result.root_cause.secondary]
        llm_context = self._build_llm_context(tvir, rule_result)
        prompt = build_root_cause_prompt(llm_context, language=self.config.language)
        raw = self.llm_client.generate(prompt)
        data = self._parse_llm_json(raw)
        unknown_selected = False
        if data is None:
            final_labels = RootCauseLabels(primary=rule_primary, secondary=rule_secondary)
            explanation = RootCauseExplanation(
                text="The LLM response could not be parsed as valid JSON, so the original rule-based root-cause labels are kept."
                if not (self.config.language or "en").lower().startswith("zh")
                else "LLM 返回结果无法解析为合法 JSON，因此保留规则层的根因标签。"
            )
            rationale = SelectionRationale(
                decision="kept_rule",
                reasons=[
                    "LLM output JSON parse failed; fallback to rule-based labels."
                    if not (self.config.language or "en").lower().startswith("zh")
                    else "LLM 输出 JSON 解析失败，回退到规则层标签。"
                ],
                disagreement_with_rule=[],
            )
            return RootCauseLLMOutput(
                final_root_cause=final_labels,
                explanation=explanation,
                selection_rationale=rationale,
                parse_status="failed",
                parse_error="invalid_json_object",
            )
        final_rc = data.get("final_root_cause") or {}
        if not isinstance(final_rc, dict):
            final_rc = {}
        final_primary = final_rc.get("primary") or data.get("final_primary") or rule_primary
        final_secondary = final_rc.get("secondary") or data.get("final_secondary") or rule_secondary
        if not isinstance(final_secondary, list):
            final_secondary = list(rule_secondary)
        final_secondary = [str(x) for x in final_secondary]
        if len(final_secondary) > 2:
            final_secondary = final_secondary[:2]
        final_primary = str(final_primary)
        if final_primary not in self.ALLOWED_LABELS:
            final_primary = rule_primary
        final_secondary = [
            x for x in final_secondary if x in self.ALLOWED_LABELS and x != final_primary
        ]
        unknown_selected = final_primary == "UNKNOWN"
        if unknown_selected:
            final_primary = rule_primary
            final_secondary = list(rule_secondary)
        exp_obj = data.get("explanation") or {}
        explanation_text = ""
        if isinstance(exp_obj, dict):
            explanation_text = exp_obj.get("text") or ""
        elif isinstance(exp_obj, str):
            explanation_text = exp_obj
        else:
            explanation_text = data.get("explanation_text") or ""
        explanation_text = str(explanation_text).strip()
        rat_obj = data.get("selection_rationale") or {}
        reasons: list[str] = []
        disagreement: list[str] = []
        if isinstance(rat_obj, dict):
            r = rat_obj.get("reasons")
            d = rat_obj.get("disagreement_with_rule")
            if isinstance(r, list):
                reasons = [str(x) for x in r if str(x).strip()]
            if isinstance(d, list):
                disagreement = [str(x) for x in d if str(x).strip()]
        if unknown_selected:
            disagreement = []
            if not reasons:
                reasons = []
            reasons.insert(
                0,
                "LLM returned UNKNOWN; fallback to rule-based labels for downstream modules."
                if not (self.config.language or "en").lower().startswith("zh")
                else "LLM 选择 UNKNOWN，因此回退到规则层标签以保证后续模块可继续执行。",
            )
            if not explanation_text:
                explanation_text = (
                    "The LLM could not confidently adjust the labels; we keep the rule-based labels and explain accordingly."
                    if not (self.config.language or "en").lower().startswith("zh")
                    else "LLM 无法确信纠偏，因此沿用规则层标签并据此给出违例原因解释。"
                )
        if unknown_selected:
            decision = "kept_rule"
        else:
            rule_sec_set = set(rule_secondary)
            final_sec_set = set(final_secondary)
            decision = (
                "kept_rule"
                if final_primary == rule_primary and final_sec_set == rule_sec_set
                else "adjusted"
            )
        if not reasons:
            if decision == "kept_rule":
                reasons = [
                    "Final labels are consistent with the rule-based prior and the provided evidence/features."
                    if not (self.config.language or "en").lower().startswith("zh")
                    else "最终标签与规则层先验及证据/特征一致，因此沿用规则层判断。"
                ]
            else:
                reasons = [
                    "Final labels differ from the rule-based prior; the choice is based on evidence/features in llm_context."
                    if not (self.config.language or "en").lower().startswith("zh")
                    else "最终标签与规则层不一致；根据 llm_context 中的证据/特征进行了纠偏选择。"
                ]
        final_labels = RootCauseLabels(primary=final_primary, secondary=final_secondary)
        return RootCauseLLMOutput(
            final_root_cause=final_labels,
            explanation=RootCauseExplanation(text=explanation_text),
            selection_rationale=SelectionRationale(
                decision=decision, reasons=reasons, disagreement_with_rule=disagreement
            ),
        )

    def _build_llm_context(
        self, tvir: dict[str, Any], rule_result: RootCauseResult
    ) -> dict[str, Any]:
        ctx = tvir.get("context", {}) or {}
        feats = rule_result.diagnostic_features
        violation = {
            "violation_type": feats.violation_type or ctx.get("violation_type"),
            "clock": ctx.get("clock"),
            "period_ns": feats.period_ns or ctx.get("period_ns"),
            "slack_ns": feats.slack_ns or ctx.get("slack_ns"),
            "normalized_slack": getattr(feats, "normalized_slack", None),
            "launch_clock": feats.launch_clock or ctx.get("launch_clock"),
            "capture_clock": feats.capture_clock or ctx.get("capture_clock"),
            "required_time_ns": ctx.get("required_time_ns"),
            "arrival_time_ns": ctx.get("arrival_time_ns"),
        }
        dataflow_path = tvir.get("dataflow_path", []) or []
        path_evidence = {
            "dataflow_path": dataflow_path,
            "dataflow_description": self._build_dataflow_description(dataflow_path),
            "rtl_snippet_text": self._build_rtl_snippet_text(tvir.get("rtl_snippet")),
        }
        tvir_features = {
            "path_metrics": tvir.get("path_metrics") or {},
            "fanout_info": tvir.get("fanout_info") or {},
            "hierarchy_info": tvir.get("hierarchy_info") or {},
        }
        candidates = list(rule_result.candidates or [])
        candidates_sorted = sorted(
            candidates, key=lambda c: float(getattr(c, "score", 0.0)), reverse=True
        )
        topk = max(int(self.config.candidates_topk), 0)
        candidates_topk = [
            {"label": str(c.label), "score": float(c.score)}
            for c in (candidates_sorted[:topk] if topk > 0 else [])
        ]
        rule_prior = {
            "rule_primary": str(rule_result.root_cause.primary),
            "rule_secondary": [str(x) for x in rule_result.root_cause.secondary],
            "candidates_topk": candidates_topk,
            "diagnostic_features": feats.to_dict(),
        }
        return {
            "task": {"allowed_labels": list(self.ALLOWED_LABELS), "output_format": "STRICT_JSON"},
            "violation": violation,
            "path_evidence": path_evidence,
            "tvir_features": tvir_features,
            "rule_prior": rule_prior,
        }

    def _build_dataflow_description(self, dataflow_path: Any) -> str:
        if not isinstance(dataflow_path, list):
            return ""
        parts: list[str] = []
        for node in dataflow_path:
            if not isinstance(node, dict):
                continue
            role = node.get("role")
            if role == "op":
                op_type = str(node.get("op_type", "op"))
                parts.append(f"[{op_type}]")
            else:
                name = node.get("name")
                if name:
                    parts.append(str(name))
        parts = [p for p in parts if p]
        return " -> ".join(parts)

    def _build_rtl_snippet_text(self, rtl_snippet: Any) -> str:
        lines: list[str] = []
        if isinstance(rtl_snippet, str):
            lines = rtl_snippet.splitlines()
        elif isinstance(rtl_snippet, list):
            for item in rtl_snippet:
                if isinstance(item, str):
                    lines.append(item)
                elif isinstance(item, dict):
                    code = item.get("code") or item.get("text")
                    if code:
                        lines.extend(str(code).splitlines())
                    else:
                        lines.append(str(item))
                else:
                    lines.append(str(item))
        elif rtl_snippet is None:
            lines = []
        else:
            lines = str(rtl_snippet).splitlines()
        max_lines = max(int(self.config.max_rtl_lines), 1)
        if len(lines) > max_lines:
            lines = lines[:max_lines] + ["... (truncated)"]
        return "\n".join(lines)

    def _parse_llm_json(self, raw: str) -> dict[str, Any] | None:
        if not raw:
            return None
        text = raw.strip()
        with suppress(json.JSONDecodeError):
            return _json_object(text)
        if "```" in text:
            text2 = text.replace("```json", "").replace("```", "").strip()
            with suppress(json.JSONDecodeError):
                return _json_object(text2)
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and (end > start):
            candidate = text[start : end + 1]
            try:
                return _json_object(candidate)
            except json.JSONDecodeError:
                return None
        return None


def _json_object(text):
    value = json.loads(text)
    return value if isinstance(value, dict) else None
