"""Stage-4 decision engine: agreement with ground truth, the event log, the N:M bridge, payment
safety, REV rulings (VEN-04 precedence, retired GST12), unit fixtures for every exception type absent
from the data, the time-travel sandbox and a rule-mutation probe (the evaluation is not circular)."""
from __future__ import annotations

import dataclasses
import copy
import json
import shutil
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal as D
from pathlib import Path

import pytest

from invoice_ap.common.calendar import BusinessCalendar
from invoice_ap.common.policy import load_policy
from invoice_ap.engine import run_engine
from invoice_ap.engine.explain import explain
from invoice_ap.engine.pipeline import OUTPUT_TABLES
from invoice_ap.evaluation.decisions import evaluate_decisions
from invoice_ap.quality.quick import load, validate
from invoice_ap.spec import BY_NAME
from invoice_ap.spec.io import csv_bytes, read_table

POLICY = load_policy()
ABSENT = ["VENDOR_NOT_FOUND", "VENDOR_SENDER_MISMATCH", "PO_NOT_FOUND", "INVOICE_DATE_IN_FUTURE", "TAX_CODE_INVALID",
          "PO_LINE_UNMATCHED", "VENDOR_NOT_PAYABLE", "PAYMENT_DUE_DATE_PASSED"]


# ------------------------------------------------------------------ agreement on the generated data
@pytest.mark.parametrize("scale", ["starter", "full"])
def test_engine_agrees_with_ground_truth_on_every_invoice(engine_runs, scale):
    _, _, _, r = engine_runs[scale]
    n = r["invoices"]
    for item, value in {**r["agreement"]}.items():
        assert value.startswith(f"{n}/{n}"), (item, value)
    for item, value in r["line_agreement"].items():
        assert value.endswith("(100.00%)"), (item, value)
    assert all(m["fp"] == 0 and m["fn"] == 0 for m in r["per_type_invoice"].values())
    assert all(m["fp"] == 0 and m["fn"] == 0 for m in r["per_type_line"].values())
    assert r["primary_issue_off_diagonal"] == 0
    assert r["acceptance"]["fail"] == 0 and r["acceptance"]["pass"] == n
    assert r["payments"]["blocked_or_unapproved_with_payment"] == 0
    assert r["duplicates"]["correct_pairs"] == r["duplicates"]["expected_pairs"] == r["duplicates"]["detected_pairs"]
    assert r["duplicates"]["true_negative_false_positives"] == 0
    assert r["value_at_risk"]["blocked_invoices_released_in_error_value_inr"] == "0.00"


def test_absent_types_are_reported_as_not_present(engine_runs):
    _, _, _, r = engine_runs["full"]
    assert r["not_present_types"] == ABSENT
    for t in ABSENT:
        assert r["per_type_invoice"][t] == {"tp": 0, "fp": 0, "fn": 0, "precision": "not present",
                                            "recall": "not present", "f1": "not present"}


def test_event_log_and_processed_tables_validate(engine_runs):
    root, _, _, _ = engine_runs["full"]
    report = validate(load(root), POLICY)
    assert report["status"] == "pass", [c for c in report["checks"] if c["violations"]]
    events = read_table(root / "processed", "ap_event")
    assert [e["event_id"] for e in events] == sorted(e["event_id"] for e in events)
    assert all(a["event_at"] <= b["event_at"] for a, b in zip(events, events[1:]))      # append-only, time order


def test_bridge_is_exercised_in_both_directions(engine_runs):
    """A-26: one GRN line allocated to several invoice lines (partial billing) and one invoice line
    allocated to several GRN lines (consolidated billing); never more than received, never a future GRN."""
    root, _, _, _ = engine_runs["full"]
    alloc = read_table(root / "processed", "match_allocation")
    per_grn, per_line = Counter(a["grn_line_id"] for a in alloc), Counter(a["invoice_line_id"] for a in alloc)
    assert max(per_grn.values()) >= 2 and max(per_line.values()) >= 2
    received = {g["grn_line_id"]: (D(g["received_qty"]), g["po_line_id"], g["grn_id"])
                for g in read_table(root / "master", "goods_receipt_line")}
    posted = {g["grn_id"]: g["posted_at"] for g in read_table(root / "master", "goods_receipt")}
    used = defaultdict(D)
    match = {m["invoice_line_id"]: m for m in read_table(root / "processed", "match_result")}
    cap = {c["invoice_id"]: c for c in read_table(root / "processed", "captured_invoice")}
    manifest = {m["doc_id"]: m for m in read_table(root / "inbox", "intake_manifest")}
    for a in alloc:
        qty, po_line, grn = received[a["grn_line_id"]]
        used[a["grn_line_id"]] += D(a["allocated_qty"])
        m = match[a["invoice_line_id"]]
        assert m["po_line_id"] == po_line
        assert posted[grn] <= manifest[cap[m["invoice_id"]]["doc_id"]]["received_at"]
    assert all(used[g] <= received[g][0] for g in used)


