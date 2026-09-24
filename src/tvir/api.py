from __future__ import annotations

from typing import List, Optional, Dict, Any

from .raw import RawTimingViolation
from .builder import TVIR, TVIRBuilder
from .report_parser_vivado import parse_vivado_report_to_raw_violations
from .rtl_snippet_extractor import (
    extract_rtl_snippet_for_path,
    extract_all_always_blocks,
)
from .pyv_expr_path import extract_ops_for_reg_from_text, get_signal_width_from_text
import re
from pathlib import Path
import json


def _normalize_reg_core(report_name: str) -> str:

    if not report_name:
        return ""

    core = report_name.strip()

    core = re.sub(r"/[A-Z]+$", "", core)

    if "/" in core:
        core = core.split("/")[-1]

    core = re.sub(r"\[[^\]]+\]$", "", core)

    if core.endswith("_reg"):
        core = core[: -len("_reg")]

    return core


def _build_reg_core_to_module_map(rtl_text: str, reg_cores: set[str]) -> Dict[str, str]:

    if not rtl_text or not reg_cores:
        return {}

    blocks = extract_all_always_blocks(rtl_text)
    core_to_module: Dict[str, str] = {}

    for blk in blocks:
        module_name = getattr(blk, "module_name", None)
        if not module_name:
            continue

        for name in blk.reg_names:
            if name in reg_cores and name not in core_to_module:
                core_to_module[name] = module_name

    return core_to_module


def build_tvir_from_raw(
    raw_violation: RawTimingViolation,
    rtl_snippet: List[str],
    cdc_hint: Optional[str] = None,
) -> TVIR:

    builder = TVIRBuilder()
    return builder.from_raw_violation(
        raw=raw_violation,
        rtl_snippet=rtl_snippet,
        cdc_hint=cdc_hint,
    )


def build_tvir_from_report_dict(
    report_dict: Dict[str, Any],
    rtl_snippet: List[str],
    cdc_hint: Optional[str] = None,
) -> TVIR:

    raw = RawTimingViolation.from_dict(report_dict)
    return build_tvir_from_raw(raw, rtl_snippet=rtl_snippet, cdc_hint=cdc_hint)


def build_tvir_dict_from_report_dict(
    report_dict: Dict[str, Any],
    rtl_snippet: List[str],
    cdc_hint: Optional[str] = None,
) -> Dict[str, Any]:

    tvir = build_tvir_from_report_dict(
        report_dict=report_dict,
        rtl_snippet=rtl_snippet,
        cdc_hint=cdc_hint,
    )
    return tvir.to_dict()


def build_tvirs_from_vivado_report_and_rtl(
    report_text: str,
    rtl_text: str,
    *,
    only_violations: bool = True,
    max_paths: Optional[int] = None,
) -> List[TVIR]:

    raw_list = parse_vivado_report_to_raw_violations(
        report_text,
        only_violations=only_violations,
        max_paths=max_paths,
    )
    if not raw_list:
        return []

    reg_cores: set[str] = set()
    for raw in raw_list:
        sc = _normalize_reg_core(raw.start_reg)
        ec = _normalize_reg_core(raw.end_reg)
        if sc:
            reg_cores.add(sc)
        if ec:
            reg_cores.add(ec)

    core_to_module = _build_reg_core_to_module_map(rtl_text, reg_cores)

    builder = TVIRBuilder()
    tvir_list: List[TVIR] = []

    builder = TVIRBuilder()
    tvir_list: List[TVIR] = []

    for raw in raw_list:
        snippet = extract_rtl_snippet_for_path(
            rtl_text=rtl_text,
            start_reg_report_name=raw.start_reg,
            end_reg_report_name=raw.end_reg,
        )

        start_core = _normalize_reg_core(raw.start_reg)
        end_core = _normalize_reg_core(raw.end_reg)

        if start_core and not raw.start_module:
            raw.start_module = core_to_module.get(start_core)

        op_types, assign_lineno, rhs_text, module_name = extract_ops_for_reg_from_text(
            verilog_text=rtl_text,
            start_reg_core=start_core,
            end_reg_core=end_core,
        )

        if module_name:
            raw.end_module = module_name
        elif end_core and not raw.end_module:
            raw.end_module = core_to_module.get(end_core)

        w1 = get_signal_width_from_text(
            rtl_text, module_name=raw.start_module, signal_name=raw.start_reg
        )
        w2 = get_signal_width_from_text(
            rtl_text, module_name=raw.end_module, signal_name=raw.end_reg
        )
        raw.cdc_signal_width = max([x for x in (w1, w2) if isinstance(x, int)], default=None)

        tvir = builder.from_raw_violation(
            raw=raw,
            rtl_snippet=snippet,
            cdc_hint=None,
            op_types=op_types,
            assign_line_no=assign_lineno,
            rhs_text=rhs_text,
            start_core=start_core,
            end_core=end_core,
        )

        tvir_list.append(tvir)

    return tvir_list


