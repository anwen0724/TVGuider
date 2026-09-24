"""Build root-cause diagnosis prompts from prepared evidence."""

import json


def build_root_cause_prompt(llm_context: dict, *, language: str = "en") -> str:
    """Render JSON-serializable context without changing it or calling a model."""
    lang = (language or "en").lower()
    context_json = json.dumps(llm_context, ensure_ascii=False, indent=2)

    if lang.startswith("zh"):
        instructions = (
            "你是一名经验丰富的硬件设计与时序分析专家。\n"
            "你会收到一个 llm_context(JSON)，其中包含：\n"
            "- violation：基本时序信息（slack/period/clock等）\n"
            "- path_evidence：数据流路径与相关 RTL 代码片段\n"
            "- tvir_features：客观证据（path_metrics/fanout/hierarchy/cdc）\n"
            "- rule_prior：规则层先验（rule_primary/rule_secondary/candidates_topk/diagnostic_features）\n\n"
            "【重要】你可以不同意规则层的先验结论，作为重要参考信息即可。\n"
            "如果证据/特征与规则层结论矛盾，你应当纠偏并选择更符合证据的最终标签。\n"
            "如果证据严重缺失或冲突，也可以选择 'UNKNOWN'。\n\n"
            "你的任务：\n"
            "1) 基于证据/特征为主来决定最终根因标签(final_root_cause)；可参考 rule_prior，但不得被其束缚；\n"
            "2) 输出对“为什么会违时/存在风险”的解释 explanation.text（建议 3~6 句，避免给具体修复建议）；\n"
            "3) 输出 selection_rationale：说明你是沿用规则还是进行了纠偏，并点出关键证据。\n\n"
            "输出要求（非常重要）：\n"
            "- 只能输出一个严格合法的 JSON 对象；\n"
            "- 不要输出任何额外文字；不要使用 Markdown 代码块；\n"
            "- final_root_cause.primary 必须是 allowed_labels 中的一个；secondary 最多 2 个；\n"
            "- selection_rationale.decision 只能是 kept_rule / adjusted / unknown。\n"
        )
    else:
        instructions = (
            "You are an experienced hardware timing analysis expert.\n"
            "You will receive llm_context (JSON) including:\n"
            "- violation (slack/period/clocks)\n"
            "- path_evidence (dataflow path + RTL snippet)\n"
            "- tvir_features (objective evidence: path_metrics/fanout/hierarchy/cdc)\n"
            "- rule_prior (rule-based prior: rule_primary/rule_secondary/candidates_topk/diagnostic_features)\n\n"
            "IMPORTANT: You are NOT required to agree with the rule-based prior,but you can treat them as important reference information.\n"
            "If the evidence/features contradict the prior labels, you SHOULD adjust the final labels accordingly.\n"
            "If evidence is severely missing or contradictory, you may choose 'UNKNOWN'.\n\n"
            "Your tasks:\n"
            "1) Decide the final root-old_cause labels (final_root_cause) based primarily on evidence/features;\n"
            "2) Provide explanation.text (3–6 sentences) explaining why the violation/risk occurs; do NOT provide concrete fix steps;\n"
            "3) Provide selection_rationale explaining whether you kept the prior or adjusted it, and cite the key evidence.\n\n"
            "IMPORTANT output requirements:\n"
            "- Output ONE valid JSON object only;\n"
            "- No extra text; no Markdown code fences;\n"
            "- final_root_cause.primary must be one of allowed_labels; secondary up to 2;\n"
            "- selection_rationale.decision must be kept_rule / adjusted / unknown.\n"
        )

    output_skeleton = {
        "final_root_cause": {"primary": "UNKNOWN", "secondary": []},
        "explanation": {"text": ""},
        "selection_rationale": {
            "decision": "unknown",
            "reasons": [],
            "disagreement_with_rule": [],
        },
    }

    return (
        f"{instructions}\n\n"
        "llm_context:\n"
        f"{context_json}\n\n"
        "You MUST output JSON in the following structure (fill values accordingly):\n"
        f"{json.dumps(output_skeleton, ensure_ascii=False, indent=2)}\n"
    )
