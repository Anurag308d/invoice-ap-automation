"""Stage-2 generator: exact counts, IDs, FKs, arithmetic, edge cases, boundary exactness, the
as-of limit, no accidental duplicates, closures after activity, isolation of injections, the
oracle-vs-intent assertion, and determinism (same seed, PYTHONHASHSEED independence)."""
from __future__ import annotations

import dataclasses
import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict
from decimal import Decimal as D

import pytest

from invoice_ap.common import ids
from invoice_ap.common.paths import REPO_ROOT
from invoice_ap.common.policy import load_policy
from invoice_ap.generator import oracle as oracle_mod
from invoice_ap.generator.build import generate
from invoice_ap.generator.oracle import OracleMismatch, label
from invoice_ap.generator.tables import normalize_invoice_number
from invoice_ap.quality.quick import load
from invoice_ap.spec import BY_NAME

EXPECTED = {"full": (300, 1500, 2200, 1800, 2000), "starter": (30, 150, 220, 180, 200)}


@pytest.fixture(scope="session")
def builds(tmp_path_factory):
    out = {}
    for scale in ("starter", "full"):
        root = tmp_path_factory.mktemp(scale)
        result = generate(scale, out=root)
        out[scale] = (result, load(root))
    return out


@pytest.fixture(params=["starter", "full"])
def build(request, builds):
    return builds[request.param]


def _gt(t):
    return {r["invoice_id"]: r for r in t["ground_truth"]}


def test_exact_volumes(build):
    result, t = build
    got = tuple(len(t[n]) for n in ("vendor", "purchase_order", "purchase_order_line", "goods_receipt", "invoice"))
    assert got == EXPECTED[result.alloc.scale]
    assert all(1 <= int(p["line_count"]) <= 8 for p in t["purchase_order"])


def test_mix_matches_the_allocation(build):
    result, t = build
    gt = t["ground_truth"]
    assert Counter(r["scenario_category"] for r in gt) == Counter(result.alloc.categories)
    assert Counter(r["scenario_code"] for r in gt) == Counter({k: v for k, v in result.alloc.subscenarios.items() if v})
    if result.alloc.scale == "full":
        cats = Counter(r["scenario_category"] for r in gt)
        assert (cats["CLEAN"], cats["CAPTURE_REVIEW"]) == (1350, 10)


def test_ids_follow_the_conventions_and_embed_their_parents(build):
    _, t = build
    for name, rows in t.items():
        for f in BY_NAME[name].fields:
            if f.type == "id" and f.pattern:
                rx = re.compile(f.pattern)
                assert all(rx.match(r[f.name]) for r in rows if r[f.name]), f"{name}.{f.name}"
    seq = {m["doc_id"]: int(m["intake_seq"]) for m in t["intake_manifest"]}
    for inv in t["invoice"]:
        assert ids.vendor_of_invoice(inv["invoice_id"]) == inv["vendor_id"]
        assert inv["invoice_id"] == ids.invoice_id(inv["vendor_id"], seq[inv["doc_id"]])


def test_self_checks_pass_and_the_baseline_is_clean(build):
    result, _ = build
    assert result.baseline_report["status"] == "pass"
    assert result.baseline_report["violations"] == 0 and result.baseline_report["labelled"] == 0
    assert result.report["status"] == "pass" and result.report["violations"] == 0
    checks = {c["check"]: c for c in result.report["checks"]}
    assert checks["foreign keys (every declared FK)"]["violations"] == 0


def test_totals_recompute_from_lines_except_labelled_defects(build):
    _, t = build
    gt = _gt(t)
    lines = defaultdict(list)
    for l in t["invoice_line"]:
        lines[l["invoice_id"]].append(l)
    for inv in t["invoice"]:
        net = sum(D(l["line_net_amount"]) for l in lines[inv["invoice_id"]])
        tax = sum(D(l["tax_amount"]) for l in lines[inv["invoice_id"]])
        same = D(inv["header_gross_amount"]) == net + tax
        original = gt[inv["invoice_id"]]["expected_duplicate_of"]
        codes = {gt[inv["invoice_id"]]["scenario_code"], gt[original]["scenario_code"] if original else ""}
        assert same or "ARITH-HEADER-TOTAL" in codes, inv["invoice_id"]


