from repair.planner import RepairPlanner, RepairPlannerConfig
from repair.strategies import STRATEGY_LIBRARY


def test_planner_removes_cdc_and_enforces_latency_constraint():
    assert all(s.root_cause_label.startswith("S") for s in STRATEGY_LIBRARY.values())
    final = {"final_root_cause": {"primary": "S1_combinational_path_too_long", "secondary": []}}
    planner = RepairPlanner(RepairPlannerConfig(max_strategies=20, allow_latency_increase=False))
    plan = planner.plan(final, rule_features={"period_ns": 2, "slack_ns": -1})
    assert plan.candidate_strategies
    assert all("latency_increase_allowed" not in s.preconditions for s in plan.candidate_strategies)
    assert "S3_local_simplify_then_pipeline" not in {s.id for s in plan.candidate_strategies}
    permitted = RepairPlanner(RepairPlannerConfig(max_strategies=20, allow_latency_increase=True))
    assert "S1_pipeline_insert_basic" in {s.id for s in permitted.plan(final).candidate_strategies}
