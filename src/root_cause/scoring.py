from dataclasses import dataclass

from .features import DiagnosticFeatures

LABEL_S1 = "S1_combinational_path_too_long"
LABEL_S2 = "S2_high_fanout"
LABEL_S3 = "S3_complex_arithmetic_no_pipeline"
LABEL_S4 = "S4_cross_hierarchy_path"


@dataclass
class RootCauseCandidate:
    label: str
    score: float
    reason: str


class RootCauseScoringConfig:
    def __init__(
        self,
        s1_delay_ratio_start: float = 0.4,
        s1_delay_ratio_strong: float = 0.8,
        s1_logic_levels_low: int = 4,
        s1_logic_levels_high: int = 10,
        s1_neg_slack_norm_ref: float = 0.25,
        s1_op_count_min: int = 1,
        s2_fanout_warn: int = 16,
        s2_fanout_high: int = 64,
        s3_min_arith_chain_len: int = 2,
        s3_max_arith_chain_len: int = 4,
        s4_hierarchy_depth_max: int = 4,
        s4_module_crossings_max: int = 3,
    ):
        self.s1_delay_ratio_start = s1_delay_ratio_start
        self.s1_delay_ratio_strong = s1_delay_ratio_strong
        self.s1_logic_levels_low = s1_logic_levels_low
        self.s1_logic_levels_high = s1_logic_levels_high
        self.s1_neg_slack_norm_ref = s1_neg_slack_norm_ref
        self.s1_op_count_min = s1_op_count_min
        self.s2_fanout_warn = s2_fanout_warn
        self.s2_fanout_high = s2_fanout_high
        self.s3_min_arith_chain_len = s3_min_arith_chain_len
        self.s3_max_arith_chain_len = s3_max_arith_chain_len
        self.s4_hierarchy_depth_max = s4_hierarchy_depth_max
        self.s4_module_crossings_max = s4_module_crossings_max


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    if x < lo:
        return lo
    if x > hi:
        return hi
    return x


def score_S1(features: DiagnosticFeatures, cfg: RootCauseScoringConfig) -> RootCauseCandidate:
    label = LABEL_S1
    if features.violation_type != "setup":
        return RootCauseCandidate(
            label=label,
            score=0.0,
            reason=f"violation_type={features.violation_type}，当前 S1 只考虑 setup 违规。",
        )
    if features.period_ns is None:
        return RootCauseCandidate(
            label=label, score=0.0, reason="缺少 period_ns 信息，无法判断组合路径相对于周期的长短。"
        )
    if features.op_count < cfg.s1_op_count_min:
        return RootCauseCandidate(
            label=label,
            score=0.0,
            reason=f"op_count={features.op_count} < {cfg.s1_op_count_min}，路径过短，不认为是 S1。",
        )
    ratio = features.data_delay_ratio
    if ratio is not None:
        if ratio <= cfg.s1_delay_ratio_start:
            r1 = 0.0
        elif ratio >= cfg.s1_delay_ratio_strong:
            r1 = 1.0
        else:
            r1 = (ratio - cfg.s1_delay_ratio_start) / (
                cfg.s1_delay_ratio_strong - cfg.s1_delay_ratio_start
            )
    else:
        r1 = 0.5
    if features.logic_levels is not None:
        L = features.logic_levels
        if L <= cfg.s1_logic_levels_low:
            r2 = 0.0
        elif L >= cfg.s1_logic_levels_high:
            r2 = 1.0
        else:
            r2 = (L - cfg.s1_logic_levels_low) / float(
                cfg.s1_logic_levels_high - cfg.s1_logic_levels_low
            )
    else:
        r2 = 0.5
    if features.normalized_slack is not None:
        ns = features.normalized_slack
        if ns >= 0:
            r3 = 0.0
        else:
            r3 = _clamp(-ns / cfg.s1_neg_slack_norm_ref)
    else:
        r3 = 0.5
    score = 0.4 * r1 + 0.3 * r2 + 0.3 * r3
    score = _clamp(score)
    if ratio is not None:
        ratio_part = f"data_delay_ratio={ratio:.2f}，"
    else:
        ratio_part = "data_delay_ratio=None，"
    reason = (
        ratio_part
        + f"logic_levels={features.logic_levels}, "
        + f"normalized_slack={features.normalized_slack}，"
        + "综合判断组合路径相对周期偏长。"
    )
    return RootCauseCandidate(label=label, score=score, reason=reason)