def test_payments_only_for_unblocked_fully_approved_invoices(engine_runs):
    root, _, _, _ = engine_runs["full"]
    exc = defaultdict(list)
    for e in read_table(root / "processed", "ap_exception"):
        exc[e["invoice_id"]].append(e)
    apr = defaultdict(list)
    for a in read_table(root / "processed", "approval"):
        apr[a["invoice_id"]].append(a)
    dec = {d["invoice_id"]: d for d in read_table(root / "processed", "invoice_decision")}
    cal = BusinessCalendar.from_policy(POLICY.raw)
    for p in read_table(root / "processed", "payment"):
        iid = p["invoice_id"]
        assert not any(e["blocking"] == "true" and e["status_as_of"] == "OPEN" for e in exc[iid])
        assert apr[iid] and all(a["status_as_of"] == "APPROVED" for a in apr[iid])
        assert [a["level"] for a in sorted(apr[iid], key=lambda a: int(a["sequence"]))] == dec[iid]["approval_levels"].split("|")
        assert (p["payment_method"] == "RTGS") == (D(p["amount"]) >= D("200000.00"))
        ready = date.fromisoformat(p["created_at"][:10])
        assert date.fromisoformat(p["scheduled_date"]) >= cal.next_business_day(ready)
    for iid, d in dec.items():
        if d["blocked"] == "true":
            assert not apr[iid] or d["status_as_of"] == "ON_HOLD" and d["primary_issue"] == "VENDOR_NOT_PAYABLE"


def test_explain_reconstructs_one_invoice(engine_runs):
    root, _, _, _ = engine_runs["starter"]
    held = next(d for d in read_table(root / "processed", "invoice_decision") if d["primary_issue"] == "PRICE_VARIANCE")
    text = explain(root / "processed", held["invoice_id"])
    for part in ("STATUS ON_HOLD", "PRICE_VARIANCE [MAT-02]", "Line match:", "Event log:", "CAPTURED -> ON_HOLD",
                 "Decision trace:", "BUSINESS_REQUESTER"):
        assert part in text


# ------------------------------------------------------------------ fixtures on a temp copy
def _copy(root: Path, dst: Path) -> Path:
    for layer in ("master", "inbox"):
        shutil.copytree(root / layer, dst / layer)
    return dst


def _run(ds: Path, policy=POLICY) -> dict:
    run_engine(ds / "master", ds / "inbox", ds / "processed", policy)
    out = {t: read_table(ds / "processed", t) for t in OUTPUT_TABLES}
    out["by_doc"] = {c["doc_id"]: c["invoice_id"] for c in out["captured_invoice"]}
    return out


def _decision(out: dict, doc_id: str) -> tuple[dict, list[dict]]:
    iid = out["by_doc"][doc_id]
    return (next(d for d in out["invoice_decision"] if d["invoice_id"] == iid),
            [e for e in out["ap_exception"] if e["invoice_id"] == iid])


def _clean_portal_docs(root: Path) -> list[dict]:
    """Clean PO-backed invoices delivered as portal v1 JSON, in intake order."""
    gt = {g["doc_id"]: g for g in read_table(root / "ground_truth", "ground_truth")}
    out = []
    for m in read_table(root / "inbox", "intake_manifest"):
        g = gt[m["doc_id"]]
        if m["channel"] == "PORTAL" and g["expected_primary_issue"] == "NONE" and g["is_po_backed"] == "true":
            if json.loads((root / "inbox" / m["file_path"]).read_text()).get("schema"):
                out.append(dict(m, band=g["expected_approval_band"], status=g["expected_final_status"]))
    return out


def _edit(ds: Path, m: dict, fn) -> None:
    path = ds / "inbox" / m["file_path"]
    obj = json.loads(path.read_text(encoding="utf-8"))
    fn(obj)
    path.write_text(json.dumps(obj, indent=2), encoding="utf-8")


def _write(ds: Path, table: str, rows: list[dict]) -> None:
    (ds / BY_NAME[table].layer / f"{table}.csv").write_bytes(csv_bytes(table, rows))


def _route(t: str) -> tuple:
    r = POLICY.raw["routing"]["types"][t]
    return r["role"], r["queue"], r["raised_by"], "true" if r["blocking"] else "false"


