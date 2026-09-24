from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import List, Optional, Dict, Any


@dataclass
class TVIRContext:
    clock: str
    period_ns: float
    violation_type: str
    slack_ns: float
    launch_clock: str
    capture_clock: str
    required_time_ns: float
    arrival_time_ns: float


@dataclass
class TVIRDataflowNode:
    role: str
    name: Optional[str] = None
    op_type: Optional[str] = None
    module: Optional[str] = None


@dataclass
class TVIR:
    context: TVIRContext
    dataflow_path: List[TVIRDataflowNode]
    rtl_snippet: List[str]
    path_metrics: Optional[Dict[str, Any]] = None
    fanout_info: Optional[Dict[str, Any]] = None
    hierarchy_info: Optional[Dict[str, Any]] = None
    cdc_info: Optional[Dict[str, Any]] = None
    cdc_hint: Optional[str] = None
    alignment_evidence: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:

        context_dict = asdict(self.context)

        df_nodes: List[Dict[str, Any]] = []
        for n in self.dataflow_path:
            node: Dict[str, Any] = {"role": n.role}
            if n.name is not None:
                node["name"] = n.name
            if n.op_type is not None:
                node["op_type"] = n.op_type
            if n.module is not None:
                node["module"] = n.module

            df_nodes.append(node)

        result: Dict[str, Any] = {
            "context": context_dict,
            "dataflow_path": df_nodes,
            "rtl_snippet": list(self.rtl_snippet),
        }

        if self.cdc_hint is not None:
            result["cdc_hint"] = self.cdc_hint
        if self.alignment_evidence is not None:
            result["alignment_evidence"] = self.alignment_evidence
        if self.path_metrics is not None:
            result["path_metrics"] = self.path_metrics
        if self.fanout_info is not None:
            result["fanout_info"] = self.fanout_info
        if self.hierarchy_info is not None:
            result["hierarchy_info"] = self.hierarchy_info
        if self.cdc_info is not None:
            result["cdc_info"] = self.cdc_info

        return result

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "TVIR":

        ctx = d.get("context", {})
        context = TVIRContext(
            clock=ctx.get("clock", ""),
            period_ns=ctx.get("period_ns", 0.0),
            violation_type=ctx.get("violation_type", "setup"),
            slack_ns=ctx.get("slack_ns", 0.0),
            launch_clock=ctx.get("launch_clock", ctx.get("clock", "")),
            capture_clock=ctx.get("capture_clock", ctx.get("clock", "")),
            required_time_ns=ctx.get("required_time_ns", 0.0),
            arrival_time_ns=ctx.get("arrival_time_ns", 0.0),
        )

        df_nodes: List[TVIRDataflowNode] = []
        for nd in d.get("dataflow_path", []):
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

        rtl_snippet = d.get("rtl_snippet") or []
        if isinstance(rtl_snippet, str):
            rtl_snippet = rtl_snippet.splitlines()
        elif not isinstance(rtl_snippet, list):
            rtl_snippet = [str(rtl_snippet)]

        return TVIR(
            context=context,
            dataflow_path=df_nodes,
            rtl_snippet=rtl_snippet,
            cdc_hint=d.get("cdc_hint"),
            alignment_evidence=d.get("alignment_evidence"),
            path_metrics=d.get("path_metrics"),
            fanout_info=d.get("fanout_info"),
            hierarchy_info=d.get("hierarchy_info"),
            cdc_info=d.get("cdc_info"),
        )
