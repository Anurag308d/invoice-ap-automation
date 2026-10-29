"""Documentation stays in sync with code and config, and every reference in it resolves."""
from __future__ import annotations

import re

import pytest

from invoice_ap.cli import doc_blocks
from invoice_ap.common.docsync import block_in_sync
from invoice_ap.common.paths import DOCS_DIR, PACKAGE_DIR, REPO_ROOT

STAGE1_DOCS = ("architecture.md", "schema.md", "data_dictionary.md", "business_rules.md",
               "data_generation.md", "evaluation_plan.md", "requirements_traceability.md",
               "assumptions_and_decisions.md")
MARKDOWN = [REPO_ROOT / "README.md", *sorted(DOCS_DIR.glob("*.md"))]


def test_stage1_documents_exist():
    for name in STAGE1_DOCS:
        assert (DOCS_DIR / name).stat().st_size > 1000, name


@pytest.mark.parametrize("path,name,content", doc_blocks(),
                         ids=[f"{p.name}:{n}" for p, n, _ in doc_blocks()])
def test_generated_blocks_are_current(path, name, content):
    assert block_in_sync(path, name, content), f"{path.name} [{name}] is stale: python -m invoice_ap docs"


@pytest.mark.parametrize("doc", MARKDOWN, ids=[p.name for p in MARKDOWN])
def test_relative_links_resolve(doc):
    for target in re.findall(r"\]\(([^)#\s]+)(?:#[^)]*)?\)", doc.read_text(encoding="utf-8")):
        if target.startswith(("http://", "https://", "mailto:")):
            continue
        assert (doc.parent / target).exists(), f"{doc.name} links to missing {target}"


def test_every_referenced_adr_is_defined():
    adr_text = (DOCS_DIR / "assumptions_and_decisions.md").read_text(encoding="utf-8")
    defined = set(re.findall(r"\*\*(ADR-\d{3})\b", adr_text))
    sources = [*MARKDOWN, *PACKAGE_DIR.rglob("*.py"), REPO_ROOT / "config" / "ap_policy.toml"]
    referenced = {m for p in sources for m in re.findall(r"ADR-\d{3}", p.read_text(encoding="utf-8"))}
    assert referenced <= defined, f"undefined ADRs: {sorted(referenced - defined)}"


def test_every_rule_id_in_the_policy_is_documented():
    rules_doc = (DOCS_DIR / "business_rules.md").read_text(encoding="utf-8")
    policy = (REPO_ROOT / "config" / "ap_policy.toml").read_text(encoding="utf-8")
    for rule in sorted(set(re.findall(r'"([A-Z]{2,4}(?:-[A-Z]{2,4})?-\d{2})"', policy))):
        assert rule in rules_doc, f"rule {rule} is in the policy but not in business_rules.md"
