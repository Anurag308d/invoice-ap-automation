"""E3-E11 decision evaluation against ground truth, and the per-invoice acceptance check (R34a-e).

Engine invoices are joined to ground truth on `doc_id` (the engine assigns invoice IDs; agreement of
those IDs is itself reported). Every metric is computed from the files of one built dataset:
`processed/` (engine), `ground_truth/` and `source/` (evaluation only), `master/`.
"""
from __future__ import annotations

import csv
import io
from collections import Counter, defaultdict
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from ..common.enums import EXCEPTION_TYPES
from ..common.money import line_net, tax_amount
from ..spec.io import read_table

D = Decimal
ARI_TAX = {"HEADER_TOTAL_MISMATCH", "LINE_AMOUNT_MISMATCH", "TAX_CODE_INVALID", "TAX_CODE_MISMATCH",
           "TAX_AMOUNT_MISMATCH"}
FULL_GROSS = {"EXT_LOW_CONFIDENCE", "DUPLICATE_EXACT", "DUPLICATE_NUMBER_REUSE", "DUPLICATE_SUSPECTED",
              "VENDOR_NOT_FOUND", "VENDOR_SENDER_MISMATCH", "VENDOR_CLOSED", "VENDOR_BLOCKED", "PO_NOT_FOUND",
              "VENDOR_PO_MISMATCH", "INVOICE_DATE_IN_FUTURE", "INVOICE_BEFORE_PO", "MISSING_RECEIPT",
              "PO_LINE_UNMATCHED", "VENDOR_NOT_PAYABLE"}


def _lst(v: str) -> list[str]:
    return [x for x in v.split("|") if x]


def _pct(n, d) -> str:
    return f"{(D(n) * 100 / D(d)).quantize(D('0.01'))}%" if d else "-"


def _f1(tp, fp, fn) -> dict:
    p = D(tp) / (tp + fp) if tp + fp else None
    r = D(tp) / (tp + fn) if tp + fn else None
    f = 2 * p * r / (p + r) if p is not None and r is not None and p + r else (D(0) if p is not None or r is not None else None)
    q = lambda x: f"{x.quantize(D('0.0001'))}" if x is not None else "not present"
    return {"tp": tp, "fp": fp, "fn": fn, "precision": q(p), "recall": q(r), "f1": q(f)}


