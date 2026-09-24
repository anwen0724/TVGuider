from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class DiagnosticFeatures:
    violation_type: str | None = None
    period_ns: float | None = None
    slack_ns: float | None = None
    required_time_ns: float | None = None
    arrival_time_ns: float | None = None
    launch_clock: str | None = None
    capture_clock: str | None = None
    logic_levels: int | None = None
    combinational_delay_ns: float | None = None
    net_delay_ns: float | None = None
    data_delay_ratio: float | None = None
    op_count: int = 0
    op_types: list[str] = field(default_factory=list)
    arith_op_count: int = 0
    logic_op_count: int = 0
    shift_op_count: int = 0
    mux_op_count: int = 0
    has_mul: bool = False
    has_div: bool = False
    has_mux: bool = False
    has_logic: bool = False
    has_shift: bool = False
    max_arith_chain_len: int = 0
    has_mixed_ops: bool = False
    start_hierarchy: str | None = None
    end_hierarchy: str | None = None
    hierarchy_depth: int | None = None
    module_crossings: int = 0
    max_fanout_signal: str | None = None
    max_fanout_count: int | None = None
    path_score: float = 0.0
    allowed_score: float | None = None
    path_score_ratio: float | None = None
    normalized_slack: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class FeatureExtractorConfig:
    def __init__(self, alpha: float = 1.0, op_type_weights: dict[str, float] | None = None):
        self.alpha = alpha
        default_weights = {
            "mul": 4.0,
            "mult": 4.0,
            "div": 4.0,
            "add": 2.0,
            "shift": 2.0,
            "logic": 1.5,
            "mux": 1.5,
        }
        if op_type_weights is None:
            self.op_type_weights = default_weights
        else:
            self.op_type_weights = {**default_weights, **op_type_weights}


def extract_diagnostic_features(
    tvir: dict[str, Any], config: FeatureExtractorConfig | None = None
) -> DiagnosticFeatures:
    if config is None:
        config = FeatureExtractorConfig()
    features = DiagnosticFeatures()
    context = tvir.get("context", {}) or {}
    features.violation_type = context.get("violation_type")
    features.period_ns = context.get("period_ns")
    features.slack_ns = context.get("slack_ns")
    features.required_time_ns = context.get("required_time_ns")
    features.arrival_time_ns = context.get("arrival_time_ns")
    features.launch_clock = context.get("launch_clock")
    features.capture_clock = context.get("capture_clock")
    path_metrics = tvir.get("path_metrics", {}) or {}
    features.logic_levels = path_metrics.get("logic_levels")
    features.combinational_delay_ns = path_metrics.get("combinational_delay_ns")
    features.net_delay_ns = path_metrics.get("net_delay_ns")
    if (
        features.period_ns
        and features.combinational_delay_ns is not None
        and (features.net_delay_ns is not None)
    ):
        try:
            total_delay = float(features.combinational_delay_ns) + float(features.net_delay_ns)
            features.data_delay_ratio = total_delay / float(features.period_ns)
        except (TypeError, ValueError, ZeroDivisionError):
            features.data_delay_ratio = None
    else:
        features.data_delay_ratio = None
    dataflow_path = tvir.get("dataflow_path", []) or []
    op_types: list[str] = []
    modules: list[str] = []
    for node in dataflow_path:
        if not isinstance(node, dict):
            continue
        role = node.get("role")
        if role == "op":
            op_type = node.get("op_type")
            if op_type:
                op_types.append(op_type)
        mod = node.get("module")
        if mod:
            modules.append(mod)
    features.op_types = op_types
    features.op_count = len(op_types)
    lower_ops = [op.lower() for op in op_types]
    arith_keywords = {"add", "sub", "mul", "mult", "multiply", "div", "divide"}
    shift_keywords = {"shift", "shl", "shr"}
    mux_keywords = {"mux", "select", "sel", "case"}
    logic_keywords = {"and", "or", "xor", "xnor", "nand", "nor"}
    for op in lower_ops:
        if op in arith_keywords:
            features.arith_op_count += 1
        if op in mux_keywords:
            features.mux_op_count += 1
        if op in logic_keywords or "logic" in op:
            features.logic_op_count += 1
        if "shift" in op or op in shift_keywords:
            features.shift_op_count += 1
    features.has_mul = any(op in ("mul", "mult", "multiply") for op in lower_ops)
    features.has_div = any(op in ("div", "divide") for op in lower_ops)
    features.has_mux = features.mux_op_count > 0
    features.has_logic = features.logic_op_count > 0
    features.has_shift = features.shift_op_count > 0
    max_chain = 0
    cur_chain = 0
    for op in lower_ops:
        if op in arith_keywords:
            cur_chain += 1
            max_chain = max(max_chain, cur_chain)
        else:
            cur_chain = 0
    features.max_arith_chain_len = max_chain
    features.has_mixed_ops = features.arith_op_count > 0 and (
        features.logic_op_count > 0 or features.shift_op_count > 0 or features.mux_op_count > 0
    )
    unique_mods: list[str] = []
    for m in modules:
        if m not in unique_mods:
            unique_mods.append(m)
    if unique_mods:
        features.module_crossings = max(0, len(unique_mods) - 1)
    else:
        features.module_crossings = 0
    hierarchy_info = tvir.get("hierarchy_info", {}) or {}
    features.start_hierarchy = hierarchy_info.get("start_hierarchy")
    features.end_hierarchy = hierarchy_info.get("end_hierarchy")
    features.hierarchy_depth = hierarchy_info.get("hierarchy_depth")
    fanout_info = tvir.get("fanout_info", {}) or {}
    features.max_fanout_signal = fanout_info.get("max_fanout_signal")
    features.max_fanout_count = fanout_info.get("max_fanout_count")
    path_score = 0.0
    for op in lower_ops:
        if op in ("mul", "mult", "multiply"):
            weight_key = "mul"
        elif op in ("div", "divide"):
            weight_key = "div"
        elif op in ("add", "sub"):
            weight_key = "add"
        elif "shift" in op or op in shift_keywords:
            weight_key = "shift"
        elif op in mux_keywords:
            weight_key = "mux"
        elif op in logic_keywords or "logic" in op:
            weight_key = "logic"
        else:
            weight_key = "logic"
        weight = config.op_type_weights.get(weight_key, 1.0)
        path_score += weight
    features.path_score = path_score
    if features.period_ns:
        try:
            period_val = float(features.period_ns)
            features.allowed_score = config.alpha * period_val
            eps = 1e-09
            features.path_score_ratio = path_score / (features.allowed_score + eps)
        except (TypeError, ValueError, ZeroDivisionError):
            features.allowed_score = None
            features.path_score_ratio = None
    else:
        features.allowed_score = None
        features.path_score_ratio = None
    if features.period_ns and features.slack_ns is not None:
        try:
            features.normalized_slack = float(features.slack_ns) / float(features.period_ns)
        except ZeroDivisionError:
            features.normalized_slack = None
    else:
        features.normalized_slack = None
    return features
