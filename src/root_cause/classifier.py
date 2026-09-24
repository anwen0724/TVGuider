from dataclasses import dataclass
from typing import Any

from .features import DiagnosticFeatures, FeatureExtractorConfig, extract_diagnostic_features
from .scoring import (
    LABEL_S1,
    LABEL_S2,
    LABEL_S3,
    LABEL_S4,
    RootCauseCandidate,
    RootCauseScoringConfig,
    score_all_root_causes,
)
from .validation import validate_setup_tvir


@dataclass
class RootCauseLabels:
    primary: str
    secondary: list[str]


@dataclass
class RootCauseResult:
    root_cause: RootCauseLabels
    candidates: list[RootCauseCandidate]
    diagnostic_features: DiagnosticFeatures

    def to_dict(self) -> dict[str, Any]:
        return {
            "root_cause": {
                "primary": self.root_cause.primary,
                "secondary": list(self.root_cause.secondary),
            },
            "candidates": [
                {"label": c.label, "score": c.score, "reason": c.reason} for c in self.candidates
            ],
            "diagnostic_features": self.diagnostic_features.to_dict(),
        }


class RootCauseClassifierConfig:
    def __init__(
        self,
        feature_cfg: FeatureExtractorConfig | None = None,
        scoring_cfg: RootCauseScoringConfig | None = None,
        primary_threshold: float = 0.5,
        secondary_threshold: float = 0.3,
        max_secondary: int = 2,
        priority_order: list[str] | None = None,
    ):
        self.feature_cfg = feature_cfg or FeatureExtractorConfig()
        self.scoring_cfg = scoring_cfg or RootCauseScoringConfig()
        self.primary_threshold = primary_threshold
        self.secondary_threshold = secondary_threshold
        self.max_secondary = max_secondary
        if priority_order is not None:
            self.priority_order = priority_order
        else:
            self.priority_order = [LABEL_S4, LABEL_S3, LABEL_S1, LABEL_S2]


class RootCauseClassifier:
    def __init__(self, config: RootCauseClassifierConfig | None = None):
        self.config = config or RootCauseClassifierConfig()

    def analyze(self, tvir: dict[str, Any]) -> RootCauseResult:
        validate_setup_tvir(tvir)
        features = extract_diagnostic_features(tvir, config=self.config.feature_cfg)
        candidates = score_all_root_causes(features, cfg=self.config.scoring_cfg)
        root_cause_labels = self._select_root_cause_labels(candidates)
        return RootCauseResult(
            root_cause=root_cause_labels, candidates=candidates, diagnostic_features=features
        )

    def _select_root_cause_labels(self, candidates: list[RootCauseCandidate]) -> RootCauseLabels:
        non_zero = [c for c in candidates if c.score > 0.0]
        if not non_zero:
            return RootCauseLabels(primary="UNKNOWN", secondary=[])
        candidates_sorted = sorted(non_zero, key=lambda c: c.score, reverse=True)
        max_score = candidates_sorted[0].score
        if max_score < self.config.primary_threshold:
            return RootCauseLabels(primary="UNKNOWN", secondary=[])
        primary_label = self._select_primary_with_priority(candidates_sorted)
        secondary_labels: list[str] = []
        if primary_label != "UNKNOWN":
            for c in candidates_sorted:
                if c.label == primary_label:
                    continue
                if c.score < self.config.secondary_threshold:
                    break
                if c.label not in secondary_labels:
                    secondary_labels.append(c.label)
                if len(secondary_labels) >= self.config.max_secondary:
                    break
        return RootCauseLabels(primary=primary_label, secondary=secondary_labels)

    def _select_primary_with_priority(self, candidates_sorted: list[RootCauseCandidate]) -> str:
        if not candidates_sorted:
            return "UNKNOWN"
        max_score = candidates_sorted[0].score
        delta = 0.05
        near_top_labels = {c.label for c in candidates_sorted if max_score - c.score <= delta}
        for label in self.config.priority_order:
            if label in near_top_labels:
                return label
        return candidates_sorted[0].label