def _median(values: list) -> str:
    s = sorted(values)
    return str(s[len(s) // 2]) if s else "-"


def evaluate_decisions(root: Path, as_of: date) -> tuple[dict, list[dict]]:
    root = Path(root)
    gt = {g["doc_id"]: g for g in read_table(root / "ground_truth", "ground_truth")}
    src = {s["doc_id"]: s for s in read_table(root / "source", "invoice")}
    src_lines = defaultdict(list)
    for l in read_table(root / "source", "invoice_line"):
        src_lines[l["invoice_id"]].append(l)
    gtl = defaultdict(dict)
    for l in read_table(root / "ground_truth", "ground_truth_line"):
        gtl[l["invoice_id"]][int(l["invoice_line_id"][-2:])] = l
    cap = {c["doc_id"]: c for c in read_table(root / "processed", "captured_invoice")}
    doc_of = {c["invoice_id"]: d for d, c in cap.items()}
    dec = {doc_of[d["invoice_id"]]: d for d in read_table(root / "processed", "invoice_decision")}
    mres = defaultdict(dict)
    for r in read_table(root / "processed", "match_result"):
        mres[r["invoice_id"]][int(r["invoice_line_id"][-2:])] = r
    exc = defaultdict(list)
    for e in read_table(root / "processed", "ap_exception"):
        exc[e["invoice_id"]].append(e)
    pay = {p["invoice_id"]: p for p in read_table(root / "processed", "payment")}
    apr = defaultdict(list)
    for a in read_table(root / "processed", "approval"):
        apr[a["invoice_id"]].append(a)
    pairs = {doc_of[p["invoice_id"]]: p for p in read_table(root / "processed", "duplicate_pair")}
    gt_doc_of = {g["invoice_id"]: d for d, g in gt.items()}

    types = Counter()
    per_type = {t: [0, 0, 0] for t in EXCEPTION_TYPES}
    line_type = {t: [0, 0, 0] for t in EXCEPTION_TYPES}
    primary_cm, status_cm = Counter(), Counter()
    agree = Counter()
    n = len(gt)
    acceptance = []
    for doc_id, g in sorted(gt.items()):
        c, d = cap[doc_id], dec[doc_id]
        iid = c["invoice_id"]
        expected, got = set(_lst(g["expected_issue_types"])), set(_lst(d["issue_types"]))
        for t in EXCEPTION_TYPES:
            per_type[t][0] += t in expected and t in got
            per_type[t][1] += t in got and t not in expected
            per_type[t][2] += t in expected and t not in got
        # line-level labels, joined on the printed line number
        eng_line = defaultdict(set)
        for e in exc[iid]:
            if e["invoice_line_id"]:
                eng_line[int(e["invoice_line_id"][-2:])].add(e["exception_type"])
        for no, gl in gtl[g["invoice_id"]].items():
            exp_l, got_l = set(_lst(gl["expected_line_issue_types"])), eng_line.get(no, set())
            for t in EXCEPTION_TYPES:
                line_type[t][0] += t in exp_l and t in got_l
                line_type[t][1] += t in got_l and t not in exp_l
                line_type[t][2] += t in exp_l and t not in got_l
            m = mres[iid].get(no)
            for key, ekey in (("price_status", "expected_price_status"), ("qty_status", "expected_qty_status"),
                              ("tax_status", "expected_tax_status")):
                agree[f"line {key}"] += bool(m) and m[key] == gl[ekey]
            for key, ekey in (("received_qty", "expected_received_qty"), ("prior_invoiced_qty",
                                                                           "expected_prior_invoiced_qty")):
                agree[f"line {key}"] += bool(m) and (m[key] == gl[ekey] or (m[key] and gl[ekey] and D(m[key]) == D(gl[ekey])))
            agree["lines"] += 1
        primary_cm[(g["expected_primary_issue"], d["primary_issue"])] += 1
        status_cm[(g["expected_final_status"], d["status_as_of"])] += 1
        p = pay.get(iid)
        exp_dup = gt_doc_of.get(g["expected_duplicate_of"]) if g["expected_duplicate_of"] else None
        got_dup = doc_of.get(d["duplicate_of_invoice_id"]) if d["duplicate_of_invoice_id"] else None
        blocking = [e for e in exc[iid] if e["blocking"] == "true"]
        roles = sorted({e["assigned_role"] for e in blocking})
        queues = sorted({e["queue"] for e in exc[iid]})
        checks = {
            "invoice_id": iid == g["invoice_id"],
            "issue_types": expected == got,
            "primary_issue": g["expected_primary_issue"] == d["primary_issue"],
            "blocked": (g["expected_blocked"] == "true") == (d["blocked"] == "true"),
            "match_status": g["expected_match_status"] == d["match_status"],
            "duplicate_of": exp_dup == got_dup,
            "assigned_roles": _lst(g["expected_assigned_roles"]) == roles,
            "queues": _lst(g["expected_queues"]) == queues,
            "approval_band": g["expected_approval_band"] == d["approval_band"],
            "approval_levels": g["expected_approval_levels"] == d["approval_levels"],
            "final_status": g["expected_final_status"] == d["status_as_of"],
            "payment_ready": (g["expected_payment_ready"] == "true") == bool(p),
            "payment_status": g["expected_payment_status"] == (p["status_as_of"] if p else ""),
            "due_date": g["expected_due_date"] == (p["due_date"] if p else ""),
            "scheduled_date": g["expected_scheduled_date"] == (p["scheduled_date"] if p else ""),
        }
        for k, v in checks.items():
            agree[k] += v
        # R34e: a payment record only with no open blocking exception, every level approved, vendor payable
        unsafe = bool(p) and (any(e["status_as_of"] == "OPEN" for e in blocking)
                              or any(a["status_as_of"] != "APPROVED" for a in apr[iid]) or not apr[iid])
        # R34b: engine ARI/TAX verdicts == ground truth, and ground truth == an independent recomputation
        arith = _recompute(src[doc_id], src_lines[g["invoice_id"]]) if not _gated(g) else set()
        exp_at = expected & ARI_TAX - {"TAX_CODE_MISMATCH", "TAX_CODE_INVALID"}
        r34b = (got & ARI_TAX) == (expected & ARI_TAX) and (arith == exp_at)
        r34a = "flagged" if c["capture_status"] == "LOW_CONFIDENCE" else "pass"
        row = {"doc_id": doc_id, "invoice_id": iid, "scenario_code": g["scenario_code"],
               "r34a_extraction": r34a, "r34b_arithmetic_tax": "pass" if r34b else "fail",
               "r34c_duplicate_pair": "pass" if checks["duplicate_of"] else "fail",
               "r34d_match_and_approval": "pass" if all(checks[k] for k in (
                   "match_status", "primary_issue", "approval_band", "approval_levels", "final_status")) else "fail",
               "r34e_no_blocked_payment_ready": "fail" if unsafe else "pass"}
        failed = [k for k, v in checks.items() if not v]
        row["result"] = "pass" if all(v in ("pass", "flagged") for v in list(row.values())[3:]) and not failed else "fail"
        row["deviation"] = "; ".join(failed)
        acceptance.append(row)
        agree["unsafe_payment"] += unsafe

    exp_pairs = {d: gt_doc_of[g["expected_duplicate_of"]] for d, g in gt.items() if g["expected_duplicate_of"]}
    got_pairs = {d: doc_of[p["original_invoice_id"]] for d, p in pairs.items()}
    pair_tp = sum(1 for d, o in got_pairs.items() if exp_pairs.get(d) == o)
    by_kind = defaultdict(lambda: [0, 0])
    for d, o in exp_pairs.items():
        kind = gt[d]["scenario_code"]
        by_kind[kind][0] += 1
        by_kind[kind][1] += got_pairs.get(d) == o
    true_negative_codes = ("C-RECURRING", "C-SAME-DAY-DIFF-PO", "C-PARTIAL-BILLING")
    tn_fp = sum(1 for d in got_pairs if gt[d]["scenario_code"].startswith(true_negative_codes))

    decisions = [dec[d] for d in gt]
    stp = sum(1 for d in decisions if d["status_as_of"] in ("PAYMENT_READY", "PAID") and not d["issue_types"]
              and d["approval_levels"] == "AUTO")
    blocked = [d for d in decisions if d["blocked"] == "true"]
    all_exc = [e for es in exc.values() for e in es]
    open_exc = [e for e in all_exc if e["status_as_of"] == "OPEN"]
    var = _value_at_risk(root, gt, cap, dec, src, src_lines)
    backlog = _backlog(open_exc, as_of)
    cycle = [(datetime.fromisoformat(pay[d["invoice_id"]]["created_at"][:19]) -
              datetime.fromisoformat(c["captured_at"][:19])).days for doc, c in cap.items()
             for d in [dec[doc]] if d["invoice_id"] in pay]
    report = {
        "invoices": n,
        "agreement": {k: f"{agree[k]}/{n} ({_pct(agree[k], n)})" for k in (
            "invoice_id", "issue_types", "primary_issue", "blocked", "match_status", "duplicate_of", "assigned_roles",
            "queues", "approval_band", "approval_levels", "final_status", "payment_ready", "payment_status",
            "due_date", "scheduled_date")},
        "line_agreement": {k[5:]: f"{agree[k]}/{agree['lines']} ({_pct(agree[k], agree['lines'])})" for k in (
            "line price_status", "line qty_status", "line tax_status", "line received_qty", "line prior_invoiced_qty")},
        "per_type_invoice": {t: _f1(*v) for t, v in per_type.items()},
        "per_type_line": {t: _f1(*v) for t, v in line_type.items() if any(v) or t in (
            "LINE_AMOUNT_MISMATCH", "TAX_CODE_INVALID", "TAX_CODE_MISMATCH", "TAX_AMOUNT_MISMATCH", "PO_LINE_UNMATCHED",
            "MISSING_RECEIPT", "QTY_EXCEEDS_PO", "QTY_EXCEEDS_RECEIVED", "PRICE_VARIANCE")},
        "not_present_types": [t for t, v in per_type.items() if not any(v)],
        "primary_issue_confusion": {f"{e} -> {p}": k for (e, p), k in sorted(primary_cm.items())},
        "primary_issue_off_diagonal": sum(k for (e, p), k in primary_cm.items() if e != p),
        "final_status_confusion": {f"{e} -> {p}": k for (e, p), k in sorted(status_cm.items())},
        "duplicates": {"expected_pairs": len(exp_pairs), "detected_pairs": len(got_pairs), "correct_pairs": pair_tp,
                       "pair_precision": _pct(pair_tp, len(got_pairs)), "pair_recall": _pct(pair_tp, len(exp_pairs)),
                       "by_type": {k: f"{v[1]}/{v[0]}" for k, v in sorted(by_kind.items())},
                       "true_negative_false_positives": tn_fp},
        "approvals": {"eligible_invoices": sum(1 for d in decisions if d["approval_band"]),
                      "approvals_for_blocked_invoices": sum(1 for d in blocked if apr[d["invoice_id"]]
                                                            and d["approval_band"] == ""),
                      "pending_at_as_of": sum(1 for a in apr.values() for x in a if x["status_as_of"] == "PENDING"),
                      "levels_by_band": dict(sorted(Counter(d["approval_band"] or "not eligible" for d in decisions).items()))},
        "payments": {"payment_records": len(pay), "blocked_or_unapproved_with_payment": agree["unsafe_payment"],
                     "paid": sum(1 for p in pay.values() if p["status_as_of"] == "PAID"),
                     "scheduled": sum(1 for p in pay.values() if p["status_as_of"] == "SCHEDULED"),
                     "rtgs": sum(1 for p in pay.values() if p["payment_method"] == "RTGS")},
        "kpis": {"stp_rate": _pct(stp, n), "stp_invoices": stp, "exception_rate": _pct(len(blocked), n),
                 "exceptions_by_type": dict(sorted(Counter(e["exception_type"] for e in all_exc).items())),
                 "open_by_role": dict(sorted(Counter(e["assigned_role"] for e in open_exc).items())),
                 "open_by_queue": dict(sorted(Counter(e["queue"] for e in open_exc).items())),
                 "cycle_days_capture_to_ready": {"median": _median(cycle),
                                                 "p90": str(sorted(cycle)[len(cycle) * 9 // 10]) if cycle else "-"}},
        "value_at_risk": var,
        "backlog": backlog,
        "acceptance": {"invoices": n, "pass": sum(r["result"] == "pass" for r in acceptance),
                       "fail": sum(r["result"] == "fail" for r in acceptance),
                       "r34a_flagged_capture_review": sum(r["r34a_extraction"] == "flagged" for r in acceptance),
                       "by_criterion": {k: dict(Counter(r[k] for r in acceptance)) for k in (
                           "r34a_extraction", "r34b_arithmetic_tax", "r34c_duplicate_pair", "r34d_match_and_approval",
                           "r34e_no_blocked_payment_ready")},
                       "deviations": [r for r in acceptance if r["result"] == "fail"]},
    }
    return report, acceptance


AGE_BUCKETS = (("<= 5 business days", 5), ("6-20 business days", 20), ("> 20 business days", None))


def _backlog(open_exc: list[dict], as_of: date) -> dict:
    """Open exceptions past their SLA at the snapshot. No resolutions are simulated (ADR-011), so this
    is the backlog an AP team would inherit on the as-of date, aged in business days since creation."""
    from ..common.calendar import BusinessCalendar
    from ..common.policy import load_policy
    cal = BusinessCalendar.from_policy(load_policy().raw)
    past = [e for e in open_exc if e["is_overdue_as_of"] == "true"]
    table: dict[str, Counter] = defaultdict(Counter)
    for e in past:
        age = len(cal.business_days(date.fromisoformat(e["created_at"][:10]), as_of)) - 1
        bucket = next(name for name, limit in AGE_BUCKETS if limit is None or age <= limit)
        table[e["assigned_role"]][bucket] += 1
        table["ALL ROLES"][bucket] += 1
    return {"label": "open and past SLA at the snapshot (no resolutions simulated)",
            "open_exceptions": len(open_exc), "past_sla": len(past),
            "by_role_and_age": {role: {name: c[name] for name, _ in AGE_BUCKETS} for role, c in sorted(table.items())}}


def _gated(g: dict) -> bool:
    return g["expected_primary_issue"] in ("EXT_LOW_CONFIDENCE", "VENDOR_NOT_FOUND") or \
        g["expected_primary_issue"].startswith("DUPLICATE_")


def _recompute(inv: dict, lines: list[dict]) -> set[str]:
    """Independent recomputation of ARI-01, ARI-02 and TAX-03 from the invoice as issued."""
    out = set()
    nets = sum(D(l["line_net_amount"]) for l in lines)
    taxes = sum(D(l["tax_amount"]) for l in lines)
    if (abs(D(inv["header_net_amount"]) - nets) > D("0.01") or abs(D(inv["header_tax_amount"]) - taxes) > D("0.01")
            or abs(D(inv["header_gross_amount"]) - nets - taxes) > D("0.01")):
        out.add("HEADER_TOTAL_MISMATCH")
    for l in lines:
        if abs(D(l["line_net_amount"]) - line_net(D(l["quantity"]), D(l["unit_price"]))) > D("0.01"):
            out.add("LINE_AMOUNT_MISMATCH")
        if abs(D(l["tax_amount"]) - tax_amount(D(l["line_net_amount"]), D(l["tax_rate_pct"]))) > D("0.01"):
            out.add("TAX_AMOUNT_MISMATCH")
    return out


def _value_at_risk(root, gt, cap, dec, src, src_lines) -> dict:
    """E11: money held back on invoices with a true blocking issue, by the engine's primary issue."""
    mres = defaultdict(list)
    for r in read_table(root / "processed", "match_result"):
        mres[r["invoice_id"]].append(r)
    lines = defaultdict(dict)
    for l in read_table(root / "processed", "captured_invoice_line"):
        lines[l["invoice_id"]][l["invoice_line_id"]] = l
    rates = {t["tax_code"]: D(t["rate_pct"]) for t in read_table(root / "master", "tax_code")}
    by_issue, total, missed = Counter(), D(0), D(0)
    for doc_id, g in gt.items():
        d, c = dec[doc_id], cap[doc_id]
        if g["expected_blocked"] != "true":
            continue
        gross = D(src[doc_id]["header_gross_amount"])
        if d["blocked"] != "true":
            missed += gross
            continue
        issue = d["primary_issue"]
        if issue in FULL_GROSS:
            amount = gross
        elif issue in ("QTY_EXCEEDS_PO", "QTY_EXCEEDS_RECEIVED", "PRICE_VARIANCE"):
            amount = D(0)
            for r in mres[c["invoice_id"]]:
                ln = lines[c["invoice_id"]][r["invoice_line_id"]]
                q, price = D(ln["quantity"]), D(ln["unit_price"])
                rate = (D(ln["tax_amount"]) / D(ln["line_net_amount"])) if D(ln["line_net_amount"]) else D(0)
                if r["qty_status"] in ("EXCEEDS_PO", "EXCEEDS_RECEIVED"):
                    allowed = D(r["received_qty"]) if r["qty_status"] == "EXCEEDS_RECEIVED" else D(r["max_qty_vs_po"])
                    allowed = min(allowed, D(r["received_qty"])) - D(r["prior_invoiced_qty"])
                    amount += max(D(0), q - max(allowed, D(0))) * price * (1 + rate)
                if r["price_status"] == "OUT_OF_TOLERANCE":
                    amount += abs(price - D(r["po_unit_price"])) * q * (1 + rate)
        else:
            nets = sum(D(l["line_net_amount"]) for l in lines[c["invoice_id"]].values())
            taxes = sum(D(l["tax_amount"]) for l in lines[c["invoice_id"]].values())
            amount = abs(D(c["header_gross_amount"] or 0) - nets - taxes)
            for l in lines[c["invoice_id"]].values():
                amount += abs(D(l["line_net_amount"]) - line_net(D(l["quantity"]), D(l["unit_price"])))
            for r in mres[c["invoice_id"]]:              # tax: printed vs expected, and the PO code's tax
                l = lines[c["invoice_id"]][r["invoice_line_id"]]
                if r["expected_tax_amount"]:
                    amount += abs(D(l["tax_amount"]) - D(r["expected_tax_amount"]))
                if r["po_tax_code"] and r["po_tax_code"] != l["tax_code"]:
                    amount += abs(D(l["tax_amount"]) - tax_amount(D(l["line_net_amount"]), rates[r["po_tax_code"]]))
        by_issue[issue] += amount
        total += amount
    q = lambda x: f"{D(x).quantize(D('0.01')):f}"
    return {"held_value_inr": q(total), "by_primary_issue": {k: q(v) for k, v in sorted(by_issue.items())},
            "blocked_invoices_released_in_error_value_inr": q(missed),
            "basis": "full gross for duplicates, vendor, PO, date, receipt and capture holds; excess quantity or price "
                     "difference (with tax) for quantity and price variances; absolute difference for tax and arithmetic"}


def acceptance_csv(rows: list[dict]) -> bytes:
    buf = io.StringIO(newline="")
    w = csv.DictWriter(buf, fieldnames=list(rows[0]), lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue().encode("utf-8")


DEFINITIONS = (
    ("STP rate", "Invoices that reached PAYMENT_READY or PAID with no exception at all and AUTO approval, divided "
                 "by all invoices (evaluation_plan E10)."),
    ("Exception rate", "Invoices blocked at the snapshot (an open blocking exception, or REJECTED) divided by all "
                       "invoices."),
    ("Precision / recall / F1", "Per exception type, over invoices (or lines): TP = expected and raised, FP = raised "
                                "but not expected, FN = expected but not raised. A type with no expected and no "
                                "raised instance is 'not present', never 0/0."),
    ("Agreement", "Share of invoices whose engine value equals the ground-truth value exactly (joined on doc_id)."),
    ("Payment-ready safety", "Invoices with a payment record and an open blocking exception or an unapproved level "
                             "(R34e). Must be 0."),
    ("Value at risk held", "Money held back on truly blocked invoices: full gross for duplicate, vendor, PO, date, "
                           "receipt and capture holds; excess quantity or price difference (with tax) for quantity and "
                           "price variances; the absolute difference for tax and arithmetic (E11)."),
    ("Per-invoice acceptance", "R34a extracted fields equal the source (or the document is flagged for capture "
                               "review); R34b arithmetic and tax verdicts equal ground truth and an independent "
                               "recomputation; R34c the duplicate pair is correct; R34d match status, primary issue, "
                               "approval band, levels and final status agree; R34e no blocked invoice is payable."),
    ("Blocked value released in error", "Gross of invoices that ground truth blocks but the engine did not. Must "
                                        "be 0.00."),
    ("Cycle days", "Calendar days from capture to the payment record (ready), over payment-ready invoices."),
    ("Open and past SLA", "Open exceptions whose SLA due date is before the as-of date. The snapshot simulates no "
                          "resolutions (ADR-011), so this is the inherited backlog, aged in business days since the "
                          "exception was raised."),
)


def _table(head: list[str], rows: list[list]) -> list[str]:
    return ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)] + [
        "| " + " | ".join(str(c) for c in r) + " |" for r in rows]


def _kv(d: dict, key: str = "Item", value: str = "Value") -> list[str]:
    return _table([key, value], [[k, v] for k, v in d.items()])


def to_markdown(r: dict, title: str) -> str:
    k, a = r["kpis"], r["acceptance"]
    out = [f"# {title}", "", f"Invoices evaluated: {r['invoices']}. Definitions are at the end of this page.", "",
           "## Headline", ""]
    out += _kv({"STP rate": f"{k['stp_rate']} ({k['stp_invoices']} invoices)", "Exception rate": k["exception_rate"],
                "Payment-ready safety (R34e) violations": r["payments"]["blocked_or_unapproved_with_payment"],
                "Per-invoice acceptance (R34a-e)": f"{a['pass']} pass / {a['fail']} fail",
                "Value at risk held (INR)": r["value_at_risk"]["held_value_inr"],
                "Blocked value released in error (INR)": r["value_at_risk"]["blocked_invoices_released_in_error_value_inr"],
                "Cycle days capture -> ready (median / p90)": f"{k['cycle_days_capture_to_ready']['median']} / "
                                                              f"{k['cycle_days_capture_to_ready']['p90']}"}, "KPI")
    out += ["", "## Agreement with ground truth (invoice level)", ""] + _kv(r["agreement"], "Item", "Agreement")
    out += ["", "## Agreement with ground truth (line level)", ""] + _kv(r["line_agreement"], "Item", "Agreement")
    out += ["", "## Per exception type (invoice level)", ""]
    out += _table(["Type", "TP", "FP", "FN", "Precision", "Recall", "F1"],
                  [[t, m["tp"], m["fp"], m["fn"], m["precision"], m["recall"], m["f1"]]
                   for t, m in r["per_type_invoice"].items()])
    out += ["", "## Per exception type (line level)", ""]
    out += _table(["Type", "TP", "FP", "FN", "Precision", "Recall", "F1"],
                  [[t, m["tp"], m["fp"], m["fn"], m["precision"], m["recall"], m["f1"]]
                   for t, m in r["per_type_line"].items()])
    out += ["", "Not present in this dataset (covered by unit fixtures): " + ", ".join(r["not_present_types"]) + ".",
            "", f"## Primary issue confusion (expected -> engine; off-diagonal {r['primary_issue_off_diagonal']})", ""]
    out += _kv(r["primary_issue_confusion"], "Expected -> engine", "Invoices")
    out += ["", "## Final status confusion", ""] + _kv(r["final_status_confusion"], "Expected -> engine", "Invoices")
    dup = r["duplicates"]
    out += ["", "## Duplicates", ""]
    out += _kv({"Expected pairs": dup["expected_pairs"], "Detected pairs": dup["detected_pairs"],
                "Correct pairs": dup["correct_pairs"], "Pair precision": dup["pair_precision"],
                "Pair recall": dup["pair_recall"],
                "False positives on true negatives": dup["true_negative_false_positives"]})
    out += ["", "Correct by scenario:", ""] + _kv(dup["by_type"], "Scenario", "Correct / expected")
    ap = r["approvals"]
    out += ["", "## Approvals", ""]
    out += _kv({"Eligible invoices": ap["eligible_invoices"], "Approvals for blocked invoices": ap["approvals_for_blocked_invoices"],
                "Levels pending at the as-of date": ap["pending_at_as_of"]})
    out += ["", "Invoices by approval band:", ""] + _kv(ap["levels_by_band"], "Band", "Invoices")
    out += ["", "## Payments", ""] + _kv({"Payment records": r["payments"]["payment_records"],
                                         "PAID": r["payments"]["paid"], "SCHEDULED": r["payments"]["scheduled"],
                                         "RTGS": r["payments"]["rtgs"],
                                         "Blocked or unapproved with a payment": r["payments"]["blocked_or_unapproved_with_payment"]})
    out += ["", "## Exceptions", "", "Raised, by type:", ""] + _kv(k["exceptions_by_type"], "Type", "Exceptions")
    out += ["", "Open at the snapshot, by role:", ""] + _kv(k["open_by_role"], "Role", "Open")
    out += ["", "Open at the snapshot, by queue:", ""] + _kv(k["open_by_queue"], "Queue", "Open")
    b = r["backlog"]
    out += ["", f"## Backlog: {b['label']}", "",
            f"{b['past_sla']} of {b['open_exceptions']} open exceptions are past their SLA at the snapshot. Age is in "
            "business days since the exception was raised.", ""]
    names = [n for n, _ in AGE_BUCKETS]
    out += _table(["Role"] + names, [[role] + [c[n] for n in names] for role, c in b["by_role_and_age"].items()])
    v = r["value_at_risk"]
    out += ["", "## Value at risk held, by primary issue (INR)", ""] + _kv(v["by_primary_issue"], "Primary issue", "INR")
    out += ["", "## Per-invoice acceptance (R34a-e)", "",
            f"{a['pass']} of {a['invoices']} invoices pass; {a['r34a_flagged_capture_review']} are flagged for capture "
            "review, which is their expected outcome. Full list: `acceptance_per_invoice.csv`.", ""]
    out += _table(["Criterion"] + ["pass", "flagged", "fail"],
                  [[c] + [v.get(x, 0) for x in ("pass", "flagged", "fail")] for c, v in a["by_criterion"].items()])
    out += ["", "Deviations:", ""]
    out += [f"- {d['doc_id']} {d['invoice_id']} ({d['scenario_code']}): {d['deviation']}" for d in a["deviations"]] \
        or ["- none"]
    out += ["", "## Definitions", ""] + _table(["Term", "Definition"], [list(d) for d in DEFINITIONS])
    return "\n".join(out) + "\n"
