"""Check prompt builders through the text consumed by model callers."""

import json
from copy import deepcopy

import pytest

from prompts import build_repair_prompt, build_root_cause_prompt


@pytest.mark.parametrize("language", ["en", "zh"])
def test_root_cause_prompt_preserves_evidence_and_output_structure(language):
    context = {
        "violation": {"violation_type": "setup", "slack_ns": -1.25},
        "path_evidence": {"rtl_snippet_text": 'out <= {a, b};\n$display("结果");'},
        "rule_prior": {"rule_primary": "UNKNOWN", "candidates_topk": []},
    }
    original = deepcopy(context)

    prompt = build_root_cause_prompt(context, language=language)

    assert "llm_context:\n" in prompt
    payload = prompt.split("llm_context:\n", 1)[1]
    actual, end = json.JSONDecoder().raw_decode(payload)
    assert actual == original
    output_section = payload[end:]
    output = json.loads(output_section[output_section.index("{") :])
    assert output == {
        "final_root_cause": {"primary": "UNKNOWN", "secondary": []},
        "explanation": {"text": ""},
        "selection_rationale": {
            "decision": "unknown",
            "reasons": [],
            "disagreement_with_rule": [],
        },
    }
    assert context == original


@pytest.mark.parametrize(
    ("language", "allow_custom", "policy", "header"),
    [
        ("en", True, "Custom strategies are allowed.", "Here is llm_context:\n"),
        ("en", False, "Custom strategies are NOT allowed.", "Here is llm_context:\n"),
        ("zh", True, "允许 custom", "请基于以下 llm_context 输出修复建议 JSON：\n"),
        ("zh", False, "禁止 custom", "请基于以下 llm_context 输出修复建议 JSON：\n"),
    ],
)
def test_repair_prompt_preserves_candidates_and_custom_strategy_policy(
    language, allow_custom, policy, header
):
    context = {
        "final_root_cause": {"primary": "S1_combinational_path_too_long", "secondary": []},
        "candidate_set": {"candidate_strategies": [{"id": "S1_expr_simplify"}]},
        "tvir": {"rtl_snippet_lines": ["out <= a + b;", "// 中文"]},
    }
    original = deepcopy(context)

    prompt = build_repair_prompt(context, language=language, allow_custom_strategy=allow_custom)

    assert policy in prompt
    assert json.loads(prompt.split(header, 1)[1]) == original
    assert context == original
