import json

import pytest

from rag import build_knowledge_base, search_knowledge_base
from repair.contracts import RepairConstraints, RepairOutputError
from repair.generator import RepairSuggestionGenerator
from repair.planner import RepairPlanner

RTL = "module example(input clk, input a, input b, output reg q);\nalways @(posedge clk) q <= a + b;\nendmodule\n"


@pytest.fixture
def generation_case(tmp_path, source, config, backend):
    kb = tmp_path / "kb"
    build_knowledge_base(source, kb, config, backend=backend)
    retrieval = search_knowledge_base(kb, "setup combinational timing", mode="bm25")
    tvir = {
        "context": {"violation_type": "setup", "period_ns": 2, "slack_ns": -1},
        "dataflow_path": [],
        "rtl_snippet": ["q <= a + b;"],
    }
    final = {"final_root_cause": {"primary": "S1_combinational_path_too_long", "secondary": []}}
    plan = RepairPlanner().plan(final, tvir=tvir)
    response = {
        "chosen_strategies": [],
        "edit_locations": [],
        "engineer_advice": ["Keep the interface."],
        "code_hint": {"language": "verilog", "patch_like": []},
        "risks": ["STA not run."],
        "repaired_rtl": RTL,
        "change_summary": ["Interface fixture; no real repair evaluated."],
        "knowledge_used": [retrieval.results[0].chunk.chunk_id],
        "latency_change_cycles": 0,
    }
    return tvir, final, plan, retrieval, response


class Client:
    def __init__(self, response):
        self.response = response
        self.prompts = []

    def generate(self, prompt):
        self.prompts.append(prompt)
        return json.dumps(self.response)


def test_full_rtl_and_retrieved_evidence_reach_the_model(generation_case):
    tvir, final, plan, retrieval, response = generation_case
    client = Client(response)
    result = RepairSuggestionGenerator(client).generate(
        tvir=tvir,
        module2_output=final,
        repair_plan=plan,
        original_rtl=RTL,
        retrieval=retrieval,
        constraints=RepairConstraints(design_context="create_clock -period 2 clk"),
    )
    payload = json.loads(client.prompts[0].split("Here is llm_context:\n", 1)[1])
    assert payload["original_rtl"] == RTL
    assert payload["knowledge"]["build_id"] == retrieval.build_id
    assert payload["knowledge"]["chunks"][0]["sources"] == ["https://example.com/sta"]
    assert payload["constraints"]["allow_latency_increase"] is False
    assert result.suggestion["repaired_rtl"] == RTL
    assert result.suggestion["validation_status"] == "not_run"


def test_model_cannot_replace_program_owned_diagnosis_or_candidates(generation_case):
    tvir, final, plan, retrieval, response = generation_case
    response["summary"] = {"final_primary": "fabricated"}
    response["candidate_strategies"] = [{"id": "fabricated"}]
    response["validation_status"] = "passed"
    result = RepairSuggestionGenerator(Client(response)).generate(
        tvir=tvir,
        module2_output=final,
        repair_plan=plan,
        original_rtl=RTL,
        retrieval=retrieval,
    )
    assert result.suggestion["summary"]["final_primary"] == final["final_root_cause"]["primary"]
    assert {s["id"] for s in result.suggestion["candidate_strategies"]} == {
        s.id for s in plan.candidate_strategies
    }
    assert result.suggestion["validation_status"] == "not_run"


@pytest.mark.parametrize(
    "change",
    [
        "missing_rtl",
        "empty_rtl",
        "bad_citation",
        "missing_citation",
        "latency",
        "summary",
        "not_object",
    ],
)
def test_invalid_repair_is_not_returned_as_success(generation_case, change):
    tvir, final, plan, retrieval, response = generation_case
    if change == "missing_rtl":
        response.pop("repaired_rtl")
    elif change == "empty_rtl":
        response["repaired_rtl"] = " "
    elif change == "bad_citation":
        response["knowledge_used"] = ["made-up-chunk"]
    elif change == "missing_citation":
        response["knowledge_used"] = []
    elif change == "latency":
        response["latency_change_cycles"] = 1
    elif change == "summary":
        response["change_summary"] = []
    else:
        response = []
    with pytest.raises(RepairOutputError):
        RepairSuggestionGenerator(Client(response)).generate(
            tvir=tvir,
            module2_output=final,
            repair_plan=plan,
            original_rtl=RTL,
            retrieval=retrieval,
        )