def score_S2(features: DiagnosticFeatures, cfg: RootCauseScoringConfig) -> RootCauseCandidate:
    label = LABEL_S2
    if features.violation_type != "setup":
        return RootCauseCandidate(
            label=label,
            score=0.0,
            reason=f"violation_type={features.violation_type}，当前 S2 只考虑 setup 违规。",
        )
    if features.max_fanout_count is None or features.max_fanout_count <= 0:
        return RootCauseCandidate(
            label=label, score=0.0, reason="缺少 max_fanout_count 或值不大于 0，不认为是 S2。"
        )
    sig = features.max_fanout_signal or ""
    if "clk" in sig.lower():
        return RootCauseCandidate(
            label=label,
            score=0.0,
            reason=f"max_fanout_signal={sig} 看起来是时钟网，不认为是数据高扇出问题。",
        )
    fo = features.max_fanout_count
    if fo <= cfg.s2_fanout_warn:
        score = 0.0
    elif fo >= cfg.s2_fanout_high:
        score = 1.0
    else:
        score = (fo - cfg.s2_fanout_warn) / float(cfg.s2_fanout_high - cfg.s2_fanout_warn)
    score = _clamp(score)
    reason = f"max_fanout_signal={sig}, max_fanout_count={fo}，与阈值区间 [{cfg.s2_fanout_warn}, {cfg.s2_fanout_high}] 对比后评估高扇出风险。"
    return RootCauseCandidate(label=label, score=score, reason=reason)


def score_S3(features: DiagnosticFeatures, cfg: RootCauseScoringConfig) -> RootCauseCandidate:
    label = LABEL_S3
    if features.violation_type != "setup":
        return RootCauseCandidate(
            label=label,
            score=0.0,
            reason=f"violation_type={features.violation_type}，当前 S3 只考虑 setup 违规。",
        )
    if features.arith_op_count <= 0:
        return RootCauseCandidate(
            label=label,
            score=0.0,
            reason=f"arith_op_count={features.arith_op_count}，没有算术运算，不认为是 S3。",
        )
    chain = features.max_arith_chain_len
    if chain <= 1:
        r1 = 0.0
    elif chain >= cfg.s3_max_arith_chain_len:
        r1 = 1.0
    else:
        r1 = (chain - cfg.s3_min_arith_chain_len) / float(
            max(1, cfg.s3_max_arith_chain_len - cfg.s3_min_arith_chain_len)
        )
        r1 = _clamp(r1)
    r2 = 1.0 if features.has_mixed_ops else 0.3
    ratio = features.data_delay_ratio
    if ratio is None:
        ratio = features.path_score_ratio
    if ratio is not None:
        if ratio <= cfg.s1_delay_ratio_start:
            r3 = 0.0
        elif ratio >= cfg.s1_delay_ratio_strong:
            r3 = 1.0
        else:
            r3 = (ratio - cfg.s1_delay_ratio_start) / (
                cfg.s1_delay_ratio_strong - cfg.s1_delay_ratio_start
            )
    else:
        r3 = 0.5
    score = 0.5 * r1 + 0.3 * r2 + 0.2 * r3
    score = _clamp(score)
    reason = f"arith_op_count={features.arith_op_count}, max_arith_chain_len={chain}, has_mixed_ops={features.has_mixed_ops}, ratio={ratio}，说明同一拍内存在较复杂的算术/位运算链，且整体路径较重。"
    return RootCauseCandidate(label=label, score=score, reason=reason)


def score_S4(features: DiagnosticFeatures, cfg: RootCauseScoringConfig) -> RootCauseCandidate:
    label = LABEL_S4
    depth = features.hierarchy_depth
    mc = features.module_crossings
    if depth is None or depth <= 0:
        return RootCauseCandidate(
            label=label, score=0.0, reason=f"hierarchy_depth={depth}，未跨层次，不认为是 S4。"
        )
    if cfg.s4_hierarchy_depth_max > 0:
        r1 = _clamp(depth / float(cfg.s4_hierarchy_depth_max))
    else:
        r1 = 1.0
    if cfg.s4_module_crossings_max > 0:
        r2 = _clamp(mc / float(cfg.s4_module_crossings_max))
    else:
        r2 = 1.0
    score = 0.7 * r1 + 0.3 * r2
    score = _clamp(score)
    reason = f"start_hierarchy={features.start_hierarchy}, end_hierarchy={features.end_hierarchy}, hierarchy_depth={depth}, module_crossings={mc}，表明该路径跨越了多个层次/模块。"
    return RootCauseCandidate(label=label, score=score, reason=reason)


def score_all_root_causes(
    features: DiagnosticFeatures, cfg: RootCauseScoringConfig | None = None
) -> list[RootCauseCandidate]:
    if cfg is None:
        cfg = RootCauseScoringConfig()
    candidates: list[RootCauseCandidate] = []
    candidates.append(score_S4(features, cfg))
    candidates.append(score_S1(features, cfg))
    candidates.append(score_S3(features, cfg))
    candidates.append(score_S2(features, cfg))
    return candidates
