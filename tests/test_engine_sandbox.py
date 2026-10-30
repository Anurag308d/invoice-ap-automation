"""Runtime no-leakage boundary: the blind run and the ID-blind run.

- Blind run: the engine runs on a copy that holds only master/ and inbox/; its output must be
  byte-identical to the normal run next to source/ and ground_truth/.
- ID-blind run: the channel's sender fields (sender_vendor_id, sender_address) are blanked in the
  copy's manifest; extraction, vendor resolution, invoice IDs and exceptions must be identical. Only
  the VEN-04 trace entries may differ (the check becomes "not applicable").
"""
from __future__ import annotations

import csv
import io
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from invoice_ap.common.paths import REPO_ROOT
from invoice_ap.common.policy import load_policy
from invoice_ap.engine import run_engine
from invoice_ap.engine.pipeline import OUTPUT_TABLES
from invoice_ap.spec.io import csv_bytes, read_table

OUTPUTS = [f"{t}.csv" for t in OUTPUT_TABLES] + ["decision_trace.jsonl"]


def _blind_copy(root: Path, dst: Path) -> Path:
    for layer in ("master", "inbox"):
        shutil.copytree(root / layer, dst / layer)
    assert sorted(p.name for p in dst.iterdir()) == ["inbox", "master"]
    return dst


def _run(ds: Path) -> dict[str, bytes]:
    run_engine(ds / "master", ds / "inbox", ds / "processed", load_policy())
    return {name: (ds / "processed" / name).read_bytes() for name in OUTPUTS}


@pytest.mark.parametrize("scale", ["starter", "full"])
def test_blind_run_is_byte_identical(engine_runs, tmp_path, scale):
    root, _, _, _ = engine_runs[scale]
    normal = {name: (root / "processed" / name).read_bytes() for name in OUTPUTS}
    assert _run(_blind_copy(root, tmp_path / "blind")) == normal


def _blank_senders(ds: Path) -> None:
    rows = read_table(ds / "inbox", "intake_manifest")
    assert any(r["sender_vendor_id"] for r in rows)
    for r in rows:
        r["sender_vendor_id"], r["sender_address"] = "", ""
    buf = io.StringIO(newline="")
    w = csv.DictWriter(buf, fieldnames=list(rows[0]), lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    (ds / "inbox" / "intake_manifest.csv").write_text(buf.getvalue(), encoding="utf-8")


@pytest.mark.parametrize("scale", ["starter", "full"])
def test_id_blind_run_gives_identical_decisions(engine_runs, tmp_path, scale):
    root, _, _, _ = engine_runs[scale]
    normal = {name: (root / "processed" / name).read_bytes() for name in OUTPUTS}
    ds = _blind_copy(root, tmp_path / "idblind")
    _blank_senders(ds)
    blind = _run(ds)
    for name in OUTPUTS[:-1]:
        assert blind[name] == normal[name], name
    def strip(data: bytes) -> list[dict]:
        return [t for t in map(json.loads, data.decode().splitlines()) if t["rule_id"] != "VEN-04"]
    assert strip(blind["decision_trace.jsonl"]) == strip(normal["decision_trace.jsonl"])
    checked = [json.loads(l) for l in normal["decision_trace.jsonl"].decode().splitlines() if '"VEN-04"' in l]
    assert any(t["inputs"]["checked"] for t in checked)                    # VEN-04 really ran on the normal copy


def test_sender_mismatch_is_raised_and_never_changes_the_vendor(engine_runs, tmp_path):
    root, _, _, _ = engine_runs["starter"]
    ds = _blind_copy(root, tmp_path / "mismatch")
    rows = read_table(ds / "inbox", "intake_manifest")
    portal = next(r for r in rows if r["channel"] == "PORTAL")
    other = next(r["sender_vendor_id"] for r in rows if r["sender_vendor_id"] not in ("", portal["sender_vendor_id"]))
    portal["sender_vendor_id"] = other
    (ds / "inbox" / "intake_manifest.csv").write_bytes(csv_bytes("intake_manifest", rows))
    _run(ds)
    cap = {c["doc_id"]: c for c in read_table(ds / "processed", "captured_invoice")}
    exc = read_table(ds / "processed", "ap_exception")
    hit = [e for e in exc if e["exception_type"] == "VENDOR_SENDER_MISMATCH"]
    assert len(hit) == 1 and hit[0]["invoice_id"] == cap[portal["doc_id"]]["invoice_id"]
    assert cap[portal["doc_id"]]["vendor_id"] != other                     # the vendor still comes from the document
    assert (hit[0]["assigned_role"], hit[0]["queue"], hit[0]["rule_id"]) == ("OPERATIONS_ANALYST", "AP_VALIDATION",
                                                                            "VEN-04")


def test_engine_output_is_deterministic_across_hash_seeds(engine_runs, tmp_path):
    root, _, _, _ = engine_runs["starter"]
    digests = []
    for seed in ("1", "2"):
        ds = _blind_copy(root, tmp_path / f"h{seed}")
        env = dict(os.environ, PYTHONHASHSEED=seed)
        subprocess.run([sys.executable, "-m", "invoice_ap", "run", "--data", str(ds)], cwd=REPO_ROOT, env=env,
                       check=True, capture_output=True)
        digests.append({name: (ds / "processed" / name).read_bytes() for name in OUTPUTS})
    assert digests[0] == digests[1]