def test_edge_cases_are_present(build):
    result, t = build
    ec = Counter(e for r in t["ground_truth"] for e in r["edge_case_ids"].split("|") if e)
    floor = 10 if result.alloc.scale == "full" else 1
    assert all(ec[f"EC-0{i}"] >= floor for i in range(1, 9)), ec


def test_boundaries_are_exact(build):
    _, t = build
    gt, po_lines = _gt(t), {l["po_line_id"]: l for l in t["purchase_order_line"]}
    grn_cum = defaultdict(D)
    for g in t["goods_receipt_line"]:
        grn_cum[g["po_line_id"]] += D(g["received_qty"])
    seen = Counter()
    for l in t["invoice_line"]:
        code = gt[l["invoice_id"]]["scenario_code"]
        if l["line_number"] != "1" or gt[l["invoice_id"]]["expected_duplicate_of"]:
            continue
        pol = po_lines.get(l["po_line_id"]) if l["po_line_id"] else None
        if pol is None:
            continue
        price, po_price = D(l["unit_price"]), D(pol["unit_price"])
        ordered, billed = D(pol["ordered_qty"]), D(l["quantity"])
        step = D(1).scaleb(-len(pol["ordered_qty"].partition(".")[2]))
        if code == "C-PRICE-AT-TOL":
            assert price == po_price * D("1.02") and (price - po_price) * 100 / po_price == 2
        elif code == "C-PRICE-INSIDE":
            assert price == po_price * D("1.02") - D("0.01")
        elif code == "PV-BOUNDARY-OUT":
            assert price == po_price * D("1.02") + D("0.01")
        elif code == "C-QTY-AT-TOL":
            assert billed == grn_cum[pol["po_line_id"]] == ordered * D("1.05")
        elif code == "QM-BOUNDARY-OUT":
            assert billed == grn_cum[pol["po_line_id"]] == ordered * D("1.05") + step
        else:
            continue
        seen[code] += 1
    assert set(seen) == {"C-PRICE-AT-TOL", "C-PRICE-INSIDE", "PV-BOUNDARY-OUT", "C-QTY-AT-TOL", "QM-BOUNDARY-OUT"}


def test_no_completed_event_after_the_as_of_date(build):
    _, t = build
    limit = load_policy().as_of_date.isoformat()
    for name, col in (("vendor_status_history", "recorded_at"), ("vendor_status_history", "effective_date"),
                      ("goods_receipt", "posted_at"), ("goods_receipt", "received_date"), ("erp_event", "event_at"),
                      ("intake_manifest", "received_at"), ("purchase_order", "po_date"), ("invoice", "invoice_date")):
        assert max(r[col][:10] for r in t[name]) <= limit, (name, col)


def test_only_labelled_duplicates_collide(build):
    _, t = build
    gt, seq = _gt(t), {m["doc_id"]: int(m["intake_seq"]) for m in t["intake_manifest"]}
    first, collisions = {}, []
    for inv in sorted(t["invoice"], key=lambda i: seq[i["doc_id"]]):
        keys = [(inv["vendor_id"], normalize_invoice_number(inv["vendor_invoice_number"])),
                (inv["vendor_id"], inv["invoice_date"], inv["header_gross_amount"], inv["po_id"])]
        hits = {first[k] for k in keys if k in first}
        if hits:
            collisions.append(inv["invoice_id"])
            assert gt[inv["invoice_id"]]["scenario_category"] == "DUPLICATE"
            assert gt[inv["invoice_id"]]["expected_duplicate_of"] in hits
        for k in keys:
            first.setdefault(k, inv["invoice_id"])
    assert len(collisions) == sum(1 for r in t["ground_truth"] if r["scenario_category"] == "DUPLICATE")


