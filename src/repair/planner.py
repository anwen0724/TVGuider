import math
from dataclasses import dataclass
from typing import Any

from root_cause.classifier import RootCauseResult
from root_cause.features import extract_diagnostic_features

from .strategies import CAUSE_TO_STRATEGIES, STRATEGY_LIBRARY, RepairStrategy


@dataclass
class RepairPlan:
    primary_root_cause: str
    candidate_strategies: list[RepairStrategy]

    @property
    def selected_strategies(self) -> list[RepairStrategy]:
        return self.candidate_strategies


@dataclass
class RepairPlannerConfig:
    max_strategies: int = 3
    prefer_local_changes: bool = True


class RepairPlanner:
    def __init__(self, config: RepairPlannerConfig | None = None):
        self.config = config or RepairPlannerConfig()

    def _f(self, obj: Any, name: str, default=None):
        if obj is None:
            return default
        if isinstance(obj, dict):
            return obj.get(name, default)
        return getattr(obj, name, default)

    def _to_float(self, x, default: float = 0.0) -> float:
        try:
            if x is None:
                return default
            return float(x)
        except (TypeError, ValueError, OverflowError):
            return default

    def _to_int(self, x, default: int = 0) -> int:
        try:
            if x is None:
                return default
            return int(x)
        except (TypeError, ValueError, OverflowError):
            return default

    def _extract_final_labels(self, module2_output: Any) -> tuple[str, list[str]]:
        if hasattr(module2_output, "to_dict"):
            module2_output = module2_output.to_dict()
        if isinstance(module2_output, dict):
            if "final_root_cause" in module2_output and isinstance(
                module2_output["final_root_cause"], dict
            ):
                frc = module2_output["final_root_cause"]
                p = str(frc.get("primary") or "UNKNOWN")
                s = frc.get("secondary") or []
                if not isinstance(s, list):
                    s = []
                return (p, [str(x) for x in s])
            for k in ("llm_output", "module2_output", "result", "output"):
                inner = module2_output.get(k)
                if isinstance(inner, dict) and "final_root_cause" in inner:
                    frc = inner.get("final_root_cause") or {}
                    if isinstance(frc, dict):
                        p = str(frc.get("primary") or "UNKNOWN")
                        s = frc.get("secondary") or []
                        if not isinstance(s, list):
                            s = []
                        return (p, [str(x) for x in s])
        return ("UNKNOWN", [])

    def _extract_features_from_tvir(self, tvir: dict[str, Any]) -> dict[str, Any]:
        return extract_diagnostic_features(tvir).to_dict()

    def _is_clock_like_net(self, sig: str) -> bool:
        if not sig:
            return False
        s = sig.lower()
        return any(k in s for k in ["clk", "clock", "bufg", "ibuf", "mmcm", "pll"])

    def _preconditions_ok(self, strategy: RepairStrategy, features: Any) -> bool:
        pres = strategy.preconditions or []
        if "has_high_fanout_signal" in pres:
            fo = self._to_int(self._f(features, "max_fanout_count", 0), 0)
            if fo < 16:
                return False
        if "not_clock_or_global_net" in pres:
            sig = str(self._f(features, "max_fanout_signal", "") or "")
            if self._is_clock_like_net(sig):
                return False
        if "has_heavy_arithmetic_ops" in pres:
            arith_cnt = self._to_int(self._f(features, "arith_op_count", 0), 0)
            if arith_cnt <= 0:
                return False
        return True

    def plan(
        self,
        module2_llm_output: Any,
        *,
        rule_features: Any | None = None,
        tvir: dict[str, Any] | None = None,
        rule_result: RootCauseResult | None = None,
    ) -> RepairPlan:
        primary_label, secondary_labels = self._extract_final_labels(module2_llm_output)
        if rule_features is not None:
            features = rule_features
        elif (
            rule_result is not None
            and self._f(rule_result, "diagnostic_features", None) is not None
        ):
            features = rule_result.diagnostic_features
        elif tvir is not None:
            features = self._extract_features_from_tvir(tvir)
        else:
            features = {}
        scored: list[tuple[RepairStrategy, float]] = []

        def collect_for_label(label: str, base_weight: float) -> None:
            strategy_ids = CAUSE_TO_STRATEGIES.get(label, []) or []
            for sid in strategy_ids:
                st = STRATEGY_LIBRARY.get(sid)
                if not st:
                    continue
                sc = self._score_strategy(st, label, base_weight, features)
                scored.append((st, sc))

        if primary_label and primary_label != "UNKNOWN":
            collect_for_label(primary_label, base_weight=1.0)
        for lbl in secondary_labels:
            if lbl and lbl != "UNKNOWN":
                collect_for_label(lbl, base_weight=0.7)
        if not scored:
            return RepairPlan(
                primary_root_cause=primary_label or "UNKNOWN", candidate_strategies=[]
            )
        best_scores: dict[str, float] = {}
        for st, sc in scored:
            prev = best_scores.get(st.id, float("-inf"))
            if sc > prev:
                best_scores[st.id] = sc
        sorted_ids = sorted(best_scores.keys(), key=lambda sid: best_scores[sid], reverse=True)
        filtered_ids = [sid for sid in sorted_ids if best_scores[sid] > -100000000.0]
        top_k = max(self.config.max_strategies, 1)
        top_ids = filtered_ids[:top_k]
        candidates: list[RepairStrategy] = [STRATEGY_LIBRARY[sid] for sid in top_ids]
        return RepairPlan(
            primary_root_cause=primary_label or "UNKNOWN", candidate_strategies=candidates
        )

    def _score_strategy(
        self, strategy: RepairStrategy, root_cause_label: str, base_weight: float, features: Any
    ) -> float:
        if not self._preconditions_ok(strategy, features):
            return -1000000000.0
        score = 0.0
        score += 1.0 * base_weight
        gain_map = {"high": 1.0, "medium": 0.7, "low": 0.4}
        gain = gain_map.get((strategy.timing_gain or "medium").lower(), 0.5)
        score += 0.8 * gain
        risk_map = {"low": 0.2, "medium": 0.6, "high": 1.0}
        risk = risk_map.get((strategy.risk_level or "medium").lower(), 0.6)
        score -= 0.5 * risk
        if self.config.prefer_local_changes:
            if strategy.change_scope in ("local_expr", "local", "single_module"):
                score += 0.2
            elif strategy.change_scope in ("cross_module", "protocol_level"):
                score -= 0.2
        period = self._to_float(self._f(features, "period_ns", None), 0.0)
        slack = self._to_float(self._f(features, "slack_ns", None), 0.0)
        path_ratio = self._to_float(self._f(features, "path_score_ratio", None), 0.0)
        slack_ratio = slack / period if period > 0 else 0.0
        if slack_ratio < -0.2 or path_ratio > 1.2:
            if (strategy.timing_gain or "").lower() == "high":
                score += 0.4
        elif (slack_ratio > -0.05 and path_ratio < 1.0) and (
            strategy.risk_level or ""
        ).lower() == "low":
            score += 0.3
        hier_depth = self._to_int(self._f(features, "hierarchy_depth", None), 0)
        mod_cross = self._to_int(self._f(features, "module_crossings", None), 0)
        if (hier_depth > 0 or mod_cross > 0) and strategy.change_scope in (
            "cross_module",
            "boundary",
        ):
            score += 0.3
        if root_cause_label == "S2_high_fanout":
            fo = self._to_int(self._f(features, "max_fanout_count", 0), 0)
            sig = str(self._f(features, "max_fanout_signal", "") or "")
            if fo >= 64:
                score += 0.5
            elif fo >= 16:
                score += 0.3
            if self._is_clock_like_net(sig):
                score -= 1.0
        if math.isnan(score):
            return -1000000000.0
        return score
