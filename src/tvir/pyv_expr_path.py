from __future__ import annotations

from typing import List, Optional, Tuple, Dict
import tempfile
import os
import re

from pyverilog.vparser.parser import parse
from pyverilog.vparser import ast as vast

__all__ = ["extract_ops_for_reg_from_text", "get_signal_width_from_text"]


OP_CLASS_MAP = {
    vast.Plus: "add",
    vast.Minus: "sub",
    vast.Times: "mul",
    vast.Divide: "div",
    vast.Mod: "mod",
    vast.Sll: "shift",
    vast.Srl: "shift",
    vast.Sla: "shift",
    vast.Sra: "shift",
    vast.And: "bit_and",
    vast.Or: "bit_or",
    vast.Xor: "xor",
    vast.Xnor: "xnor",
    vast.Land: "logic_and",
    vast.Lor: "logic_or",
    vast.Eq: "cmp_eq",
    vast.NotEq: "cmp_ne",
    vast.Cond: "mux",
}


def _normalize_signal_core_name(signal_name: str) -> str:

    if not signal_name:
        return ""

    core = signal_name.strip()

    core = re.sub(r"/[A-Z]+$", "", core)

    if "/" in core:
        core = core.split("/")[-1]

    core = re.sub(r"\[[^\]]+\]$", "", core)

    if core.endswith("_reg"):
        core = core[: -len("_reg")]

    return core


def _eval_int(node: object) -> Optional[int]:

    if node is None:
        return None

    if isinstance(node, vast.IntConst):
        raw = (node.value or "").strip().replace("_", "")
        if not raw:
            return None

        if "'" not in raw:
            try:
                return int(raw, 10)
            except Exception:
                return None

        parts = raw.split("'", 1)
        if len(parts) != 2:
            return None
        right = parts[1].strip()

        if not right:
            return None

        signed = False
        if right[0] in ("s", "S"):
            signed = True
            right = right[1:].strip()
            if not right:
                return None

        base_ch = right[0].lower()
        digits = right[1:].strip()
        if not digits:
            return None

        if any(c in digits.lower() for c in ("x", "z", "?")):
            return None

        base_map = {"b": 2, "o": 8, "d": 10, "h": 16}
        if base_ch not in base_map:
            return None

        try:
            val = int(digits, base_map[base_ch])

            return -val if signed and raw.strip().startswith("-") else val
        except Exception:
            return None

    return None


def _width_to_int(width_node: object) -> Optional[int]:

    if width_node is None:
        return 1

    if isinstance(width_node, vast.Width):
        msb = _eval_int(getattr(width_node, "msb", None))
        lsb = _eval_int(getattr(width_node, "lsb", None))
        if msb is None or lsb is None:
            return None
        try:
            return abs(int(msb) - int(lsb)) + 1
        except Exception:
            return None

    return None


def _iter_module_defs(ast_root: vast.Node) -> List[vast.ModuleDef]:
    modules: List[vast.ModuleDef] = []

    def visit(node: vast.Node):
        if isinstance(node, vast.ModuleDef):
            modules.append(node)

            return
        for c in node.children():
            visit(c)

    visit(ast_root)
    return modules


def _build_decl_width_index(ast_root: vast.Node) -> Dict[str, Dict[str, int]]:

    index: Dict[str, Dict[str, int]] = {}

    modules = _iter_module_defs(ast_root)
    for m in modules:
        mname = getattr(m, "name", None)
        if not mname:
            continue

        decl_map: Dict[str, int] = {}

        items = getattr(m, "items", None) or []

        for it in items:
            if not isinstance(it, vast.Decl):
                continue

            decl_list = getattr(it, "list", None) or []
            for d in decl_list:
                if isinstance(d, (vast.Input, vast.Output, vast.Inout, vast.Wire, vast.Reg)):
                    name = getattr(d, "name", None)
                    if not name:
                        continue
                    w = _width_to_int(getattr(d, "width", None))
                    if w is None:
                        continue
                    decl_map[str(name)] = int(w)

        index[str(mname)] = decl_map

    return index


def get_signal_width_from_text(
    verilog_text: str,
    *,
    module_name: Optional[str],
    signal_name: str,
) -> Optional[int]:

    verilog_text = verilog_text or ""
    if not verilog_text.strip():
        return None

    sig_core = _normalize_signal_core_name(signal_name)
    if not sig_core:
        return None

    ast_root = _parse_verilog_text(verilog_text)
    idx = _build_decl_width_index(ast_root)

    if module_name:
        m = idx.get(str(module_name))
        if not m:
            return None
        return m.get(sig_core)

    hits: List[int] = []
    for _mname, mdecls in idx.items():
        if sig_core in mdecls:
            hits.append(mdecls[sig_core])

    if len(hits) == 1:
        return hits[0]

    return None