def test_true_negatives_differ_where_dup03_looks(build):
    _, t = build
    gt = _gt(t)
    by_code = defaultdict(list)
    for inv in t["invoice"]:
        by_code[gt[inv["invoice_id"]]["scenario_code"]].append(inv)
    pairs = defaultdict(list)
    for inv in by_code["C-PARTIAL-BILLING"]:
        pairs[inv["po_id"]].append(inv)
    for a, b in pairs.values():
        assert a["invoice_date"] != b["invoice_date"] and a["header_gross_amount"] != b["header_gross_amount"]
    same_day = defaultdict(list)
    for inv in by_code["C-TN-SAME-DAY"]:
        same_day[(inv["vendor_id"], inv["invoice_date"], inv["header_gross_amount"])].append(inv["po_id"])
    assert all(len(set(v)) == 2 for v in same_day.values()) and same_day
    series = defaultdict(set)
    for inv in by_code["C-NPO-RECURRING"]:
        series[(inv["vendor_id"], inv["header_gross_amount"])].add(inv["invoice_date"])
    assert all(len(d) >= 2 for d in series.values())


def test_closures_and_blocks_follow_all_other_activity(build):
    _, t = build
    gt = _gt(t)
    changes = {}
    for h in t["vendor_status_history"]:
        if h["effective_date"] >= "2026-01-01" and h["to_status"] in ("CLOSED", "BLOCKED"):
            changes[h["vendor_id"]] = h["effective_date"]
    assert changes
    for po in t["purchase_order"]:
        if po["vendor_id"] in changes:
            assert po["po_date"] < changes[po["vendor_id"]]
    for g in t["goods_receipt"]:
        if g["vendor_id"] in changes:
            assert g["received_date"] < changes[g["vendor_id"]]
    for inv in t["invoice"]:
        if inv["vendor_id"] in changes and inv["invoice_date"] >= changes[inv["vendor_id"]]:
            r = gt[inv["invoice_id"]]
            orig = gt[r["expected_duplicate_of"]]["scenario_code"] if r["expected_duplicate_of"] else ""
            assert {r["scenario_code"], orig} & {"TV-CLOSED", "TV-BLOCKED"}, inv["invoice_id"]


def test_over_receipt_beyond_tolerance_only_in_labelled_scenarios(build):
    _, t = build
    gt = _gt(t)
    labelled_pos = {inv["po_id"] for inv in t["invoice"]
                    if gt[inv["invoice_id"]]["scenario_code"] in ("QM-EXCEEDS-PO-OVERRECEIPT", "QM-BOUNDARY-OUT")}
    ordered = {l["po_line_id"]: (D(l["ordered_qty"]), l["po_id"]) for l in t["purchase_order_line"]}
    over = {ordered[g["po_line_id"]][1] for g in t["goods_receipt_line"]
            if D(g["cumulative_received_qty"]) * 100 > ordered[g["po_line_id"]][0] * 105}
    assert over == labelled_pos


def test_oracle_labels_equal_intent_and_clean_means_no_issue(build):
    _, t = build
    blocking = {k for k, v in load_policy().raw["routing"]["types"].items() if v["blocking"]}
    for r in t["ground_truth"]:
        exp = {x for x in r["expected_issue_types"].split("|") if x in blocking}
        assert exp == {x for x in r["intended_issue_types"].split("|") if x}
        if r["scenario_category"] == "CLEAN":
            assert not exp and r["is_anomaly"] == "false"


def test_generation_fails_loudly_when_an_injection_misses_its_label(builds, monkeypatch):
    result, _ = builds["starter"]
    spec = oracle_mod.CODE["PV-OVER"]
    monkeypatch.setitem(oracle_mod.CODE, "PV-OVER", dataclasses.replace(spec, intended_issues=("TAX_CODE_MISMATCH",)))
    with pytest.raises(OracleMismatch, match="PV-OVER"):
        label(result.final, load_policy())


