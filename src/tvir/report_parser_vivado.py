from __future__ import annotations

import re
from typing import List, Optional
from tvir.utils import normalize_reg_core
from .raw import RawTimingViolation


_SLACK_BLOCK_RE = re.compile(r"^\s*Slack\s*\(", re.IGNORECASE | re.MULTILINE)


def _parse_float_from_line(pattern: str, text: str) -> Optional[float]:

    m = re.search(pattern, text, re.IGNORECASE)
    if not m:
        return None
    try:
        return float(m.group(1))
    except ValueError:
        return None


def _parse_int_from_line(pattern: str, text: str) -> Optional[int]:

    m = re.search(pattern, text, re.IGNORECASE)
    if not m:
        return None
    try:
        return int(m.group(1))
    except ValueError:
        return None


def _extract_hierarchy_from_reg_name(reg_name: str) -> Optional[str]:

    if not reg_name:
        return None

    core = reg_name.strip()

    core = re.sub(r"/[A-Z]+$", "", core)

    parts = core.split("/")
    if len(parts) <= 1:
        return None

    hier_parts = parts[:-1]
    hierarchy = "/".join(hier_parts)
    return hierarchy or None


def _infer_bus_width_from_reg_name(reg_name: str) -> Optional[int]:

    if not reg_name:
        return None
    m = re.search(r"\[(\d+):(\d+)\]", reg_name)
    if not m:
        return None
    try:
        msb = int(m.group(1))
        lsb = int(m.group(2))
    except ValueError:
        return None
    return abs(msb - lsb) + 1


def _parse_last_float(pattern: str, text: str) -> Optional[float]:

    matches = list(re.finditer(pattern, text, re.IGNORECASE))
    if not matches:
        return None
    m = matches[-1]
    try:
        return float(m.group(1))
    except ValueError:
        return None


