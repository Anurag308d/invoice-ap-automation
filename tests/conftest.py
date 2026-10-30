"""Shared session fixtures: one generated dataset per scale, and one engine run over each."""
from __future__ import annotations

import pytest

from invoice_ap.common.policy import load_policy
from invoice_ap.engine import run_engine
from invoice_ap.evaluation.decisions import evaluate_decisions
from invoice_ap.evaluation.extraction import evaluate
from invoice_ap.generator.build import generate
from invoice_ap.quality.quick import load


@pytest.fixture(scope="session")
def builds(tmp_path_factory):
    """scale -> (BuildResult, tables as strings). Built once per test session."""
    out = {}
    for scale in ("starter", "full"):
        root = tmp_path_factory.mktemp(scale)
        result = generate(scale, out=root)
        out[scale] = (result, load(root))
    return out


@pytest.fixture(scope="session")
def engine_runs(builds):
    """scale -> (dataset root, engine summary, extraction evaluation, decision evaluation)."""
    out = {}
    for scale, (result, _) in builds.items():
        root = result.out
        summary = run_engine(root / "master", root / "inbox", root / "processed", load_policy())
        out[scale] = (root, summary, evaluate(root), evaluate_decisions(root, load_policy().as_of_date)[0])
    return out


@pytest.fixture(scope="session")
def complete_builds(tmp_path_factory):
    """scale -> dataset root of a complete `build` (generate, run, evaluate, validate, export, dashboard,
    manifest), exactly as `python -m invoice_ap build` makes it."""
    from invoice_ap.orchestrate import build
    out = {}
    for scale in ("starter", "full"):
        root = tmp_path_factory.mktemp(f"complete-{scale}")
        assert build(scale, 20261022, root, log=lambda *_: None)["ok"]
        out[scale] = root
    return out
