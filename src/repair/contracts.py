from dataclasses import dataclass


@dataclass(frozen=True)
class RepairConstraints:
    allow_latency_increase: bool = False
    design_context: str = ""


class RepairOutputError(ValueError):
    pass


def validate_repair_output(
    output: dict, chunk_ids: set[str], constraints: RepairConstraints
) -> None:
    rtl = output.get("repaired_rtl")
    if not isinstance(rtl, str) or not rtl.strip() or "```" in rtl:
        raise RepairOutputError("repaired_rtl must contain complete RTL without markdown fences")
    summary = output.get("change_summary")
    if (
        not isinstance(summary, list)
        or not summary
        or any(not isinstance(s, str) or not s.strip() for s in summary)
    ):
        raise RepairOutputError("change_summary must be a nonempty list of strings")
    citations = output.get("knowledge_used")
    if (
        not isinstance(citations, list)
        or not citations
        or any(not isinstance(c, str) or c not in chunk_ids for c in citations)
    ):
        raise RepairOutputError("knowledge_used must reference retrieved chunk IDs")
    latency = output.get("latency_change_cycles")
    if type(latency) is not int or latency < 0:
        raise RepairOutputError("latency_change_cycles must be a nonnegative integer")
    if latency and not constraints.allow_latency_increase:
        raise RepairOutputError("Latency increase is not allowed")