def _extract_ops_from_expr(expr_node, start_reg_core: Optional[str]) -> Tuple[List[str], bool]:

    ops: List[str] = []
    used_start = False

    def visit(node):
        nonlocal used_start

        if isinstance(node, vast.Identifier) and start_reg_core:
            if node.name == start_reg_core:
                used_start = True

        for child in node.children():
            visit(child)

        for cls, tag in OP_CLASS_MAP.items():
            if isinstance(node, cls):
                ops.append(tag)
                break

    visit(expr_node)
    return ops, used_start


def _get_lhs_name(lhs: vast.Node) -> Optional[str]:

    if isinstance(lhs, vast.Identifier):
        return lhs.name
    if isinstance(lhs, vast.Pointer) and isinstance(lhs.var, vast.Identifier):
        return lhs.var.name
    if isinstance(lhs, vast.Lvalue):
        return _get_lhs_name(lhs.var)
    return None


def _find_end_reg_assignments(
    ast_root: vast.Node, end_reg_core: str
) -> List[vast.NonblockingSubstitution]:

    assigns: List[vast.NonblockingSubstitution] = []

    def visit(node: vast.Node):
        for c in node.children():
            if isinstance(c, vast.NonblockingSubstitution):
                target_name = _get_lhs_name(c.left)
                if target_name == end_reg_core:
                    assigns.append(c)
            visit(c)

    visit(ast_root)
    return assigns


def _find_module_of_assign(ast_root, target_assign) -> Optional[str]:

    module_name_found: Optional[str] = None

    def visit(node, current_module: Optional[str] = None):
        nonlocal module_name_found

        if module_name_found is not None:
            return

        if isinstance(node, vast.ModuleDef):
            current_module = node.name

        for c in node.children():
            if c is target_assign:
                module_name_found = current_module
                return
            visit(c, current_module)

    visit(ast_root, None)
    return module_name_found


def _parse_verilog_text(verilog_text: str) -> vast.Source:

    if not verilog_text.strip():
        raise ValueError("verilog_text is empty")

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".v", delete=False) as f:
            f.write(verilog_text)
            tmp_path = f.name

        ast, _directives = parse([tmp_path])
        return ast
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass


def _extract_rhs_text(lines: List[str], lineno: int) -> str:

    if lineno is None or lineno <= 0 or lineno > len(lines):
        return ""

    i = lineno - 1
    buf: List[str] = []

    while i < len(lines):
        line = lines[i].rstrip("\n")
        buf.append(line)
        if ";" in line:
            break
        i += 1

    return "\n".join(buf)


def extract_ops_for_reg_from_text(
    verilog_text: str,
    *,
    start_reg_core: str,
    end_reg_core: str,
) -> Tuple[List[str], Optional[int], Optional[str], Optional[str]]:

    verilog_text = verilog_text or ""
    if not verilog_text.strip():
        return [], None, None, None

    ast_root = _parse_verilog_text(verilog_text)

    assigns = _find_end_reg_assignments(ast_root, end_reg_core)
    if not assigns:
        return [], None, None, None

    lines = verilog_text.splitlines()

    picked_assign = None
    picked_ops: List[str] = []
    picked_lineno: Optional[int] = None

    fallback_assign = None
    fallback_ops: List[str] = []
    fallback_lineno: Optional[int] = None

    for nb in assigns:
        rhs = nb.right

        if isinstance(rhs, vast.Rvalue):
            expr_node = rhs.var
        else:
            expr_node = rhs

        ops, used_start = _extract_ops_from_expr(expr_node, start_reg_core=start_reg_core)

        if used_start and picked_assign is None:
            picked_ops = ops
            picked_assign = nb

            coord = getattr(expr_node, "coord", None) or getattr(nb, "coord", None)
            lineno = getattr(coord, "lineno", None) if coord is not None else None
            picked_lineno = lineno

            break

        if (not used_start) and not fallback_assign and ops:
            fallback_ops = ops
            fallback_assign = nb
            coord = getattr(expr_node, "coord", None) or getattr(nb, "coord", None)
            lineno = getattr(coord, "lineno", None) if coord is not None else None
            fallback_lineno = lineno

    if picked_assign is None and fallback_assign is not None:
        picked_assign = fallback_assign
        picked_ops = fallback_ops
        picked_lineno = fallback_lineno

    if picked_assign is None:
        return [], None, None, None

    module_name = _find_module_of_assign(ast_root, picked_assign)

    if picked_lineno is None:
        if picked_ops:
            return picked_ops, None, None, module_name
        return [], None, None, module_name

    rhs_text = _extract_rhs_text(lines, picked_lineno)
    return picked_ops, picked_lineno, rhs_text, module_name