DOC_FIXTURES = {
    "VENDOR_NOT_FOUND": lambda o: o["supplier"].update(tax_registration_id="TRN-000000001"),
    "PO_NOT_FOUND": lambda o: o["invoice"].update(po_number="PO-2026-999999"),
    "INVOICE_DATE_IN_FUTURE": lambda o: o["invoice"].update(
        date=(date.fromisoformat(o["invoice"]["date"]) + timedelta(days=40)).isoformat()),
    "PO_LINE_UNMATCHED": lambda o: o["lines"][0].update(po_line_no="9"),
    "TAX_CODE_INVALID": lambda o: o["lines"][0].update(tax_code="GST12"),       # REV ruling 3: retired in 2025
}


@pytest.mark.parametrize("issue", sorted(DOC_FIXTURES))
def test_document_fixtures_for_types_absent_from_the_data(engine_runs, tmp_path, issue):
    root, _, _, _ = engine_runs["starter"]
    ds = _copy(root, tmp_path / "ds")
    target = _clean_portal_docs(root)[0]
    _edit(ds, target, DOC_FIXTURES[issue])
    out = _run(ds)
    dec, excs = _decision(out, target["doc_id"])
    hit = [e for e in excs if e["exception_type"] == issue]
    assert hit, (issue, dec["issue_types"])
    e = hit[0]
    assert (e["assigned_role"], e["queue"], e["rule_id"], e["blocking"]) == _route(issue)
    assert dec["blocked"] == "true" and dec["status_as_of"] == "ON_HOLD" and dec["payment_ready"] == "false"
    if issue == "VENDOR_NOT_FOUND":
        assert dec["invoice_id"].startswith("INV-VND-00000-") and dec["primary_issue"] == issue
    if issue in ("PO_NOT_FOUND",):
        assert dec["match_status"] == "NOT_EVALUATED"
    if issue == "TAX_CODE_INVALID":
        assert e["invoice_line_id"] and dec["match_status"] == "TAX_MISMATCH"


def test_vendor_not_payable_on_the_ready_date(engine_runs, tmp_path):
    """PAY-03: the vendor is blocked after the invoice was approved for matching but before the L1
    approval completes; the invoice must go ON_HOLD with no payment."""
    root, _, _, _ = engine_runs["starter"]
    ds = _copy(root, tmp_path / "ds")
    target = next(m for m in _clean_portal_docs(root) if m["band"] == "P2" and m["status"] in ("PAID", "PAYMENT_READY"))
    cal = BusinessCalendar.from_policy(POLICY.raw)
    received = date.fromisoformat(target["received_at"][:10])
    blocked_on = cal.add_business_days(received, 1)
    vendor = json.loads((ds / "inbox" / target["file_path"]).read_text())["supplier"]["tax_registration_id"]
    vendor_id = next(v["vendor_id"] for v in read_table(ds / "master", "vendor") if v["tax_registration_id"] == vendor)
    hist = read_table(ds / "master", "vendor_status_history")
    mine = [h for h in hist if h["vendor_id"] == vendor_id]
    assert mine[-1]["to_status"] == "ACTIVE" and mine[-1]["effective_date"] < blocked_on.isoformat()
    hist.append({"vsh_id": "VSH-999999", "vendor_id": vendor_id, "seq": str(len(mine) + 1), "from_status": "ACTIVE",
                 "to_status": "BLOCKED", "effective_date": blocked_on.isoformat(),
                 "recorded_at": f"{blocked_on.isoformat()}T09:00:00+05:30", "actor_role": "SYSTEM_ADMINISTRATOR",
                 "actor_id": "USR-0002", "reason_code": "KYC_DOCUMENTS_EXPIRED"})
    _write(ds, "vendor_status_history", hist)
    dec, excs = _decision(_run(ds), target["doc_id"])
    assert dec["primary_issue"] == "VENDOR_NOT_PAYABLE" and dec["status_as_of"] == "ON_HOLD"
    assert dec["payment_ready"] == "false" and dec["approval_band"] == "P2"
    assert [(e["exception_type"], e["assigned_role"], e["queue"]) for e in excs] == [
        ("VENDOR_NOT_PAYABLE", "SYSTEM_ADMINISTRATOR", "VENDOR_MASTER")]


