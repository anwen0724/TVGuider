import json

from rag import build_knowledge_base
from repair.__main__ import main


def test_cli_saves_candidate_and_evidence_without_overwriting_input(
    tmp_path, source, config, backend
):
    kb = tmp_path / "kb"
    build_knowledge_base(source, kb, config, backend=backend)
    rtl = tmp_path / "input.v"
    original = (
        "module example(input clk, input a, output reg q); always @(posedge clk) q <= a; endmodule"
    )
    rtl.write_text(original, encoding="utf-8")
    tv = tmp_path / "tvir.json"
    tv.write_text(
        json.dumps(
            {
                "context": {"violation_type": "setup", "period_ns": 2, "slack_ns": -1},
                "dataflow_path": [],
                "rtl_snippet": [],
            }
        ),
        encoding="utf-8",
    )

    class Model:
        count = 0

        def generate(self, prompt):
            self.count += 1
            if self.count == 1:
                return '{"final_root_cause":{"primary":"S1_combinational_path_too_long","secondary":[]}}'
            payload = json.loads(prompt.split("Here is llm_context:\n")[1])
            return json.dumps(
                {
                    "repaired_rtl": original,
                    "change_summary": ["Fixture only"],
                    "knowledge_used": [payload["knowledge"]["chunks"][0]["chunk_id"]],
                    "latency_change_cycles": 0,
                }
            )

    output = tmp_path / "output"
    args = [
        "--rtl",
        str(rtl),
        "--tvir",
        str(tv),
        "--kb",
        str(kb),
        "--output",
        str(output),
        "--mode",
        "bm25",
    ]
    model = Model()
    assert main(args, llm_client=model) == 0
    assert (output / "repaired.v").read_text(encoding="utf-8") == original
    assert (
        json.loads((output / "result.json").read_text(encoding="utf-8"))["validation_status"]
        == "not_run"
    )
    assert rtl.read_text(encoding="utf-8") == original
    assert main(args, llm_client=model) == 1
    assert model.count == 2


def test_cli_rejects_invalid_output_budget_before_reading_inputs(capsys):
    status = main(
        [
            "--rtl",
            "unused",
            "--tvir",
            "unused",
            "--kb",
            "unused",
            "--output",
            "unused",
            "--max-tokens",
            "0",
        ]
    )
    assert status == 1
    assert "max-tokens" in capsys.readouterr().err
