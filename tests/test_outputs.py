"""Stage 5: validation suite, exports and SQL seed, manifest, reproducibility, queues, dashboard and
the committed data (parity with a fresh build)."""
from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
import sqlite3
import subprocess
from pathlib import Path

import pytest

from invoice_ap.common.paths import DEFAULT_DATA_DIR, REPO_ROOT
from invoice_ap.common.policy import load_policy
from invoice_ap.generator.allocation import allocate
from invoice_ap.orchestrate import repro
from invoice_ap.quality.suite import run_suite
from invoice_ap.report.manifest import EXCLUDED_FROM_COMMIT, NOT_LISTED, file_table, is_excluded
from invoice_ap.report.queue import ROLES, queue_items
from invoice_ap.spec import BY_NAME, TABLES
from invoice_ap.spec.io import csv_bytes, read_table

POLICY = load_policy()


@pytest.fixture(params=["starter", "full"])
def built(request, complete_builds):
    return request.param, complete_builds[request.param]


# ------------------------------------------------------------------ validation suite
def test_validation_suite_passes_on_every_table(built):
    scale, root = built
    report = json.loads((root / "reports" / "validation_summary.json").read_text())
    assert report["status"] == "pass" and report["violations"] == 0
    assert set(report["tables"]) == {t.name for t in TABLES}
    assert len(report["checks"]) >= 15


def _rewrite(ds: Path, table: str, fn) -> None:
    rows = read_table(ds / BY_NAME[table].layer, table)
    rows = fn(rows)
    (ds / BY_NAME[table].file).write_bytes(csv_bytes(table, rows))


@pytest.mark.parametrize("fault,check", [
    ("payment_for_blocked", "R34e"), ("dangling_event", "polymorphic"), ("over_allocation", "N:M bridge"),
    ("orphan_fk", "foreign keys"), ("bad_transition", "lifecycle")])
def test_validation_suite_catches_injected_faults(complete_builds, tmp_path, fault, check):
    ds = tmp_path / "ds"
    shutil.copytree(complete_builds["starter"], ds, ignore=shutil.ignore_patterns("exports", "documents"))
    if fault == "payment_for_blocked":
        dec = read_table(ds / "processed", "invoice_decision")
        blocked = next(d for d in dec if d["blocked"] == "true")
        _rewrite(ds, "payment", lambda rows: rows + [dict(rows[0], payment_id="PAY-2026-999999",
                                                          invoice_id=blocked["invoice_id"])])
    elif fault == "dangling_event":
        _rewrite(ds, "ap_event", lambda rows: rows + [dict(rows[-1], event_id="EVT-2026-999999",
                                                           entity_id="APR-2026-999999", entity_type="APPROVAL",
                                                           seq="1", from_status="", to_status="PENDING")])
    elif fault == "over_allocation":
        _rewrite(ds, "match_allocation", lambda rows: [dict(r, allocated_qty="999999") if i == 0 else r
                                                       for i, r in enumerate(rows)])
    elif fault == "orphan_fk":
        _rewrite(ds, "approval", lambda rows: [dict(r, approver_user_id="USR-9999") if i == 0 else r
                                               for i, r in enumerate(rows)])
    else:
        _rewrite(ds, "ap_event", lambda rows: [dict(r, to_status="PAID") if r["to_status"] == "CAPTURED" and i < 50
                                               else r for i, r in enumerate(rows)])
    report = run_suite(ds, POLICY, allocate("starter"))
    failed = [c["check"] for c in report["checks"] if c["violations"]]
    assert report["status"] == "fail" and any(check in c for c in failed), failed


# ------------------------------------------------------------------ exports and SQL
def test_sql_seed_loads_with_foreign_keys_and_keeps_labels_separate(built):
    scale, root = built
    seed = (root / "exports/sql/seed.sql").read_text()
    evaluation = (root / "exports/sql/evaluation_seed.sql").read_text()
    for name in ("ground_truth", "ground_truth_line", "invoice", "invoice_line"):
        assert f"CREATE TABLE {name} (" not in seed and f"CREATE TABLE {name} (" in evaluation
    con = sqlite3.connect(":memory:")
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript(seed)
    assert con.execute("PRAGMA foreign_key_check").fetchall() == []
    con.executescript(evaluation)
    assert con.execute("PRAGMA foreign_key_check").fetchall() == []
    assert con.execute("PRAGMA integrity_check").fetchone() == ("ok",)
    for t in TABLES:
        rows = len(read_table(root / t.layer, t.name))
        assert con.execute(f"SELECT COUNT(*) FROM {t.name}").fetchone()[0] == rows, t.name
    with pytest.raises(sqlite3.IntegrityError):                         # CHECK constraint on an enum
        con.execute("UPDATE invoice_decision SET status_as_of = 'MAYBE' WHERE rowid = 1")
    with pytest.raises(sqlite3.IntegrityError):                         # FK enforced
        con.execute("UPDATE payment SET vendor_id = 'VND-99999' WHERE rowid = 1")


def test_json_exports_cover_every_table(built):
    scale, root = built
    for t in TABLES:
        sub = "evaluation/" if t.layer in ("source", "ground_truth") else ""
        data = json.loads((root / f"exports/json/{sub}{t.name}.json").read_text())
        assert len(data) == len(read_table(root / t.layer, t.name)), t.name
        if data:
            assert list(sorted(data[0])) == sorted(f.name for f in t.fields)


