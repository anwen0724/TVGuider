import pytest

from root_cause import RootCauseClassifier
from root_cause.explanation import RootCauseExplainer


@pytest.fixture
def setup_tvir():
    return {
        "context": {
            "violation_type": "setup",
            "clock": "clk",
            "launch_clock": "clk",
            "capture_clock": "clk",
            "period_ns": 2.0,
            "slack_ns": -1.0,
        },
        "path_metrics": {"logic_levels": 12, "combinational_delay_ns": 2.5, "net_delay_ns": 0.5},
        "dataflow_path": [
            {"role": "start_reg", "name": "a"},
            {"role": "op", "op_type": "add"},
            {"role": "end_reg", "name": "q"},
        ],
        "rtl_snippet": ["always @(posedge clk) q <= a + b;"],
    }


def test_setup_classifier_excludes_cdc_candidates(setup_tvir):
    result = RootCauseClassifier().analyze(setup_tvir)
    assert result.root_cause.primary == "S1_combinational_path_too_long"
    assert {c.label for c in result.candidates} == {
        "S1_combinational_path_too_long",
        "S2_high_fanout",
        "S3_complex_arithmetic_no_pipeline",
        "S4_cross_hierarchy_path",
    }


@pytest.mark.parametrize("change", ["hold", "cross_clock"])
def test_path_type_and_clock_names_do_not_block_analysis(setup_tvir, change):
    if change == "hold":
        setup_tvir["context"]["violation_type"] = "hold"
    else:
        setup_tvir["context"]["capture_clock"] = "other_clk"
    result = RootCauseClassifier().analyze(setup_tvir)
    assert result.candidates


def test_explainer_uses_setup_prompt_and_rejects_cdc_label(setup_tvir):
    class Client:
        prompt = ""

        def generate_response(self, prompt):
            self.prompt = prompt
            return {"content": '{"final_root_cause":{"primary":"C1_cdc_missing_synchronizer"}}'}

    client = Client()
    rule = RootCauseClassifier().analyze(setup_tvir)
    result = RootCauseExplainer(client).explain_and_adjust(setup_tvir, rule)
    assert result.final_root_cause.primary == rule.root_cause.primary
    assert "final_root_cause" in client.prompt
    assert "cdc" not in client.prompt.lower()


def test_non_object_model_json_falls_back_to_rules(setup_tvir):
    response = {"content": "[]", "model": "fixture", "response": {"provider_field": "kept"}}

    class Client:
        def generate_response(self, prompt):
            return response

    rule = RootCauseClassifier().analyze(setup_tvir)
    result = RootCauseExplainer(Client()).explain_and_adjust(setup_tvir, rule)
    assert result.final_root_cause.primary == rule.root_cause.primary
    assert "parse" in result.explanation.text.lower()
    assert result.to_dict()["parse_status"] == "failed"
    assert result.to_dict()["parse_error"]
    assert result.model_raw_response == response
