#!/usr/bin/env python3
"""check_loc.py — enforce this project's hard size limits. Vendored; do not edit.

Source lines = physical lines that are neither blank nor comment-only.
  * file      <= MAX_FILE source lines
  * function  <= MAX_FUNC source lines (excluding its docstring)

Usage: python3 tools/check_loc.py [paths...]     (default: src/)
Lists violations and exits non-zero if any limit is exceeded; used by tests/test_size.py.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

MAX_FILE = 250
MAX_FUNC = 20
ROOT = Path(__file__).resolve().parent.parent
DEFAULTS = ["src"]


def _is_code(line: str) -> bool:
    s = line.strip()
    return bool(s) and not s.startswith("#")


def _code_count(lines: list[str]) -> int:
    return sum(1 for ln in lines if _is_code(ln))


def _docstring_lines(node: ast.AST) -> set[int]:
    body = getattr(node, "body", [])
    first = body[0] if body else None
    if isinstance(first, ast.Expr) and isinstance(getattr(first, "value", None), ast.Constant) \
            and isinstance(first.value.value, str):
        return set(range(first.lineno, (first.end_lineno or first.lineno) + 1))
    return set()


def _func_loc(node: ast.AST, lines: list[str]) -> int:
    skip = _docstring_lines(node)
    span = range(node.body[0].lineno, (node.end_lineno or node.lineno) + 1)
    return sum(1 for i in span if i not in skip and _is_code(lines[i - 1]))


def _py_files(paths: list[Path]) -> list[Path]:
    out: list[Path] = []
    for p in paths:
        out += sorted(p.rglob("*.py")) if p.is_dir() else [p]
    return [f for f in out if f.suffix == ".py"]


def file_violations(f: Path) -> list[str]:
    lines = f.read_text().splitlines()
    rel = f.relative_to(ROOT)
    out = []
    if (n := _code_count(lines)) > MAX_FILE:
        out.append(f"{rel}: file has {n} code lines (> {MAX_FILE})")
    for node in ast.walk(ast.parse("\n".join(lines))):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if (fl := _func_loc(node, lines)) > MAX_FUNC:
                out.append(f"{rel}:{node.lineno} {node.name}() has {fl} code lines (> {MAX_FUNC})")
    return out


def find_violations(targets: list[str] | None = None) -> list[str]:
    paths = [ROOT / t for t in (targets or DEFAULTS)]
    out: list[str] = []
    for f in _py_files(paths):
        out += file_violations(f)
    return out


def main() -> int:
    violations = find_violations(sys.argv[1:] or None)
    for line in violations:
        print(line)
    print(f"{'FAIL' if violations else 'OK'}: {len(violations)} violation(s)")
    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
