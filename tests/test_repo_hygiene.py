"""Repository conventions: stdlib-only runtime, determinism rules, LF checkouts, licence."""
from __future__ import annotations

import ast
import re
import sys
import tomllib

from invoice_ap.common.paths import PACKAGE_DIR, REPO_ROOT

SOURCES = sorted(PACKAGE_DIR.rglob("*.py"))
# Wall-clock reads and unseeded or libm-dependent randomness break reproducibility (ADR-015).
BANNED = {
    r"\bdatetime\.now\b": "wall clock", r"\bdate\.today\b": "wall clock",
    r"\btime\.time\b": "wall clock", r"\butcnow\b": "wall clock",
    r"\brandom\.(random|randint|randrange|choice|choices|shuffle|sample|seed)\(": "global RNG",
    r"\b(gauss|normalvariate|lognormvariate|expovariate)\b": "libm-dependent RNG",
    r"\bmath\.(exp|log|pow|sin|cos)\b": "libm-dependent float math",
    r"\buuid\b": "non-deterministic ids",
}


def test_runtime_uses_only_the_standard_library():
    for path in SOURCES:
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                roots = [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom) and not node.level:
                roots = [(node.module or "").split(".")[0]]
            else:
                continue
            for root in roots:
                assert root in sys.stdlib_module_names or root == "invoice_ap", f"{path.name}: {root}"


def test_no_nondeterministic_calls_in_package():
    for path in SOURCES:
        text = path.read_text(encoding="utf-8")
        for pattern, why in BANNED.items():
            assert not re.search(pattern, text), f"{path.relative_to(REPO_ROOT)}: {why} ({pattern})"


def test_pyproject_declares_no_runtime_dependencies():
    meta = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert meta["dependencies"] == []
    assert meta["requires-python"] == ">=3.11"


def test_gitattributes_forces_lf_for_text_and_data():
    text = (REPO_ROOT / ".gitattributes").read_text(encoding="utf-8")
    assert "* text=auto eol=lf" in text
    for ext in ("csv", "json", "jsonl", "sql", "md", "py", "toml", "txt", "edi", "html"):
        assert re.search(rf"^\*\.{ext}\s+text eol=lf$", text, re.M), ext


def test_licence_is_mit():
    assert (REPO_ROOT / "LICENSE").read_text(encoding="utf-8").startswith("MIT License")


def test_text_files_use_lf_line_endings():
    for path in [*SOURCES, *(REPO_ROOT / "docs").glob("*.md"), REPO_ROOT / "config" / "ap_policy.toml"]:
        assert b"\r\n" not in path.read_bytes(), path.name
