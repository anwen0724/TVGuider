from dataclasses import dataclass


@dataclass(frozen=True)
class RepairConstraints:
    design_context: str = ""
