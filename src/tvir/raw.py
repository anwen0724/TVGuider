from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import List, Optional, Literal, Dict, Any


RawNodeKind = Literal["reg", "op", "wire"]


@dataclass
class RawPathNode:
    kind: RawNodeKind
    name: str
    op_type: Optional[str] = None
    module: Optional[str] = None


@dataclass
class RawTimingViolation:
    clock: str
    period_ns: float
    violation_type: str
    slack_ns: float
    required_time_ns: float
    arrival_time_ns: float

    launch_clock: str
    capture_clock: str

    start_reg: str
    start_module: Optional[str] = None
    end_reg: str = ""
    end_module: Optional[str] = None

    logic_levels: Optional[int] = None
    cell_count: Optional[int] = None
    combinational_delay_ns: Optional[float] = None
    net_delay_ns: Optional[float] = None

    max_fanout_signal: Optional[str] = None
    max_fanout_count: Optional[int] = None

    start_hierarchy: Optional[str] = None
    end_hierarchy: Optional[str] = None
    hierarchy_depth: Optional[int] = None

    cdc_signal_width: Optional[int] = None

    path: List[RawPathNode] = field(default_factory=list)

    cdc_hint: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:

        d = asdict(self)
        return d

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "RawTimingViolation":

        path_nodes = []
        for nd in d.get("path", []):
            if not isinstance(nd, dict):
                continue
            path_nodes.append(
                RawPathNode(
                    kind=nd.get("kind", "wire"),
                    name=nd.get("name", ""),
                    op_type=nd.get("op_type"),
                    module=nd.get("module"),
                )
            )

        return RawTimingViolation(
            clock=d.get("clock", ""),
            period_ns=float(d.get("period_ns", 0.0)),
            violation_type=d.get("violation_type", "setup"),
            slack_ns=float(d.get("slack_ns", 0.0)),
            required_time_ns=float(d.get("required_time_ns", 0.0)),
            arrival_time_ns=float(d.get("arrival_time_ns", 0.0)),
            launch_clock=d.get("launch_clock", d.get("clock", "")),
            capture_clock=d.get("capture_clock", d.get("clock", "")),
            start_reg=d.get("start_reg", ""),
            start_module=d.get("start_module"),
            end_reg=d.get("end_reg", ""),
            end_module=d.get("end_module"),
            logic_levels=d.get("logic_levels"),
            cell_count=d.get("cell_count"),
            combinational_delay_ns=d.get("combinational_delay_ns"),
            net_delay_ns=d.get("net_delay_ns"),
            max_fanout_signal=d.get("max_fanout_signal"),
            max_fanout_count=d.get("max_fanout_count"),
            start_hierarchy=d.get("start_hierarchy"),
            end_hierarchy=d.get("end_hierarchy"),
            hierarchy_depth=d.get("hierarchy_depth"),
            cdc_signal_width=d.get("cdc_signal_width"),
            path=path_nodes,
            cdc_hint=d.get("cdc_hint"),
        )
