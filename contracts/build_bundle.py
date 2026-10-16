#!/usr/bin/env python3
"""
Bundle contracts/Solvent.py with the pure contracts/solventlib/* modules into
contracts/build/Solvent.bundled.py -- the ONE file the network receives
(sibling/package imports are not supported by contract validation).

The first line of the output MUST stay a bare `# { "Depends": ... }` comment
with nothing above it, so it is split off before the AST pass and re-prepended
afterwards (ast.unparse never re-emits comments).

Sibling imports of the form `from contracts.solventlib... import ...` are
removed from Solvent.py, and every import line is removed from the inlined
library modules: the bundle header declares all of them exactly once.

Usage:  python contracts/build_bundle.py
Output: contracts/build/Solvent.bundled.py
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTRACTS_DIR = ROOT / "contracts"
LIB_DIR = CONTRACTS_DIR / "solventlib"
CONTRACT_PATH = CONTRACTS_DIR / "Solvent.py"
OUT_PATH = CONTRACTS_DIR / "build" / "Solvent.bundled.py"

LIB_MODULES = ["accounting.py", "ssrf.py", "canonicalize.py", "judgment.py"]

BEGIN_MARKER = "# BEGIN SOLVENTLIB INLINE"
END_MARKER = "# END SOLVENTLIB INLINE"

# Documented Studio deploy-size ceiling observed across prior GenLayer
# projects (a PLATFORM/RPC payload ceiling, not GenVM's own contract limit).
MAX_BUNDLE_BYTES = 52224

_DOCSTRING_RE = re.compile(r'\s*("""|\'\'\').*?\1\s*', flags=re.DOTALL)
_IMPORT_RE = re.compile(r"^\s*(import\s|from\s)")


def _strip_module(source: str) -> str:
    """AST-drops the module docstring and every (possibly multi-line) import
    from a library module -- the bundle header provides them all once."""
    tree = ast.parse(source.replace("\r\n", "\n"))
    body = []
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        if (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            continue
        body.append(node)
    tree.body = body
    ast.fix_missing_locations(tree)
    return ast.unparse(tree)


class _DocstringStripper(ast.NodeTransformer):
    """Drops docstrings so the deployed bundle carries no prose."""

    def _strip(self, body: list) -> list:
        out = []
        for node in body:
            if (
                isinstance(node, ast.Expr)
                and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)
            ):
                continue
            out.append(node)
        return out or [ast.Pass()]

    def visit_Module(self, node):
        self.generic_visit(node)
        node.body = self._strip(node.body)
        return node

    def visit_ClassDef(self, node):
        self.generic_visit(node)
        node.body = self._strip(node.body)
        return node

    def visit_FunctionDef(self, node):
        self.generic_visit(node)
        node.body = self._strip(node.body)
        return node


def _minify(source: str) -> str:
    tree = ast.parse(source)
    tree = _DocstringStripper().visit(tree)
    ast.fix_missing_locations(tree)
    return ast.unparse(tree)


def build() -> Path:
    contract_source = CONTRACT_PATH.read_text(encoding="utf-8").replace("\r\n", "\n")
    if BEGIN_MARKER not in contract_source or END_MARKER not in contract_source:
        raise SystemExit(
            f"Solvent.py is missing the {BEGIN_MARKER}/{END_MARKER} markers"
        )

    before, rest = contract_source.split(BEGIN_MARKER, 1)
    _, after = rest.split(END_MARKER, 1)

    inlined = "\n\n".join(
        _strip_module((LIB_DIR / name).read_text(encoding="utf-8"))
        for name in LIB_MODULES
    )

    bundled = (
        before
        + BEGIN_MARKER
        + " -- inlined by contracts/build_bundle.py, do not hand-edit)\n"
        + inlined
        + "\n"
        + END_MARKER
        + after
    )

    first_line, _, remainder = bundled.partition("\n")
    if not first_line.strip().startswith('# { "Depends"'):
        raise SystemExit("first line of Solvent.py must be the bare Depends comment")

    bundled = first_line + "\n" + _minify(remainder) + "\n"

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(bundled, encoding="utf-8", newline="\n")

    size = len(bundled.encode("utf-8"))
    print(f"Wrote {OUT_PATH} ({size} bytes, {len(bundled.splitlines())} lines)")
    if size > MAX_BUNDLE_BYTES:
        print(
            f"WARNING: exceeds the documented {MAX_BUNDLE_BYTES}-byte Studio "
            f"ceiling by {size - MAX_BUNDLE_BYTES} bytes"
        )
    else:
        print(f"OK: {MAX_BUNDLE_BYTES - size} bytes under the {MAX_BUNDLE_BYTES}-byte ceiling")
    return OUT_PATH


if __name__ == "__main__":
    build()
