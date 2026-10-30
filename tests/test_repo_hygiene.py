"""Repository conventions: stdlib-only runtime, determinism rules, LF checkouts, licence."""
from __future__ import annotations

import ast
import re
import sys
import tomllib

import pytest

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


def test_no_secrets_or_personal_data_in_tracked_files():
    """No credentials or keys anywhere, and every e-mail address in code, docs and generated data uses a
    reserved example domain (the only exception is the AI tool's commit-trailer address in docs)."""
    import re
    import subprocess
    try:
        files = subprocess.run(["git", "ls-files"], cwd=REPO_ROOT, capture_output=True, text=True,
                               check=True).stdout.split()
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("not a git checkout")
    secret = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----|AKIA[0-9A-Z]{16}|\bsk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{30,}")
    email = re.compile(r"[A-Za-z0-9._%+-]+@([A-Za-z0-9-]+\.)+[A-Za-z]{2,}")
    allowed = (".example", "example.com", "noreply@anthropic.com")
    for rel in files:
        path = REPO_ROOT / rel
        if path.suffix in (".png", ".pdf") or not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        assert not secret.search(text), f"{rel} contains something that looks like a secret"
        for m in email.finditer(text):
            assert m.group(0).endswith(allowed), f"{rel}: non-example e-mail address {m.group(0)}"