def test_payment_due_date_passed_is_a_warning(engine_runs, tmp_path):
    """PAY-06: with zero-day terms the due date has passed when the invoice becomes ready; it is paid
    the next business day after ready and flagged, but not blocked."""
    root, _, _, _ = engine_runs["starter"]
    ds = _copy(root, tmp_path / "ds")
    terms = read_table(ds / "master", "payment_terms")
    for t in terms:
        t["net_days"] = "0"
    _write(ds, "payment_terms", terms)
    out = _run(ds)
    cal = BusinessCalendar.from_policy(POLICY.raw)
    warned = [e for e in out["ap_exception"] if e["exception_type"] == "PAYMENT_DUE_DATE_PASSED"]
    assert warned
    pay = {p["invoice_id"]: p for p in out["payment"]}
    dec = {d["invoice_id"]: d for d in out["invoice_decision"]}
    for e in warned:
        p, d = pay[e["invoice_id"]], dec[e["invoice_id"]]
        assert (e["assigned_role"], e["queue"], e["blocking"]) == ("OPERATIONS_ANALYST", "PAYMENT_WATCH", "false")
        assert p["due_date_passed"] == "true"
        assert p["scheduled_date"] == cal.next_business_day(date.fromisoformat(p["created_at"][:10])).isoformat()
        assert d["status_as_of"] in ("PAID", "PAYMENT_READY") and d["blocked"] == "false"
        assert d["primary_issue"] == "NONE" and "PAYMENT_DUE_DATE_PASSED" in d["issue_types"]


def test_sender_mismatch_on_a_duplicate_reports_the_duplicate(engine_runs, tmp_path):
    """REV ruling 2: VEN-04 runs after the duplicate gates, so a duplicate with a forged sender is
    reported as DUPLICATE_* and VEN-04 is not evaluated for it."""
    root, _, _, _ = engine_runs["full"]
    ds = _copy(root, tmp_path / "ds")
    gt = {g["doc_id"]: g for g in read_table(root / "ground_truth", "ground_truth")}
    rows = read_table(ds / "inbox", "intake_manifest")
    dup = next(r for r in rows if gt[r["doc_id"]]["expected_duplicate_of"] and r["channel"] in ("PORTAL", "EDI"))
    clean = next(r for r in rows if gt[r["doc_id"]]["expected_primary_issue"] == "NONE" and r["channel"] == "PORTAL"
                 and r["sender_vendor_id"] != dup["sender_vendor_id"])
    forged = next(r["sender_vendor_id"] for r in rows if r["sender_vendor_id"] not in ("", dup["sender_vendor_id"],
                                                                                      clean["sender_vendor_id"]))
    dup["sender_vendor_id"] = clean["sender_vendor_id"] = forged
    _write(ds, "intake_manifest", rows)
    out = _run(ds)
    d, excs = _decision(out, dup["doc_id"])
    assert d["primary_issue"].startswith("DUPLICATE_") and "VENDOR_SENDER_MISMATCH" not in d["issue_types"]
    assert [e["exception_type"] for e in excs] == [d["primary_issue"]]
    c, cexcs = _decision(out, clean["doc_id"])                            # the control does raise VEN-04
    assert c["primary_issue"] == "VENDOR_SENDER_MISMATCH" and c["status_as_of"] == "ON_HOLD"


# ------------------------------------------------------------------ time travel (ADR-038)
def _blank_snapshots(ds: Path) -> None:
    for table in ("vendor", "purchase_order", "purchase_order_line", "goods_receipt"):
        rows = read_table(ds / "master", table)
        for r in rows:
            for k in r:
                if k.startswith("snapshot_"):
                    r[k] = "0" if k.endswith("_qty") else "ACTIVE" if table == "vendor" else "POSTED" \
                        if table == "goods_receipt" else "ISSUED"
        _write(ds, table, rows)


def test_snapshots_and_post_as_of_rows_never_change_a_decision(engine_runs, tmp_path):
    root, _, _, _ = engine_runs["full"]
    normal = {t: (root / "processed" / f"{t}.csv").read_bytes() for t in OUTPUT_TABLES}
    ds = _copy(root, tmp_path / "ds")
    _blank_snapshots(ds)
    hist = read_table(ds / "master", "vendor_status_history")       # a status change after the as-of date
    v = hist[0]["vendor_id"]
    seq = max(int(h["seq"]) for h in hist if h["vendor_id"] == v) + 1
    hist.append(dict(hist[0], vsh_id="VSH-999998", seq=str(seq), from_status="ACTIVE", to_status="BLOCKED",
                     effective_date="2026-10-23", recorded_at="2026-10-23T09:00:00+05:30",
                     reason_code="KYC_DOCUMENTS_EXPIRED"))
    _write(ds, "vendor_status_history", hist)
    grns = read_table(ds / "master", "goods_receipt")               # a receipt posted after the as-of date
    lines = read_table(ds / "master", "goods_receipt_line")
    g, l = dict(grns[0]), dict(next(x for x in lines if x["grn_id"] == grns[0]["grn_id"]))
    g.update(grn_id="GRN-2026-999999", received_date="2026-10-23", posted_at="2026-10-23T11:00:00+05:30",
             line_count="1")
    l.update(grn_line_id="GRNL-GRN-2026-999999-01", grn_id="GRN-2026-999999", line_number="1")
    _write(ds, "goods_receipt", grns + [g])
    _write(ds, "goods_receipt_line", lines + [l])
    _run(ds)
    for t in OUTPUT_TABLES:
        assert (ds / "processed" / f"{t}.csv").read_bytes() == normal[t], t


