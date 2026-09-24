"""Build repair suggestion prompts from prepared diagnosis and candidates."""

import json


def build_repair_prompt(
    llm_context: dict, *, language: str = "en", allow_custom_strategy: bool = True
) -> str:
    """Render JSON-serializable context with the chosen strategy policy."""
    lang = (language or "en").lower()
    allow_custom = bool(allow_custom_strategy)
    ctx_json = json.dumps(llm_context, ensure_ascii=False, indent=2)

    if lang.startswith("zh"):
        instructions = (
            "你是一名经验丰富的硬件设计与时序/CDC 收敛专家。\n"
            "给定 llm_context（JSON），请输出一个严格的 JSON 修复建议对象（不要输出Markdown，不要输出额外说明）。\n\n"
            "【目标】输出要能被人类工程师直接拿去指导 RTL 修复与验证。\n\n"
            "【必须输出的字段】\n"
            "- chosen_strategies: list，每项至少包含 {source, id, confidence, reason}。\n"
            f"  - source 只能是 'library' 或 'custom'。{'允许 custom，但必须额外给出 title，并解释为何候选集合不足。' if allow_custom else '禁止 custom。'}\n"
            "- edit_locations: list，每项包含 {location_type, ref, rationale}。\n"
            "  - location_type 只能是 'dataflow_node' 或 'rtl_snippet_line_range'。\n"
            '  - dataflow_node.ref={"index":int} 0-based 指向 dataflow_path[index]\n'
            '  - rtl_snippet_line_range.ref={"start":int,"end":int} 0-based 指向 rtl_snippet 行范围\n'
            "- engineer_advice: string list，给出可执行建议（分点）。\n"
            "- code_hint: {language:'verilog', patch_like:[...]} 给出简短伪补丁（可为空）。\n"
            "- risks: string list，说明副作用/风险与验证建议。\n\n"
            "【强约束】\n"
            "1) 优先从 candidate_set.candidate_strategies 中选择（source='library' 且 id 必须来自候选集合）；\n"
            f"2) {'候选不足时可提出少量 custom，但必须说明为什么候选不够。' if allow_custom else '禁止提出候选集合之外策略。'}\n"
            "3) 不得编造 llm_context 中不存在的信号/模块/寄存器名；只能引用 llm_context 中看到的名字。\n"
            "4) root_cause_explanation 仅为叙述参考，不得把其中未被结构化证据支持的内容当作事实。\n"
        )
        header = "请基于以下 llm_context 输出修复建议 JSON：\n"
    else:
        instructions = (
            "You are an experienced hardware designer and timing/CDC closure expert.\n"
            "Given llm_context (JSON), output a strict JSON repair suggestion object ONLY (no markdown, no extra text).\n\n"
            "Required fields: chosen_strategies, edit_locations, engineer_advice, code_hint, risks.\n"
            f"Custom strategies are {'allowed' if allow_custom else 'NOT allowed'}.\n"
            "Hard constraints:\n"
            "1) Prefer selecting from candidate_set.candidate_strategies (library ids must come from the candidate set);\n"
            "2) Do NOT invent signal/module/reg names not present in llm_context;\n"
            "3) root_cause_explanation is narrative-only reference; prefer structured evidence.\n"
        )
        header = "Here is llm_context:\n"

    return f"{instructions}\n{header}{ctx_json}\n"