# ------------------------------------------------------------------ manifest
def test_manifest_lists_every_file_with_checksums_and_provenance(built):
    scale, root = built
    m = json.loads((root / "reports/source_manifest.json").read_text())
    on_disk = file_table(root)
    assert {k: {x: v[x] for x in ("bytes", "sha256")} for k, v in m["files"].items()} == \
        {k: {x: v[x] for x in ("bytes", "sha256")} for k, v in on_disk.items()}
    for rel, entry in m["files"].items():
        if rel.endswith(".csv"):
            with open(root / rel, newline="", encoding="utf-8") as fh:
                assert entry["rows"] == sum(1 for _ in csv.reader(fh)) - 1
        assert entry["committed"] == (not is_excluded(scale, rel))
    for key in ("generator_version", "seed", "scale", "policy", "provenance", "command", "label_separation"):
        assert key in m
    assert m["provenance"]["external_sources"] == [] and "MIT" in m["provenance"]["licences"]["code"]
    assert m["command"]["this_scale"] == f"python -m invoice_ap build --scale {scale} --seed 20261022"


# ------------------------------------------------------------------ queues and dashboard
def test_every_actor_has_a_queue(complete_builds):
    root = complete_builds["full"]
    items = {r: queue_items(root, r, POLICY.as_of_date, POLICY.raw) for r in ROLES}
    assert all(items[r] for r in ROLES), {r: len(v) for r, v in items.items()}
    exc = {e["exception_id"]: e for e in read_table(root / "processed", "ap_exception")}
    for role, rows in items.items():
        assert [i["due"] or "9999" for i in rows] == sorted(i["due"] or "9999" for i in rows)
        for i in rows:
            if i["kind"] == "exception":
                assert exc[i["id"]]["assigned_role"] == role and exc[i["id"]]["status_as_of"] == "OPEN"


def test_dashboard_is_offline_and_deterministic(complete_builds):
    from invoice_ap.report.dashboard import build_dashboard
    root = complete_builds["starter"]
    html = (root / "reports/dashboard.html").read_text(encoding="utf-8")
    assert not re.search(r"https?://|<link |src=", html), "no external resources"
    for role in ROLES:
        assert role in html
    for part in ("Invoice explorer", "Validation suite", "Evaluation against ground truth", "past SLA at the snapshot"):
        assert part in html
    assert build_dashboard(root, POLICY).decode("utf-8") == html


def test_evaluation_markdown_is_readable_and_defines_its_kpis(complete_builds):
    text = (complete_builds["full"] / "reports/evaluation.md").read_text()
    assert "{'" not in text and "{\"" not in text
    definitions = text.split("## Definitions")[1]
    for term in ("STP rate", "Exception rate", "Payment-ready safety", "Value at risk held", "Cycle days",
                 "Per-invoice acceptance", "Blocked value released in error", "Open and past SLA"):
        assert f"| {term} |" in definitions
    assert "open and past SLA at the snapshot (no resolutions simulated)" in text
    assert "<= 5 business days" in text and "> 20 business days" in text


# ------------------------------------------------------------------ reproducibility and committed data
def test_repro_rebuilds_identically_and_another_seed_differs(complete_builds, tmp_path):
    root = tmp_path / "s"
    shutil.copytree(complete_builds["starter"], root)
    report = repro("starter", 20261022, root, log=lambda *_: None)
    assert report["pass"] and report["matches_this_build"]["identical"]
    assert report["same_seed"]["differing_files"] == []
    assert report["different_seed"]["core_row_counts_equal"] and report["different_seed"]["core_tables_differ"]
    assert (root / "reports/reproducibility.md").exists()


def test_gitignore_excludes_exactly_the_budgeted_files():
    lines = {l.strip() for l in (REPO_ROOT / ".gitignore").read_text().splitlines()}
    for scale, patterns in EXCLUDED_FROM_COMMIT.items():
        for p in patterns:
            assert f"data/{scale}/{p}" in lines
    assert "data/" not in lines


@pytest.mark.parametrize("scale", ["starter", "full"])
def test_committed_data_equals_a_fresh_build(complete_builds, scale):
    """A-54 parity: every committed file is byte-identical to a fresh build, and every file left out of
    the commit matches the checksum recorded in the committed manifest."""
    committed = DEFAULT_DATA_DIR / scale
    if not (committed / "reports/source_manifest.json").exists():
        pytest.skip("no committed data in this checkout")
    fresh = complete_builds[scale]
    manifest = json.loads((committed / "reports/source_manifest.json").read_text())
    assert (fresh / "reports/source_manifest.json").read_bytes() == (committed / "reports/source_manifest.json").read_bytes()
    for rel, entry in manifest["files"].items():
        data = (fresh / rel).read_bytes()
        assert hashlib.sha256(data).hexdigest() == entry["sha256"], rel
        if entry["committed"]:
            assert (committed / rel).read_bytes() == data, rel
    present = {p.relative_to(committed).as_posix() for p in committed.rglob("*") if p.is_file()}
    extra = present - set(manifest["files"]) - set(NOT_LISTED)
    assert all(is_excluded(scale, rel) for rel in extra), sorted(extra)[:5]      # only regenerable local files
    try:
        tracked = subprocess.run(["git", "ls-files", f"data/{scale}"], cwd=REPO_ROOT, capture_output=True, text=True,
                                 check=True).stdout.split()
    except (OSError, subprocess.CalledProcessError):
        return
    if tracked:
        assert not [t for t in tracked if is_excluded(scale, t[len(f"data/{scale}/"):])]
