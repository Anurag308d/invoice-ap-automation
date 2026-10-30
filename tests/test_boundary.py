"""No-leakage boundary, static half (the runtime half is tests/test_engine_sandbox.py).

The engine may import only the standard library, invoice_ap.common, invoice_ap.spec and its own
modules, and those shared packages may not import generator or evaluation code either, so no
transitive path into generator internals or ground truth exists.
"""
from __future__ import annotations

import ast
import re
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
                            "CAPTURE_OVERLAYS", "catalogue", '"source"', "'source'",
                            "snapshot_",          # as-of snapshots are reporting only (S1-R1-02)
                            "vendor_of_invoice")  # never read a vendor out of an invoice_id (S1-R1-01)
SENDER_FIELDS = ("sender_vendor_id", "sender_address")
SENDER_CHECK_MODULE = "vendor_identity.py"  # the only engine module that may read them (VEN-04)


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


def test_engine_never_takes_the_vendor_from_the_sender_or_an_id():
    """S1-R1-01 static half: vendor identity comes only from the printed tax registration number
    (VEN-01). Sender fields may be read only by the VEN-04 cross-check module, and no engine code
    slices an invoice_id. The ID-blind sandbox run (test_engine_sandbox.py) is the runtime half."""
    for path in _modules("engine"):
        text = path.read_text(encoding="utf-8")
        if path.name != SENDER_CHECK_MODULE:
            for needle in SENDER_FIELDS:
                assert needle not in text, f"{path.name} reads {needle}"
        assert not re.search(r"invoice_id[\"']?\]?\s*\[\s*-?\d*\s*:", text), f"{path.name} slices invoice_id"
