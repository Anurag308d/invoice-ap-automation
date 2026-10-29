"""No-leakage boundary, static half (runtime sandbox test arrives with the engine in Stage 3).

The engine may import only the standard library, invoice_ap.common, invoice_ap.spec and its own
modules, and those shared packages may not import generator or evaluation code either, so no
transitive path into generator internals or ground truth exists.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

from invoice_ap.common.paths import PACKAGE_DIR

ALLOWED_FOR = {
    "engine": {"common", "spec", "engine"},
    "common": {"common"},
    "spec": {"common", "spec"},
}
FORBIDDEN_TEXT_IN_ENGINE = ("ground_truth", "SCENARIO_", "EDGE_CASES", "intended_issue",
                            "CAPTURE_OVERLAYS", "catalogue", '"source"', "'source'")


def _modules(package: str) -> list[Path]:
    return sorted((PACKAGE_DIR / package).rglob("*.py"))


def _internal_imports(path: Path) -> set[str]:
    """Top-level invoice_ap sub-packages imported by a module (absolute or relative)."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    rel = path.relative_to(PACKAGE_DIR).parts
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = list(rel[:-1])[: len(rel) - node.level]
                names = [".".join(["invoice_ap", *base, node.module or ""]).rstrip(".")]
                if not node.module:
                    names = [".".join(["invoice_ap", *base, a.name]) for a in node.names]
            else:
                names = [node.module or ""]
        else:
            continue
        for name in names:
            parts = name.split(".")
            if parts[0] == "invoice_ap" and len(parts) > 1:
                found.add(parts[1])
            elif parts[0] not in sys.stdlib_module_names and parts[0] != "invoice_ap":
                found.add(f"third-party:{parts[0]}")
    return found


@pytest.mark.parametrize("package", sorted(ALLOWED_FOR))
def test_import_boundaries(package):
    for path in _modules(package):
        extra = _internal_imports(path) - ALLOWED_FOR[package]
        assert not extra, f"{path.relative_to(PACKAGE_DIR)} imports {sorted(extra)}"


def test_engine_source_never_names_evaluation_only_data():
    for path in _modules("engine"):
        text = path.read_text(encoding="utf-8")
        for needle in FORBIDDEN_TEXT_IN_ENGINE:
            if path.name == "__init__.py" and needle in ("ground_truth",):
                continue  # the package docstring states the rule itself
            assert needle not in text, f"{path.name} mentions {needle}"
