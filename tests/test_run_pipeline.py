import importlib.util
import json
from pathlib import Path

import pytest

from rag import build_knowledge_base

spec = importlib.util.spec_from_file_location(
    "run_pipeline", Path(__file__).resolve().parents[1] / "src" / "run_pipeline.py"
)
pipeline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pipeline)


def test_directory_scan_matches_nested_cases_without_fixed_filenames(tmp_path):
    rtl_dir, report_dir = tmp_path / "rtl", tmp_path / "reports"
    for root in (rtl_dir, report_dir):
        (root / "group").mkdir(parents=True)
    (rtl_dir / "group" / "alpha.v").write_text("module alpha; endmodule")
    (report_dir / "group" / "alpha.rpt").write_text("report")
    (rtl_dir / "beta.v").write_text("module beta; endmodule")
    (report_dir / "beta.txt").write_text("report")
    (rtl_dir / "notes.md").write_text("not input")
    cases = pipeline.discover_cases(rtl_dir, report_dir)
    assert [(str(key).replace("\\", "/"), rtl.name, report.name) for key, rtl, report in cases] == [
        ("beta", "beta.v", "beta.txt"),
        ("group/alpha", "alpha.v", "alpha.rpt"),
    ]


def test_ambiguous_reports_do_not_silently_choose_one(tmp_path):
    rtl_dir, report_dir = tmp_path / "rtl", tmp_path / "reports"
    rtl_dir.mkdir()
    report_dir.mkdir()
    (rtl_dir / "a.v").write_text("module a; endmodule")
    (report_dir / "a.txt").write_text("first report")
    (report_dir / "a.rpt").write_text("second report")
    with pytest.raises(ValueError, match="a"):
        pipeline.discover_cases(rtl_dir, report_dir)


@pytest.fixture
def configured_pipeline(tmp_path, monkeypatch, source, config, backend):
    rtl_dir, report_dir = tmp_path / "rtl", tmp_path / "reports"
    rtl_dir.mkdir()
    report_dir.mkdir()
    rtl = "module example(input clk, input [7:0] a, output reg [7:0] q);\nreg [7:0] x;\nalways @(posedge clk) begin x <= a; q <= x + 1; end\nendmodule\n"
    report = """Slack (VIOLATED) : -1.000ns
Source: x_reg[0]/C
Destination: q_reg[0]/D
Path Group: clk
Path Type: Setup
Requirement: 2.000ns
Data Path Delay: 3.000ns (logic 2.000ns route 1.000ns)
Logic Levels: 5
"""
    (rtl_dir / "example.v").write_text(rtl, encoding="utf-8")
    (report_dir / "example.txt").write_text(report, encoding="utf-8")
    kb = tmp_path / "kb"
    build_knowledge_base(source, kb, config, backend=backend)
    output = tmp_path / "output"
    for name, value in {
        "PROJECT_ROOT": tmp_path,
        "RTL_DIR": Path("rtl"),
        "REPORT_DIR": Path("reports"),
        "OUTPUT_DIR": Path("output"),
        "KB_DIR": Path("kb"),
        "RETRIEVAL_MODE": "hybrid",
    }.items():
        monkeypatch.setattr(pipeline, name, value)
    other_cwd = tmp_path / "unrelated-working-directory"
    other_cwd.mkdir()
    monkeypatch.chdir(other_cwd)
    return output, rtl_dir, report_dir


@pytest.mark.parametrize(
    "raw",
    [
        "",
        '  incomplete {"repaired_rtl":',
        "[]",
        '{"repaired_rtl":"module changed; endmodule","latency_change_cycles":3,"knowledge_used":["unknown-chunk"]}',
    ],
)
def test_full_directory_pipeline_saves_one_file_per_stage(configured_pipeline, backend, raw):
    output, rtl_dir, _ = configured_pipeline
    original = (rtl_dir / "example.v").read_bytes()
    root_response = {
        "content": '{"final_root_cause":{"primary":"S1_combinational_path_too_long"},"explanation":{"text":"Long combinational path"}}',
        "model": "fixture",
        "finish_reason": "stop",
        "usage": {"completion_tokens": 50},
        "response": {"provider_field": "unchanged"},
    }
    repair_response = {
        "content": raw,
        "model": "fixture",
        "finish_reason": "length",
        "usage": {"completion_tokens": 32768},
        "response": {},
    }

    class Model:
        def __init__(self):
            self.prompts = []

        def generate_response(self, prompt):
            self.prompts.append(prompt)
            if len(self.prompts) == 1:
                return root_response
            saved = json.loads((output / "example" / "root_cause.json").read_text(encoding="utf-8"))
            assert set(saved) == {"rule_analysis", "model_raw_response", "model_analysis"}
            assert saved["model_raw_response"] == root_response
            assert saved["model_analysis"]["explanation"]["text"] == "Long combinational path"
            assert "Long combinational paths reduce setup slack" in prompt
            return repair_response

    model = Model()
    assert pipeline.main(llm_client=model, embedding_backend=backend) == 0
    assert len(model.prompts) == 2
    case_dir = output / "example"
    assert {path.name for path in case_dir.iterdir()} == {"root_cause.json", "repair_result.json"}
    result = json.loads((case_dir / "repair_result.json").read_text(encoding="utf-8"))
    assert result["model_raw_response"] == repair_response
    assert result["model_result"]["parse_status"] == (
        "parsed" if raw.startswith('{"repaired_rtl"') else "failed"
    )
    assert result["model_result"]["raw_output"] == raw
    assert result["model_result"]["validation_status"] == "not_run"
    assert result["retrieval"]["query"].isascii()
    assert result["retrieval"]["mode"] == "hybrid"
    assert result["retrieval"]["top_k"] == 5
    assert (rtl_dir / "example.v").read_bytes() == original
    assert pipeline.main(llm_client=model, embedding_backend=backend) == 1
    assert len(model.prompts) == 2


@pytest.mark.parametrize("failure", ["retrieval", "repair_call", "root_parsing"])
def test_root_result_remains_when_a_later_step_fails(
    configured_pipeline, backend, monkeypatch, failure
):
    output, _, _ = configured_pipeline
    response = {
        "content": "  invalid JSON\n",
        "model": "fixture",
        "finish_reason": "length",
        "usage": None,
        "response": {},
    }

    class Model:
        calls = 0

        def generate_response(self, prompt):
            self.calls += 1
            if self.calls > 1:
                raise RuntimeError("Test service failure")
            return response

    if failure == "retrieval":
        monkeypatch.setattr(pipeline, "KB_DIR", Path("missing-kb"))
    elif failure == "root_parsing":

        def fail_parse(*args):
            raise RuntimeError("Test parsing failure")

        monkeypatch.setattr(pipeline.RootCauseExplainer, "parse_response", fail_parse)
    model = Model()
    assert pipeline.main(llm_client=model, embedding_backend=backend) == 1
    saved = json.loads((output / "example" / "root_cause.json").read_text(encoding="utf-8"))
    assert saved["model_raw_response"] == response
    assert saved["rule_analysis"]["candidates"]
    if failure != "root_parsing":
        assert saved["model_analysis"]["parse_status"] == "failed"
    else:
        assert saved["model_analysis"] is None
    assert not (output / "example" / "repair_result.json").exists()
