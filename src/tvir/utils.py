import re
from typing import Optional


def normalize_reg_core(report_name: str) -> str:

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