PROCESSING_TIME = ("match_status", "duplicate_of_invoice_id", "decided_at")


def test_time_travel_truncated_master_gives_the_same_processing_decision(engine_runs, tmp_path):
    """For sampled invoices: drop every master row recorded after the invoice was received and every
    later document; the decision taken at processing time must not change."""
    root, _, _, _ = engine_runs["starter"]
    full = _run(_copy(root, tmp_path / "base"))
    manifest = sorted(read_table(root / "inbox", "intake_manifest"), key=lambda m: int(m["intake_seq"]))
    late = {"VENDOR_NOT_PAYABLE", "PAYMENT_DUE_DATE_PASSED"}
    for m in manifest[7::8]:
        at, day = m["received_at"], m["received_at"][:10]
        ds = _copy(root, tmp_path / m["doc_id"])
        _blank_snapshots(ds)
        keep = lambda rows, pred: [r for r in rows if pred(r)]
        grns = keep(read_table(ds / "master", "goods_receipt"), lambda g: g["posted_at"] <= at)
        ids_ = {g["grn_id"] for g in grns}
        _write(ds, "goods_receipt", grns)
        _write(ds, "goods_receipt_line", keep(read_table(ds / "master", "goods_receipt_line"), lambda l: l["grn_id"] in ids_))
        _write(ds, "vendor_status_history", keep(read_table(ds / "master", "vendor_status_history"),
                                                 lambda h: h["recorded_at"] <= at))
        _write(ds, "erp_event", keep(read_table(ds / "master", "erp_event"), lambda e: e["event_at"] <= at))
        pos = keep(read_table(ds / "master", "purchase_order"), lambda p: p["po_date"] <= day)
        po_ids = {p["po_id"] for p in pos}
        _write(ds, "purchase_order", pos)
        _write(ds, "purchase_order_line", keep(read_table(ds / "master", "purchase_order_line"),
                                               lambda l: l["po_id"] in po_ids))
        _write(ds, "intake_manifest", keep(read_table(ds / "inbox", "intake_manifest"),
                                           lambda r: int(r["intake_seq"]) <= int(m["intake_seq"])))
        past = _run(ds)
        a, ea = _decision(full, m["doc_id"])
        b, eb = _decision(past, m["doc_id"])
        assert {k: a[k] for k in PROCESSING_TIME} == {k: b[k] for k in PROCESSING_TIME}, m["doc_id"]
        strip = lambda es: sorted((e["exception_type"], e["invoice_line_id"], e["expected_value"], e["actual_value"])
                                  for e in es if e["exception_type"] not in late)
        assert strip(ea) == strip(eb), m["doc_id"]
        rows = lambda out: [r for r in out["match_result"] if r["invoice_id"] == a["invoice_id"]]
        assert rows(full) == rows(past), m["doc_id"]


# ------------------------------------------------------------------ rule mutation: the evaluation is not circular
def test_changing_a_tolerance_changes_the_engine_and_the_evaluation_sees_it(engine_runs, tmp_path):
    root, _, _, _ = engine_runs["starter"]
    ds = _copy(root, tmp_path / "ds")
    for layer in ("source", "ground_truth"):
        shutil.copytree(root / layer, ds / layer)
    raw = copy.deepcopy(POLICY.raw)
    raw["matching"]["price_tolerance_pct"] = "2.50"
    _run(ds, dataclasses.replace(POLICY, raw=raw))
    report, _ = evaluate_decisions(ds, POLICY.as_of_date)
    pv = report["per_type_invoice"]["PRICE_VARIANCE"]
    assert pv["fn"] >= 1 and pv["fp"] == 0                    # PV-BOUNDARY-OUT (+2% + 1 cent) now passes
    assert report["acceptance"]["fail"] >= 1