def build_tvir_dicts_from_vivado_report_and_rtl(
    report_text: str,
    rtl_text: str,
    *,
    only_violations: bool = True,
    max_paths: Optional[int] = None,
) -> List[Dict[str, Any]]:

    tvir_objs = build_tvirs_from_vivado_report_and_rtl(
        report_text=report_text,
        rtl_text=rtl_text,
        only_violations=only_violations,
        max_paths=max_paths,
    )
    return [t.to_dict() for t in tvir_objs]


def save_tvir_dicts_to_dir(
    tvir_dicts: List[Dict[str, Any]],
    output_dir: str,
    *,
    prefix: str = "tvir_",
    with_index: bool = True,
) -> List[str]:

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    written_paths: List[str] = []
    index_entries: List[Dict[str, Any]] = []

    for idx, tvir in enumerate(tvir_dicts, start=1):
        filename = f"{prefix}{idx:04d}.json"
        file_path = out_dir / filename

        with file_path.open("w", encoding="utf-8") as f:
            json.dump(tvir, f, ensure_ascii=False, indent=2)

        written_paths.append(str(file_path))

        ctx = tvir.get("context", {}) or {}
        dataflow = tvir.get("dataflow_path", []) or []

        start_reg_name = None
        end_reg_name = None
        for node in dataflow:
            role = node.get("role")
            if role == "start_reg" and start_reg_name is None:
                start_reg_name = node.get("name")
            elif role == "end_reg" and end_reg_name is None:
                end_reg_name = node.get("name")

        index_entries.append(
            {
                "file": filename,
                "violation_type": ctx.get("violation_type"),
                "slack_ns": ctx.get("slack_ns"),
                "launch_clock": ctx.get("launch_clock"),
                "capture_clock": ctx.get("capture_clock"),
                "start_reg": start_reg_name,
                "end_reg": end_reg_name,
            }
        )

    if with_index:
        index_data = {
            "tvir_files": index_entries,
        }
        index_path = out_dir / "index.json"
        with index_path.open("w", encoding="utf-8") as f:
            json.dump(index_data, f, ensure_ascii=False, indent=2)

    return written_paths


def build_and_save_tvirs_from_vivado_report_and_rtl(
    report_text: str,
    rtl_text: str,
    output_dir: str,
    *,
    only_violations: bool = True,
    max_paths: Optional[int] = None,
    prefix: str = "tvir_",
    with_index: bool = True,
) -> List[str]:

    tvir_dicts = build_tvir_dicts_from_vivado_report_and_rtl(
        report_text=report_text,
        rtl_text=rtl_text,
        only_violations=only_violations,
        max_paths=max_paths,
    )
    return save_tvir_dicts_to_dir(
        tvir_dicts=tvir_dicts,
        output_dir=output_dir,
        prefix=prefix,
        with_index=with_index,
    )