def _extract_block_fields(block: str) -> Optional[RawTimingViolation]:

    slack = _parse_float_from_line(r"Slack[^\d\-+]*([\-+]?\d+\.\d+)", block)
    if slack is None:
        return None

    vt_match = re.search(r"Path\s+Type\s*:\s*(Setup|Hold)", block, re.IGNORECASE)
    if vt_match:
        vt = vt_match.group(1).strip().lower()
        violation_type = "setup" if vt.startswith("setup") else "hold"
    else:
        violation_type = "setup"

    clock_match = re.search(r"Path\s+Group\s*:\s*([^\s\(\r\n]+)", block, re.IGNORECASE)
    clock = clock_match.group(1).strip() if clock_match else ""

    period = _parse_float_from_line(r"period\s*=\s*([\-+]?\d+\.\d+)", block)
    if period is None:
        period = _parse_float_from_line(r"Requirement[^\d\-+]*([\-+]?\d+\.\d+)", block)
    period_ns = period if period is not None else 0.0

    required_time = _parse_last_float(r"required\s+time[^\d\-+]*([\-+]?\d+\.\d+)", block)
    arrival_time = _parse_last_float(r"arrival\s+time[^\d\-+]*([\-+]?\d+\.\d+)", block)

    if required_time is None:
        required_time = _parse_float_from_line(r"Requirement[^\d\-+]*([\-+]?\d+\.\d+)", block)
    if arrival_time is None:
        arrival_time = _parse_float_from_line(r"Arrival\s+Time[^\d\-+]*([\-+]?\d+\.\d+)", block)

    required_time_ns = required_time if required_time is not None else 0.0
    arrival_time_ns = arrival_time if arrival_time is not None else 0.0

    src_match = re.search(r"Source\s*:\s*([^\s\(\r\n]+)", block, re.IGNORECASE)
    dst_match = re.search(r"(Destination|Dest)\s*:\s*([^\s\(\r\n]+)", block, re.IGNORECASE)
    start_reg = src_match.group(1).strip() if src_match else ""
    end_reg = dst_match.group(2).strip() if dst_match else ""

    logic_levels = _parse_int_from_line(r"Logic\s+Levels\s*:\s*(\d+)", block)
    comb_delay = _parse_float_from_line(r"logic\s+([\-+]?\d+\.\d+)\s*ns", block)
    net_delay = _parse_float_from_line(r"route\s+([\-+]?\d+\.\d+)\s*ns", block)

    start_hierarchy = _extract_hierarchy_from_reg_name(start_reg)
    end_hierarchy = _extract_hierarchy_from_reg_name(end_reg)

    hierarchy_depth = None
    if start_hierarchy is not None and end_hierarchy is not None:
        if start_hierarchy == end_hierarchy:
            hierarchy_depth = 0
        else:
            s_parts = start_hierarchy.split("/")
            e_parts = end_hierarchy.split("/")

            L = 0
            for a, b in zip(s_parts, e_parts):
                if a == b:
                    L += 1
                else:
                    break

            hierarchy_depth = (len(s_parts) - L) + (len(e_parts) - L)

    lines = block.splitlines()
    datapath_lines: List[str] = []
    in_datapath = False

    start_reg_core = start_reg.split("/")[0] if start_reg else ""
    end_reg_core = end_reg.split("/")[0] if end_reg else ""

    for line in lines:
        if not in_datapath:
            if start_reg_core and (start_reg_core + "/Q") in line:
                in_datapath = True
                datapath_lines.append(line)
            continue

        datapath_lines.append(line)

        if end_reg_core and (end_reg_core + "/D") in line:
            break

    if not datapath_lines:
        datapath_lines = lines

    max_fanout_signal = None
    max_fanout_count: Optional[int] = None

    for line in datapath_lines:
        if "(fo=" not in line:
            continue

        m = re.search(r"\(fo=(\d+)", line)
        if not m:
            continue
        try:
            fo = int(m.group(1))
        except ValueError:
            continue

        parts = line.strip().split()
        if not parts:
            continue
        sig = parts[-1]

        if re.search(r"clk", sig, re.IGNORECASE):
            continue

        if max_fanout_count is None or fo > max_fanout_count:
            max_fanout_count = fo
            max_fanout_signal = sig

    launch_clock = None
    capture_clock = None

    src_line_match = re.search(
        r"Source\s*:\s*.*?clocked\s+by\s+([^\s\)\r\n]+)", block, re.IGNORECASE
    )
    if src_line_match:
        launch_clock = src_line_match.group(1).strip()

    dst_line_match = re.search(
        r"(Destination|Dest)\s*:\s*.*?clocked\s+by\s+([^\s\)\r\n]+)",
        block,
        re.IGNORECASE,
    )
    if dst_line_match:
        capture_clock = dst_line_match.group(2).strip()

    if not launch_clock:
        launch_clock = clock
    if not capture_clock:
        capture_clock = clock

    cdc_signal_width = _infer_bus_width_from_reg_name(start_reg)

    raw = RawTimingViolation(
        clock=clock,
        period_ns=period_ns,
        violation_type=violation_type,
        slack_ns=slack,
        required_time_ns=required_time_ns,
        arrival_time_ns=arrival_time_ns,
        launch_clock=launch_clock,
        capture_clock=capture_clock,
        start_reg=start_reg,
        start_module=None,
        end_reg=end_reg,
        end_module=None,
        logic_levels=logic_levels,
        cell_count=None,
        combinational_delay_ns=comb_delay,
        net_delay_ns=net_delay,
        max_fanout_signal=max_fanout_signal,
        max_fanout_count=max_fanout_count,
        start_hierarchy=start_hierarchy,
        end_hierarchy=end_hierarchy,
        hierarchy_depth=hierarchy_depth,
        cdc_signal_width=cdc_signal_width,
        path=[],
        cdc_hint=None,
    )
    return raw


def parse_vivado_report_to_raw_violations(
    report_text: str,
    *,
    only_violations: bool = True,
    max_paths: Optional[int] = None,
) -> List[RawTimingViolation]:

    raw_text = report_text
    blocks: List[str] = []

    matches = list(_SLACK_BLOCK_RE.finditer(raw_text))
    if not matches:
        return []

    for i, m in enumerate(matches):
        start = m.start()
        if i + 1 < len(matches):
            end = matches[i + 1].start()
        else:
            end = len(raw_text)
        block = raw_text[start:end]
        blocks.append(block)

    violations: List[RawTimingViolation] = []

    for block in blocks:
        raw = _extract_block_fields(block)
        if raw is None:
            continue

        if only_violations and raw.slack_ns >= 0:
            continue

        violations.append(raw)

        if max_paths is not None and len(violations) >= max_paths:
            break

    return violations