def test_injections_do_not_touch_unrelated_rows(builds):
    result, _ = builds["full"]
    base, final = result.baseline.tables, result.final.tables
    for name in ("purchase_order", "goods_receipt", "sku", "app_user", "tax_code", "payment_terms"):
        assert base[name] == final[name], name                      # identical master rows
    over_bills = [b for b in result.plan.bills if b.code in ("QM-EXCEEDS-PO-OVERRECEIPT", "QM-BOUNDARY-OUT")]
    over_pos = {b.po.po_id for b in over_bills}
    for r, s in zip(base["purchase_order_line"], final["purchase_order_line"]):
        diff = {k for k in r if r[k] != s[k]}
        assert not diff or (r["po_id"] in over_pos and all(k.startswith("snapshot_") for k in diff)), r["po_line_id"]
    changed = [r["vendor_id"] for r, s in zip(base["vendor"], final["vendor"]) if r != s]
    tv = {b.vendor.vendor_id for b in result.plan.bills if b.code in ("TV-CLOSED", "TV-BLOCKED")}
    assert set(changed) <= tv
    grn_changed = {r["grn_line_id"] for r, s in zip(base["goods_receipt_line"], final["goods_receipt_line"]) if r != s}
    assert {ids.parent_of_line(g) for g in grn_changed} <= {b.po.deliveries[0].grn_id for b in over_bills}
    fields = ("vendor_id", "invoice_date", "po_id", "header_net_amount", "header_tax_amount", "header_gross_amount")
    b_docs = {d.key: d for d in result.baseline.docs}
    for d in result.final.docs:
        if d.kind == "bill" and d.code.startswith("C-"):
            assert all(d.invoice[f] == b_docs[d.key].invoice[f] for f in fields), d.key


def _hashes(root):
    return {k: v["sha256"] for k, v in json.loads((root / "reports" / "source_manifest.json").read_text())["files"].items()}


def test_same_seed_gives_identical_files(tmp_path):
    generate("starter", out=tmp_path / "a")
    generate("starter", out=tmp_path / "b")
    assert _hashes(tmp_path / "a") == _hashes(tmp_path / "b")
    assert (tmp_path / "a" / "reports" / "source_manifest.json").read_bytes() == \
        (tmp_path / "b" / "reports" / "source_manifest.json").read_bytes()


def test_output_does_not_depend_on_pythonhashseed(tmp_path):
    for hs in ("1", "2"):
        env = dict(os.environ, PYTHONHASHSEED=hs)
        subprocess.run([sys.executable, "-m", "invoice_ap", "generate", "--scale", "starter", "--out",
                        str(tmp_path / hs)], cwd=REPO_ROOT, env=env, check=True, capture_output=True)
    assert _hashes(tmp_path / "1") == _hashes(tmp_path / "2")


def test_another_seed_changes_the_data_but_not_the_counts(tmp_path):
    a = generate("starter", out=tmp_path / "a")
    b = generate("starter", seed=7, out=tmp_path / "b")
    fixed = ("vendor", "purchase_order", "purchase_order_line", "goods_receipt", "invoice", "ground_truth")
    assert [len(a.final.tables[n]) for n in fixed] == [len(b.final.tables[n]) for n in fixed]
    mix = [Counter(r["scenario_code"] for r in x.final.tables["ground_truth"]) for x in (a, b)]
    assert mix[0] == mix[1]
    assert _hashes(tmp_path / "a")["source/invoice.csv"] != _hashes(tmp_path / "b")["source/invoice.csv"]


def test_inbox_never_hands_over_the_vendor(build):
    _, t = build
    assert "invoice_id" not in t["intake_manifest"][0]
    for m in t["intake_manifest"]:
        assert bool(m["sender_vendor_id"]) == (m["channel"] in ("PORTAL", "EDI"))
        assert m["channel"] != "SCAN" or m["sender_address"].startswith("MAILROOM-BATCH-")


def test_one_receipt_line_is_billed_by_two_invoice_lines(build):
    """A-26 at data level (the bridge rows themselves are written by the Stage-4 engine)."""
    _, t = build
    gt = _gt(t)
    grn_lines = Counter(g["po_line_id"] for g in t["goods_receipt_line"])
    billed = Counter(l["po_line_id"] for l in t["invoice_line"]
                     if l["po_line_id"] and not gt[l["invoice_id"]]["expected_duplicate_of"])
    shared = [pl for pl, n in billed.items() if n >= 2 and grn_lines[pl] == 1]
    assert len(shared) >= 1
