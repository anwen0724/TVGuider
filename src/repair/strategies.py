from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RepairStrategy:
    id: str
    root_cause_label: str
    title: str
    description: str
    preconditions: list[str]
    timing_gain: str
    risk_level: str
    change_scope: str
    notes: list[str]


STRATEGY_LIBRARY: dict[str, RepairStrategy] = {}


def _add_strategy(s: RepairStrategy) -> None:
    if s.id in STRATEGY_LIBRARY:
        raise ValueError(f"Duplicate strategy id: {s.id}")
    STRATEGY_LIBRARY[s.id] = s


_add_strategy(
    RepairStrategy(
        id="S1_pipeline_insert_basic",
        root_cause_label="S1_combinational_path_too_long",
        title="Insert a pipeline register into a long combinational path",
        description="When too many arithmetic or logic operations are chained between two registers within one clock cycle, insert a register along the path to split the computation across two cycles and significantly reduce the combinational delay of the critical path.",
        preconditions=["path_has_heavy_arith_or_logic"],
        timing_gain="high",
        risk_level="medium",
        change_scope="single_module",
        notes=[
            "May add one clock cycle of end-to-end latency; check compatibility with interface and control timing.",
            "Recheck downstream logic assumptions about the timing of this signal.",
        ],
    )
)
_add_strategy(
    RepairStrategy(
        id="S1_expr_simplify",
        root_cause_label="S1_combinational_path_too_long",
        title="Rewrite complex expressions to reduce combinational logic depth",
        description="For paths with nested operations or complex conditional expressions, use algebraic rewriting, precomputation of intermediate results, or common subexpression elimination to reduce combinational logic depth and shorten critical-path delay.",
        preconditions=["can_refactor_expression"],
        timing_gain="medium",
        risk_level="low",
        change_scope="local_expr",
        notes=[
            "Usually preserves the overall pipeline structure and limits changes to local expressions, with little impact on system behavior.",
            "Preserve functional equivalence and check it through simulation or formal verification.",
        ],
    )
)
_add_strategy(
    RepairStrategy(
        id="S1_expr_manual_refactor",
        root_cause_label="S1_combinational_path_too_long",
        title="Manually refactor complex conditional or multiplexer expressions",
        description="For expressions with deeply nested conditions or multiple MUX levels, separate condition evaluations or break intermediate computations into steps to reduce expression complexity and make logic optimization easier for the synthesis tool.",
        preconditions=["can_refactor_expression"],
        timing_gain="medium",
        risk_level="low",
        change_scope="local_expr",
        notes=[
            "Usually preserves the overall timing structure, but may alter conditional logic; verify functional behavior carefully.",
            "Suitable for paths with slightly negative slack or timing close to the limit.",
        ],
    )
)
_add_strategy(
    RepairStrategy(
        id="S2_replicate_driver_or_logic",
        root_cause_label="S2_high_fanout",
        title="Replicate or split a high-fanout driver register or logic cone",
        description="When excessive fanout on a control or data signal significantly increases routing delay, replicate the driving register or combinational logic for separate downstream load groups to reduce fanout per net and wire length.",
        preconditions=["has_high_fanout_signal"],
        timing_gain="medium",
        risk_level="medium",
        change_scope="local",
        notes=["May increase register or logic area; preserve functional equivalence and consistent reset and enable semantics."],
    )
)
_add_strategy(
    RepairStrategy(
        id="S2_buffer_or_stage_fanout_control",
        root_cause_label="S2_high_fanout",
        title="Stage or buffer high-fanout signals using local registers or staged enables",
        description="Distribute high-fanout control signals, such as enable, valid, or reset-like signals, in stages: generate local controls with smaller fanout, then use them to drive smaller logic regions, reducing global net fanout and routing pressure.",
        preconditions=["has_high_fanout_signal"],
        timing_gain="medium",
        risk_level="low",
        change_scope="local",
        notes=["May introduce additional latency, especially with registered stages; check whether timing and protocol requirements allow it."],
    )
)
_add_strategy(
    RepairStrategy(
        id="S3_pipeline_insert_core",
        root_cause_label="S3_complex_arithmetic_no_pipeline",
        title="Insert a pipeline stage into the core computation path",
        description="When a single always block contains expensive operations such as multiplication or addition followed by substantial logic, insert a register between the arithmetic and subsequent logic to spread the computation across multiple cycles and ease critical-path timing pressure.",
        preconditions=["path_is_single_module"],
        timing_gain="high",
        risk_level="medium",
        change_scope="single_module",
        notes=[
            "Increases pipeline depth; assess the impact on alignment between data and control paths.",
            "May require upstream or downstream alignment registers or changes to the handshake mechanism.",
        ],
    )
)
_add_strategy(
    RepairStrategy(
        id="S3_pipeline_rebalance",
        root_cause_label="S3_complex_arithmetic_no_pipeline",
        title="Rebalance the existing pipeline stages",
        description="When some pipeline stages are overloaded while others have little work, repartition the computation across stages to distribute expensive operations more evenly without significantly increasing total latency.",
        preconditions=["pipeline_structure_present"],
        timing_gain="medium",
        risk_level="medium",
        change_scope="single_module",
        notes=[
            "May require substantial changes to computation order and register placement within existing always blocks.",
            "Reverify the functionality and timing relationships of the entire pipeline.",
        ],
    )
)
_add_strategy(
    RepairStrategy(
        id="S3_local_simplify_then_pipeline",
        root_cause_label="S3_complex_arithmetic_no_pipeline",
        title="Simplify expressions locally before considering pipeline insertion",
        description="For marginal timing violations, first reduce path delay through local expression rewriting or operator substitution. If timing still does not close, insert a small number of pipeline registers at critical locations to limit the impact on the overall architecture.",
        preconditions=["can_refactor_expression"],
        timing_gain="medium",
        risk_level="low",
        change_scope="single_module",
        notes=[
            "Suitable for slightly negative slack that does not yet require aggressive structural changes.",
            "Helps avoid unnecessary increases in the number of pipeline stages.",
        ],
    )
)
_add_strategy(
    RepairStrategy(
        id="S4_registerize_boundary",
        root_cause_label="S4_cross_hierarchy_path",
        title="Register signals at module boundaries",
        description="When a critical path crosses multiple modules, add registers at module inputs or outputs to divide it into shorter paths within individual modules, reducing delay from inter-module connections and logic.",
        preconditions=[],
        timing_gain="high",
        risk_level="medium",
        change_scope="cross_module",
        notes=[
            "Adds cycles to inter-module communication; check compatibility with protocol and timing assumptions.",
            "Reassess data-flow and control-flow latency at the system level.",
        ],
    )
)
_add_strategy(
    RepairStrategy(
        id="S4_module_refactoring",
        root_cause_label="S4_cross_hierarchy_path",
        title="Repartition modules to shorten critical paths across module boundaries",
        description="For inter-module connections that frequently appear on critical paths, redraw module boundaries to group tightly coupled logic in one module or place critical combinational logic together where it is easier to optimize, reducing paths across module boundaries.",
        preconditions=["can_change_module_boundary"],
        timing_gain="medium",
        risk_level="high",
        change_scope="cross_module",
        notes=[
            "May require interface changes and extensive refactoring, creating significant project risk.",
            "Consider as a fallback when local optimization and register insertion are ineffective.",
        ],
    )
)
CAUSE_TO_STRATEGIES = {
    "S1_combinational_path_too_long": [
        "S1_pipeline_insert_basic",
        "S1_expr_simplify",
        "S1_expr_manual_refactor",
        "S3_local_simplify_then_pipeline",
    ],
    "S2_high_fanout": ["S2_replicate_driver_or_logic", "S2_buffer_or_stage_fanout_control"],
    "S3_complex_arithmetic_no_pipeline": [
        "S3_pipeline_insert_core",
        "S3_pipeline_rebalance",
        "S3_local_simplify_then_pipeline",
    ],
    "S4_cross_hierarchy_path": ["S4_registerize_boundary", "S4_module_refactoring"],
}
