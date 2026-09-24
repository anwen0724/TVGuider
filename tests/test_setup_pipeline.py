import json

import pytest

from rag import build_knowledge_base, search_knowledge_base
from repair.service import repair_from_tvir


def test_pipeline_connects_diagnosis_real_retrieval_and_full_rtl(tmp_path, source, config, backend):
    kb = tmp_path / "kb"
    built = build_knowledge_base(source, kb, config, backend=backend)
    hit = search_knowledge_base(kb, "setup", mode="bm25").results[0]
    original = (
        "module design(input clk, input a, output reg q); always @(posedge clk) q <= a; endmodule"
    )
    tvir = {
        "context": {"violation_type": "setup", "period_ns": 2, "slack_ns": -0.5},
        "dataflow_path": [],
        "rtl_snippet": ["q <= a;"],
    }

    class Model:
        def __init__(self):
            self.prompts = []

        def generate(self, prompt):
            self.prompts.append(prompt)
            if len(self.prompts) == 1:
                return json.dumps(
                    {
                        "final_root_cause": {
                            "primary": "S1_combinational_path_too_long",
                            "secondary": [],
                        },
                        "explanation": {"text": "Long combinational setup path."},
                    }
                )
            return json.dumps(
                {
                    "repaired_rtl": original,
                    "change_summary": ["Fixture for interface validation."],
                    "knowledge_used": [hit.chunk.chunk_id],
                    "latency_change_cycles": 0,
                }
            )

    model = Model()
    result = repair_from_tvir(
        tvir, original, kb_dir=kb, llm_client=model, embedding_backend=backend
    )
    assert len(model.prompts) == 2
    assert result["retrieval"]["mode"] == "hybrid"
    assert result["retrieval"]["top_k"] == 5
    assert result["retrieval"]["build_id"] == built.build_id
    assert result["retrieval"]["query"].isascii()
    assert "long combinational" in result["retrieval"]["query"]
    assert result["repair"]["suggestion"]["repaired_rtl"] == original
    assert result["repair"]["suggestion"]["knowledge_used"] == [hit.chunk.chunk_id]
    assert result["validation_status"] == "not_run"
    assert hit.chunk.text in model.prompts[1]


def test_pipeline_rejects_hold_before_model_call():
    class Model:
        def generate(self, prompt):
            pytest.fail("Out-of-scope input must not trigger a model call")

    with pytest.raises(ValueError, match="setup"):
        repair_from_tvir(
            {"context": {"violation_type": "hold"}},
            "module m; endmodule",
            kb_dir="unused",
            llm_client=Model(),
        )
