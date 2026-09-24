from __future__ import annotations

from typing import List, Optional, Dict, Any

from .model import TVIR, TVIRContext, TVIRDataflowNode
from .raw import RawTimingViolation, RawPathNode


OP_TYPE_TO_RTL_OP = {
    "add": "+",
    "sub": "-",
    "mul": "*",
    "div": "/",
    "mod": "%",
    "shift": "<< / >>",
    "bit_and": "&",
    "bit_or": "|",
    "xor": "^",
    "xnor": "~^",
    "logic_and": "&&",
    "logic_or": "||",
    "cmp_eq": "==",
    "cmp_ne": "!=",
    "mux": "?:",
}


class TVIRBuilder:
    def from_manual(
        self,
        *,
        clock: str,
        period_ns: float,
        violation_type: str,
        slack_ns: float,
        launch_clock: Optional[str],
        capture_clock: Optional[str],
        required_time_ns: float,
        arrival_time_ns: float,
        dataflow_nodes: List[Dict[str, Any]],
        rtl_snippet: List[str],
        cdc_hint: Optional[str] = None,
    ) -> TVIR:

        ctx = TVIRContext(
            clock=clock,
            period_ns=period_ns,
            violation_type=violation_type,
            slack_ns=slack_ns,
            launch_clock=launch_clock or clock,
            capture_clock=capture_clock or clock,
            required_time_ns=required_time_ns,
            arrival_time_ns=arrival_time_ns,
        )

        df_nodes: List[TVIRDataflowNode] = []
        for nd in dataflow_nodes:
            if not isinstance(nd, dict):
                continue
            df_nodes.append(
                TVIRDataflowNode(
                    role=nd.get("role", "signal"),
                    name=nd.get("name"),
                    op_type=nd.get("op_type"),
                    module=nd.get("module"),
                )
            )

        return TVIR(
            context=ctx,
            dataflow_path=df_nodes,
            rtl_snippet=rtl_snippet,
            cdc_hint=cdc_hint,
        )

    def from_raw_violation(
        self,
        raw: RawTimingViolation,
        rtl_snippet: list[str],
        cdc_hint: Optional[str] = None,
        *,
        op_types: Optional[list[str]] = None,
        assign_line_no: Optional[int] = None,
        rhs_text: Optional[str] = None,
        start_core: Optional[str] = None,
        end_core: Optional[str] = None,
    ) -> TVIR:

        context = TVIRContext(
            clock=raw.clock,
            period_ns=raw.period_ns,
            violation_type=raw.violation_type,
            slack_ns=raw.slack_ns,
            launch_clock=raw.launch_clock,
            capture_clock=raw.capture_clock,
            required_time_ns=raw.required_time_ns,
            arrival_time_ns=raw.arrival_time_ns,
        )

        path: list[TVIRDataflowNode] = []

        start_name = start_core or raw.start_reg
        end_name = end_core or raw.end_reg

        path.append(
            TVIRDataflowNode(
                role="start_reg",
                name=start_name,
                module=raw.start_module,
            )
        )

        if op_types:
            for ot in op_types:
                path.append(
                    TVIRDataflowNode(
                        role="op",
                        name=None,
                        op_type=ot,
                        module=raw.end_module,
                    )
                )
        else:
            for rnode in raw.path:
                if rnode.kind == "op":
                    path.append(
                        TVIRDataflowNode(
                            role="op",
                            name=None,
                            op_type=rnode.op_type,
                            module=rnode.module,
                        )
                    )
                elif rnode.kind == "wire":
                    path.append(
                        TVIRDataflowNode(
                            role="signal",
                            name=rnode.name,
                            module=rnode.module,
                        )
                    )

        path.append(
            TVIRDataflowNode(
                role="end_reg",
                name=end_name,
                module=raw.end_module,
            )
        )

        if cdc_hint is not None:
            final_cdc_hint = cdc_hint
        elif raw.cdc_hint is not None:
            final_cdc_hint = raw.cdc_hint
        else:
            if raw.launch_clock == raw.capture_clock:
                final_cdc_hint = "single_clock_no_cdc"
            else:
                final_cdc_hint = "cross_clock_unknown"

        def _contains_in_snippet(name: Optional[str]) -> bool:
            if not name:
                return False
            return any(name in line for line in rtl_snippet)

        rtl_start_core = start_core
        rtl_end_core = end_core

        start_found = _contains_in_snippet(rtl_start_core)
        end_found = _contains_in_snippet(rtl_end_core)

        reg_alignment = {
            "report_start_reg": raw.start_reg,
            "report_end_reg": raw.end_reg,
            "rtl_start_core": rtl_start_core,
            "rtl_end_core": rtl_end_core,
            "start_reg_found": start_found if rtl_start_core else None,
            "end_reg_found": end_found if rtl_end_core else None,
        }

        expr_src: Optional[str] = None

        if rhs_text:
            expr_src = rhs_text.strip()
        else:
            candidate_indices: list[int] = []
            if rtl_end_core:
                for idx, line in enumerate(rtl_snippet):
                    if (rtl_end_core in line) and ("<=" in line):
                        candidate_indices.append(idx)

            chosen_idx: Optional[int] = None

            if candidate_indices:
                if rtl_start_core:
                    for idx in candidate_indices:
                        window = rtl_snippet[idx]
                        if idx + 1 < len(rtl_snippet):
                            window += "\n" + rtl_snippet[idx + 1]
                        if rtl_start_core in window:
                            chosen_idx = idx
                            break

                if chosen_idx is None:
                    chosen_idx = candidate_indices[0]

            if chosen_idx is not None:
                lines: list[str] = []
                i = chosen_idx
                while i < len(rtl_snippet):
                    l = rtl_snippet[i].rstrip("\n")
                    lines.append(l)
                    if ";" in l:
                        break
                    i += 1

                expr_src = "\n".join(lines).strip()
            else:
                joined = "\n".join(rtl_snippet).strip()
                expr_src = joined if joined else None

        expr_alignment: list[Dict[str, Any]] = []
        if op_types:
            for ot in op_types:
                expr_alignment.append(
                    {
                        "op_type": ot,
                        "rtl_op": OP_TYPE_TO_RTL_OP.get(ot),
                        "match_expr": expr_src,
                    }
                )

        alignment_evidence: Dict[str, Any] = {
            "snippet_source": "always_block_by_reg",
            "reg_alignment": reg_alignment,
            "expr_alignment": expr_alignment,
        }

        path_metrics: Dict[str, Any] = {}
        if raw.logic_levels is not None:
            path_metrics["logic_levels"] = raw.logic_levels
        if raw.cell_count is not None:
            path_metrics["cell_count"] = raw.cell_count
        if raw.combinational_delay_ns is not None:
            path_metrics["combinational_delay_ns"] = raw.combinational_delay_ns
        if raw.net_delay_ns is not None:
            path_metrics["net_delay_ns"] = raw.net_delay_ns
        if not path_metrics:
            path_metrics = None

        fanout_info: Dict[str, Any] = {}
        if raw.max_fanout_signal is not None:
            fanout_info["max_fanout_signal"] = raw.max_fanout_signal
        if raw.max_fanout_count is not None:
            fanout_info["max_fanout_count"] = raw.max_fanout_count
        if not fanout_info:
            fanout_info = None

        start_hier = raw.start_hierarchy
        end_hier = raw.end_hierarchy

        if start_hier is None and raw.start_module:
            start_hier = raw.start_module
        if end_hier is None and raw.end_module:
            end_hier = raw.end_module

        if start_hier is not None and end_hier is not None:
            if "/" not in start_hier and "/" not in end_hier and start_hier != end_hier:
                start_hier = f"{end_hier}/{start_hier}"

        hierarchy_depth = None
        if start_hier is not None and end_hier is not None:
            if start_hier == end_hier:
                hierarchy_depth = 0
            else:
                s_parts = start_hier.split("/")
                e_parts = end_hier.split("/")

                L = 0
                for a, b in zip(s_parts, e_parts):
                    if a == b:
                        L += 1
                    else:
                        break
                hierarchy_depth = (len(s_parts) - L) + (len(e_parts) - L)

        hierarchy_info = None
        if start_hier is not None or end_hier is not None or hierarchy_depth is not None:
            h: Dict[str, Any] = {}
            if start_hier is not None:
                h["start_hierarchy"] = start_hier
            if end_hier is not None:
                h["end_hierarchy"] = end_hier
            if hierarchy_depth is not None:
                h["hierarchy_depth"] = hierarchy_depth
            if h:
                hierarchy_info = h

        cdc_info: Dict[str, Any] = {}

        if raw.launch_clock:
            cdc_info["source_clock"] = raw.launch_clock
        if raw.capture_clock:
            cdc_info["dest_clock"] = raw.capture_clock
        if raw.cdc_signal_width is not None:
            cdc_info["cdc_signal_width"] = raw.cdc_signal_width
        if not cdc_info:
            cdc_info = None

        tvir = TVIR(
            context=context,
            dataflow_path=path,
            rtl_snippet=rtl_snippet,
            cdc_hint=final_cdc_hint,
            alignment_evidence=alignment_evidence,
            path_metrics=path_metrics,
            fanout_info=fanout_info,
            hierarchy_info=hierarchy_info,
            cdc_info=cdc_info,
        )
        return tvir
