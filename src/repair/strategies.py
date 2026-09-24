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
        title="在长组合路径中插入流水线寄存器",
        description="当同一时钟周期内在两个寄存器之间串联了过多算术或逻辑运算时，可以在路径中间引入一个新的寄存器，将原本一拍完成的计算拆分为两拍完成，从而显著缩短关键路径的组合延迟。",
        preconditions=["path_has_heavy_arith_or_logic"],
        timing_gain="high",
        risk_level="medium",
        change_scope="single_module",
        notes=[
            "可能会增加 1 个时钟周期的端到端延迟，需要确认与接口/控制逻辑的时序关系。",
            "需要重新检查下游逻辑对该信号时序的假设。",
        ],
    )
)
_add_strategy(
    RepairStrategy(
        id="S1_expr_simplify",
        root_cause_label="S1_combinational_path_too_long",
        title="重写复杂表达式以减少组合级数",
        description="对于包含多层嵌套运算或复杂条件表达式的路径，可以通过代数重写、预计算部分中间结果、合并重复子表达式等方式，降低组合逻辑的总级数，从而缩短关键路径延迟。",
        preconditions=["can_refactor_expression"],
        timing_gain="medium",
        risk_level="low",
        change_scope="local_expr",
        notes=[
            "一般不会改变整体流水线结构，属于局部重写，对系统行为影响较小。",
            "需要注意保持功能等价，可配合仿真或形式验证。",
        ],
    )
)
_add_strategy(
    RepairStrategy(
        id="S1_expr_manual_refactor",
        root_cause_label="S1_combinational_path_too_long",
        title="手工重构复杂条件/多路选择表达式",
        description="针对包含深层次嵌套条件或多级 MUX 的表达式，可以通过拆分条件判断、分阶段计算中间结果等方式，降低表达式复杂度，使综合器更容易进行逻辑优化。",
        preconditions=["can_refactor_expression"],
        timing_gain="medium",
        risk_level="low",
        change_scope="local_expr",
        notes=[
            "通常不会改变整体时序结构，但可能改写条件逻辑，需要仔细验证功能行为。",
            "适合 slack 略为为负或接近临界的路径。",
        ],
    )
)
_add_strategy(
    RepairStrategy(
        id="S2_replicate_driver_or_logic",
        root_cause_label="S2_high_fanout",
        title="复制/分裂高扇出驱动源（寄存器或组合逻辑）",
        description="当某个控制/数据信号扇出过高导致路由延迟显著增大时，可以通过复制驱动寄存器或复制一段组合逻辑，为不同下游扇出组生成局部副本，从而降低单网扇出与线长压力。",
        preconditions=["has_high_fanout_signal"],
        timing_gain="medium",
        risk_level="medium",
        change_scope="local",
        notes=["可能增加寄存器/逻辑面积；需要确保功能等价与复位/使能语义一致。"],
    )
)
_add_strategy(
    RepairStrategy(
        id="S2_buffer_or_stage_fanout_control",
        root_cause_label="S2_high_fanout",
        title="对高扇出信号做分级/缓冲（插入一级局部寄存或分级使能）",
        description="对高扇出的控制信号（如 enable/valid/reset-like）可采用分级传播：先生成较小扇出的一组局部控制，再由局部控制驱动更小范围逻辑，降低全局单网扇出与布线压力。",
        preconditions=["has_high_fanout_signal"],
        timing_gain="medium",
        risk_level="low",
        change_scope="local",
        notes=["可能引入额外延迟（尤其是寄存分级）；需检查时序/协议是否允许。"],
    )
)
_add_strategy(
    RepairStrategy(
        id="S3_pipeline_insert_core",
        root_cause_label="S3_complex_arithmetic_no_pipeline",
        title="在核心计算路径中插入流水线级",
        description="当单个 always 块内既包含乘法、加法等重运算，又存在较多后续逻辑时，可在重运算与后续逻辑之间插入一个寄存器，将一拍内的计算拆分为多拍，以缓解关键路径的时序压力。",
        preconditions=["path_is_single_module"],
        timing_gain="high",
        risk_level="medium",
        change_scope="single_module",
        notes=[
            "会显式增加流水线深度，需要评估对数据通路和控制通路的一致性影响。",
            "可能需要在上游/下游增加对齐寄存器或调整握手机制。",
        ],
    )
)
_add_strategy(
    RepairStrategy(
        id="S3_pipeline_rebalance",
        root_cause_label="S3_complex_arithmetic_no_pipeline",
        title="重平衡现有流水线划分",
        description="当部分流水线级负载过重而其它级较空时，可以通过重新划分计算逻辑，在不显著增加总延迟的前提下，将耗时运算拆分到不同流水线级中，使各级延迟更加均衡。",
        preconditions=["pipeline_structure_present"],
        timing_gain="medium",
        risk_level="medium",
        change_scope="single_module",
        notes=[
            "可能需要较大幅度调整现有 always 块内的计算顺序和寄存器位置。",
            "需要重新验证整个流水线的功能和时序关系。",
        ],
    )
)
_add_strategy(
    RepairStrategy(
        id="S3_local_simplify_then_pipeline",
        root_cause_label="S3_complex_arithmetic_no_pipeline",
        title="先局部简化表达式，再考虑插入流水线",
        description="对于边界情况的违例，可以先通过局部表达式重写或算子替换减轻路径延迟，如果仍不足以关闭时序，再在关键位置插入少量流水线寄存器，以降低对整体架构的冲击。",
        preconditions=["can_refactor_expression"],
        timing_gain="medium",
        risk_level="low",
        change_scope="single_module",
        notes=[
            "适合 slack 略为为负、尚不需要激进结构调整的场景。",
            "有助于减少不必要的流水线级数增加。",
        ],
    )
)
_add_strategy(
    RepairStrategy(
        id="S4_registerize_boundary",
        root_cause_label="S4_cross_hierarchy_path",
        title="在模块边界处对信号进行寄存器化",
        description="当关键路径跨越多个模块时，可以在模块输出或输入处增加寄存器，将长路径切分为多个较短的模块内部路径，从而降低跨模块连线和逻辑带来的延迟。",
        preconditions=[],
        timing_gain="high",
        risk_level="medium",
        change_scope="cross_module",
        notes=[
            "会增加模块间通信的拍数，需要确认与协议/时序假设是否兼容。",
            "需要在系统层面重新评估数据流和控制流延迟。",
        ],
    )
)
_add_strategy(
    RepairStrategy(
        id="S4_module_refactoring",
        root_cause_label="S4_cross_hierarchy_path",
        title="调整模块划分以缩短跨模块关键路径",
        description="对于频繁出现在关键路径上的跨模块连接，可以通过重新划分模块边界，将强耦合逻辑合并到同一模块，或将关键组合逻辑集中到一个更易优化的地方，以减少跨模块路径。",
        preconditions=["can_change_module_boundary"],
        timing_gain="medium",
        risk_level="high",
        change_scope="cross_module",
        notes=[
            "可能涉及接口重定义和较大范围的重构，对项目风险较高。",
            "适合作为对局部优化和寄存器化方案效果不佳时的备选方案。",
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
