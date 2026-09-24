from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Set
import re


@dataclass
class AlwaysBlock:
    module_name: Optional[str]
    clock_signal: Optional[str]
    start_line: int
    end_line: int
    lines: List[str]
    reg_names: Set[str]


def _detect_clock_signal(line: str) -> Optional[str]:

    m = re.search(r"(?:posedge|negedge)\s+([A-Za-z_]\w*)", line)
    if m:
        return m.group(1)
    return None


def _collect_identifiers(lines: List[str]) -> Set[str]:

    ids: Set[str] = set()
    ident_re = re.compile(r"\b([A-Za-z_]\w*)\b")

    keywords = {
        "module",
        "endmodule",
        "input",
        "output",
        "inout",
        "wire",
        "reg",
        "logic",
        "always",
        "begin",
        "end",
        "if",
        "else",
        "case",
        "endcase",
        "for",
        "generate",
        "endgenerate",
        "assign",
    }

    for line in lines:
        for m in ident_re.finditer(line):
            name = m.group(1)
            if name in keywords:
                continue
            ids.add(name)

    return ids


def _normalize_reg_name_from_report(reg_name: str) -> str:

    if not reg_name:
        return ""

    core = reg_name.strip()

    core = re.sub(r"/[A-Z]+$", "", core)

    if "/" in core:
        core = core.split("/")[-1]

    core = re.sub(r"\[[^\]]+\]$", "", core)

    if core.endswith("_reg"):
        core = core[: -len("_reg")]

    return core


def extract_all_always_blocks(verilog_text: str) -> List[AlwaysBlock]:

    lines = verilog_text.splitlines()
    blocks: List[AlwaysBlock] = []

    current_module: Optional[str] = None

    module_re = re.compile(r"^\s*module\s+([A-Za-z_]\w*)")
    endmodule_re = re.compile(r"^\s*endmodule\b")
    always_re = re.compile(r"^\s*always\b")

    i = 0
    n = len(lines)

    while i < n:
        line = lines[i]

        m_mod = module_re.match(line)
        if m_mod:
            current_module = m_mod.group(1)

        if endmodule_re.match(line):
            current_module = None

        if always_re.match(line):
            start_line = i
            clock_signal = _detect_clock_signal(line)

            depth = 0
            saw_begin = False
            end_line = i

            if "begin" in line:
                saw_begin = True
                depth += line.count("begin")
                depth -= line.count("end")

            j = i + 1
            while j < n:
                l = lines[j]

                if "begin" in l:
                    saw_begin = True
                    depth += l.count("begin")
                if "end" in l:
                    depth -= l.count("end")

                if saw_begin and depth <= 0:
                    end_line = j
                    break

                j += 1

            if not saw_begin:
                end_line = start_line
            else:
                if depth > 0:
                    end_line = n - 1

            block_lines = lines[start_line : end_line + 1]
            reg_names = _collect_identifiers(block_lines)

            block = AlwaysBlock(
                module_name=current_module,
                clock_signal=clock_signal,
                start_line=start_line,
                end_line=end_line,
                lines=block_lines,
                reg_names=reg_names,
            )
            blocks.append(block)

            i = end_line + 1
            continue

        i += 1

    return blocks


def select_blocks_by_regs(
    blocks: List[AlwaysBlock],
    reg_names: List[str],
) -> List[AlwaysBlock]:

    target_set = {rn for rn in reg_names if rn}
    selected: List[AlwaysBlock] = []

    for blk in blocks:
        if blk.reg_names & target_set:
            selected.append(blk)
            continue

        if not target_set:
            continue
        joined = "\n".join(blk.lines)
        hit = False
        for rn in target_set:
            if rn in joined:
                hit = True
                break
        if hit:
            selected.append(blk)

    return selected


def extract_rtl_snippet_for_regs(
    verilog_text: str,
    reg_names: List[str],
) -> List[str]:

    if not reg_names:
        return []

    blocks = extract_all_always_blocks(verilog_text)
    if not blocks:
        return []

    selected = select_blocks_by_regs(blocks, reg_names)
    if not selected:
        return []

    selected_sorted = sorted(selected, key=lambda b: b.start_line)

    snippet: List[str] = []
    seen_ranges = set()

    for blk in selected_sorted:
        key = (blk.start_line, blk.end_line)
        if key in seen_ranges:
            continue
        seen_ranges.add(key)

        if snippet and (snippet[-1].strip() != ""):
            snippet.append("")

        snippet.extend(blk.lines)

    return snippet


def extract_rtl_snippet_for_path(
    rtl_text: str,
    start_reg_report_name: str,
    end_reg_report_name: str,
) -> List[str]:

    core_start = _normalize_reg_name_from_report(start_reg_report_name)
    core_end = _normalize_reg_name_from_report(end_reg_report_name)

    reg_cores: List[str] = []
    if core_start:
        reg_cores.append(core_start)
    if core_end and core_end != core_start:
        reg_cores.append(core_end)

    if not reg_cores:
        return []

    return extract_rtl_snippet_for_regs(rtl_text, reg_cores)
