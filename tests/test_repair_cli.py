import json

import pytest

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


@pytest.mark.parametrize(
    "raw",
    [
        "",
        '  {"repaired_rtl":',
        "[]",
        '{"repaired_rtl":"module m; endmodule","latency_change_cycles":2}',
    ],
)
def test_cli_preserves_responses_before_parsing(tmp_path, source, config, backend, raw):
    kb = tmp_path / "kb"
    build_knowledge_base(source, kb, config, backend=backend)
    rtl = tmp_path / "input.v"
    rtl.write_text("module m; endmodule", encoding="utf-8")
    tvir = tmp_path / "tvir.json"
    tvir.write_text(
        json.dumps(
            {"context": {"violation_type": "hold", "launch_clock": "a", "capture_clock": "b"}}
        ),
        encoding="utf-8",
    )
    output = tmp_path / "output"
    diagnosis = '  {"final_root_cause":{"primary":"S1_combinational_path_too_long"}}\n'

    class Model:
        count = 0

        def generate_response(self, prompt):
            self.count += 1
            if self.count == 1:
                content = diagnosis
            else:
                saved = json.loads(
                    (output / "root_cause_response.json").read_text(encoding="utf-8")
                )
                assert saved["content"] == diagnosis
                content = raw
            return {
                "content": content,
                "model": "test-model",
                "finish_reason": "length",
                "usage": {"completion_tokens": 32768},
                "response": {"provider_field": "kept"},
            }

    args = [
        "--rtl",
        str(rtl),
        "--tvir",
        str(tvir),
        "--kb",
        str(kb),
        "--output",
        str(output),
        "--mode",
        "bm25",
    ]
    assert main(args, llm_client=Model()) == 0
    response = json.loads((output / "repair_response.json").read_text(encoding="utf-8"))
    assert response["content"] == raw
    assert response["model"] == "test-model"
    assert response["finish_reason"] == "length"
    assert response["usage"]["completion_tokens"] == 32768
    assert response["response"] == {"provider_field": "kept"}
    result = json.loads((output / "result.json").read_text(encoding="utf-8"))
    assert result["repair"]["raw_output"] == raw
    assert result["validation_status"] == "not_run"
    if raw.endswith("2}"):
        assert (output / "repaired.v").read_text(encoding="utf-8") == "module m; endmodule"
        assert result["repair"]["parse_status"] == "parsed"
    else:
        assert not (output / "repaired.v").exists()
        assert result["repair"]["parse_status"] == "failed"


def test_cli_keeps_diagnosis_when_later_retrieval_fails(tmp_path):
    rtl = tmp_path / "input.v"
    rtl.write_text("module m; endmodule", encoding="utf-8")
    tvir = tmp_path / "tvir.json"
    tvir.write_text('{"context":{"violation_type":"setup"}}', encoding="utf-8")
    output = tmp_path / "output"

    class Model:
        count = 0

        def generate(self, prompt):
            self.count += 1
            return "  original response\n"

    model = Model()
    args = [
        "--rtl",
        str(rtl),
        "--tvir",
        str(tvir),
        "--kb",
        str(tmp_path / "missing-kb"),
        "--output",
        str(output),
    ]
    assert main(args, llm_client=model) == 1
    response_path = output / "root_cause_response.json"
    assert (
        json.loads(response_path.read_text(encoding="utf-8"))["content"] == "  original response\n"
    )
    before = response_path.read_bytes()
    assert main(args, llm_client=model) == 1
    assert model.count == 1
    assert response_path.read_bytes() == before
