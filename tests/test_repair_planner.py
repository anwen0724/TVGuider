from repair.planner import RepairPlanner, RepairPlannerConfig
from repair.strategies import STRATEGY_LIBRARY


def test_planner_includes_pipeline_candidates_without_permission_flag():
    assert all(s.root_cause_label.startswith("S") for s in STRATEGY_LIBRARY.values())
    final = {"final_root_cause": {"primary": "S1_combinational_path_too_long", "secondary": []}}
    planner = RepairPlanner(RepairPlannerConfig(max_strategies=20))
    plan = planner.plan(final, rule_features={"period_ns": 2, "slack_ns": -1})
    assert plan.candidate_strategies
    assert "S3_local_simplify_then_pipeline" in {s.id for s in plan.candidate_strategies}
    assert "S1_pipeline_insert_basic" in {s.id for s in plan.candidate_strategies}
