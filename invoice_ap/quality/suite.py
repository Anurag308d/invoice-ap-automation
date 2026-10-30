"""Full validation suite over every table of a built dataset (R31).

It runs the defect-aware checks of `quick.py` (keys, every declared FK, enums and formats, embedded
IDs, date order and the as-of limit, arithmetic, lifecycles replayed from both event logs, mix,
oracle intent, duplicate collisions) and adds the engine-side invariants:
- polymorphic references: every `ap_event` and `erp_event` entity exists, with a consistent invoice;
- one decision per captured invoice; decision fields consistent with exceptions, approvals and
  payments; exactly one primary exception per blocked invoice, and it is the first in precedence;
- R34e: no payment for an invoice with an open blocking exception or an unapproved level;
- approvals only for invoices without a blocking issue at decision time;
- the N:M bridge never allocates more than a GRN line received, never a later GRN, never another
  PO line; duplicate pairs point to an earlier document of the same vendor;
- capture consistency (line counts, extraction rows, decided after captured) and policy provenance.

Labelled defects stay "labelled", never violations.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path

from ..common.enums import EXCEPTION_TYPES
from ..common.policy import Policy
from .quick import Checks, load, validate

RANK = {t: i for i, t in enumerate(EXCEPTION_TYPES)}
ENTITY_TABLE = {"INVOICE": ("invoice_decision", "invoice_id"), "EXCEPTION": ("ap_exception", "exception_id"),
                "APPROVAL": ("approval", "approval_id"), "PAYMENT": ("payment", "payment_id"),
                "PURCHASE_ORDER": ("purchase_order", "po_id"), "GOODS_RECEIPT": ("goods_receipt", "grn_id")}


def _engine_checks(t: dict, policy: Policy, c: Checks) -> None:
    index = {name: {r[key]: r for r in t.get(name, [])} for name, key in ENTITY_TABLE.values()}
    bad = []
    for log in ("ap_event", "erp_event"):
        for e in t.get(log, []):
            name, _ = ENTITY_TABLE[e["entity_type"]]
            target = index[name].get(e["entity_id"])
            if target is None:
                bad.append(f"{e['event_id']} -> missing {e['entity_type']} {e['entity_id']}")
            elif log == "ap_event" and target.get("invoice_id", e["invoice_id"]) != e["invoice_id"]:
                bad.append(f"{e['event_id']} invoice {e['invoice_id']} != entity's {target['invoice_id']}")
    c.add("polymorphic event references (ap_event, erp_event)", bad)

    cap = {r["invoice_id"]: r for r in t.get("captured_invoice", [])}
    dec = index["invoice_decision"]
    exc, apr = defaultdict(list), defaultdict(list)
    for e in t.get("ap_exception", []):
        exc[e["invoice_id"]].append(e)
    for a in t.get("approval", []):
        apr[a["invoice_id"]].append(a)
    pay = {p["invoice_id"]: p for p in t.get("payment", [])}
    bad = [f"{i} has no decision" for i in cap if i not in dec] + [f"{i} decided but not captured" for i in dec
                                                                   if i not in cap]
    unsafe, approvals_blocked = [], []
    for iid, d in dec.items():
        blocking = sorted((e for e in exc[iid] if e["blocking"] == "true"), key=lambda e: RANK[e["exception_type"]])
        open_blocking = [e for e in blocking if e["status_as_of"] == "OPEN"]
        primaries = [e for e in exc[iid] if e["is_primary"] == "true"]
        expected_primary = blocking[0]["exception_type"] if blocking else "NONE"
        if d["primary_issue"] != expected_primary:
            bad.append(f"{iid} primary {d['primary_issue']} != first blocking {expected_primary}")
        if (len(primaries) != 1 if blocking else primaries) or (primaries and primaries[0]["exception_type"] != expected_primary):
            bad.append(f"{iid} primary exception flags inconsistent")
        if (d["blocked"] == "true") != bool(open_blocking or d["status_as_of"] == "REJECTED"):
            bad.append(f"{iid} blocked flag inconsistent with exceptions")
        if set(x for x in d["issue_types"].split("|") if x) != {e["exception_type"] for e in exc[iid]}:
            bad.append(f"{iid} issue_types != its exceptions")
        if (d["payment_id"] or None) != (pay[iid]["payment_id"] if iid in pay else None):
            bad.append(f"{iid} payment_id inconsistent")
        if d["decided_at"] < cap[iid]["captured_at"]:
            bad.append(f"{iid} decided before captured")
        levels = [a["level"] for a in sorted(apr[iid], key=lambda a: int(a["sequence"]))]
        if levels and levels != d["approval_levels"].split("|")[:len(levels)]:
            bad.append(f"{iid} approval rows != approval_levels")
        if iid in pay and (open_blocking or not apr[iid] or any(a["status_as_of"] != "APPROVED" for a in apr[iid])):
            unsafe.append(iid)
        if apr[iid] and blocking and blocking[0]["created_at"] <= apr[iid][0]["requested_at"]:
            approvals_blocked.append(iid)
        for e in exc[iid]:
            if e["sla_due_date"] < e["created_at"][:10]:
                bad.append(f"{e['exception_id']} SLA before creation")
            overdue = e["status_as_of"] == "OPEN" and e["sla_due_date"] < policy.as_of_date.isoformat()
            if (e["is_overdue_as_of"] == "true") != overdue:
                bad.append(f"{e['exception_id']} overdue flag inconsistent")
    c.add("decision consistency (one decision per invoice, primary, blocked, issues, payment link)", bad)
    c.add("R34e: no payment for a blocked or unapproved invoice", [f"{i} paid while blocked" for i in unsafe])
    c.add("approvals only for invoices without a blocking issue at decision time",
          [f"{i} approval requested after a blocking issue" for i in approvals_blocked])

    bad = []
    grn_lines = {g["grn_line_id"]: g for g in t.get("goods_receipt_line", [])}
    posted = {g["grn_id"]: g["posted_at"] for g in t.get("goods_receipt", [])}
    lines = {l["invoice_line_id"]: l for l in t.get("captured_invoice_line", [])}
    match = {m["invoice_line_id"]: m for m in t.get("match_result", [])}
    received_at = {m["doc_id"]: m["received_at"] for m in t.get("intake_manifest", [])}
    used = Counter()
    for a in t.get("match_allocation", []):
        g, m = grn_lines[a["grn_line_id"]], match[a["invoice_line_id"]]
        used[a["grn_line_id"]] += Decimal(a["allocated_qty"])
        inv = cap[lines[a["invoice_line_id"]]["invoice_id"]]
        if g["po_line_id"] != m["po_line_id"]:
            bad.append(f"{a['allocation_id']} GRN line of another PO line")
        if posted[g["grn_id"]] > received_at[inv["doc_id"]]:
            bad.append(f"{a['allocation_id']} GRN posted after the invoice arrived")
    bad += [f"{g} allocated {q} > received" for g, q in used.items() if q > Decimal(grn_lines[g]["received_qty"])]
    for p in t.get("duplicate_pair", []):
        a, b = cap[p["invoice_id"]], cap[p["original_invoice_id"]]
        if received_at[b["doc_id"]] >= received_at[a["doc_id"]] or a["vendor_id"] != b["vendor_id"]:
            bad.append(f"{p['duplicate_pair_id']} original not earlier or other vendor")
    c.add("N:M bridge and duplicate pairs", bad)

    bad = []
    n_lines = Counter(l["invoice_id"] for l in t.get("captured_invoice_line", []))
    fields = Counter(f["invoice_id"] for f in t.get("extraction_field", []))
    for iid, r in cap.items():
        if int(r["line_count"]) != n_lines[iid]:
            bad.append(f"{iid} line_count != captured lines")
        if not fields[iid]:
            bad.append(f"{iid} has no extraction_field rows")
    versions = {p["policy_version"]: p for p in t.get("policy_version", [])}
    if t.get("policy_version") is not None:
        pv = versions.get(policy.version)
        if not pv or pv["sha256"] != policy.sha256:
            bad.append("policy_version row does not match config/ap_policy.toml")
        for name in ("invoice_decision", "ap_exception", "approval", "payment", "ap_event"):
            bad += [f"{name} uses unknown policy {r['policy_version']}" for r in t.get(name, [])
                    if r["policy_version"] not in versions]
    c.add("capture consistency and policy provenance", bad)


def run_suite(root: Path, policy: Policy, alloc=None) -> dict:
    t = load(Path(root))
    report = validate(t, policy, alloc)
    c = Checks()
    _engine_checks(t, policy, c)
    report["checks"] += c.items
    report["violations"] = sum(i["violations"] for i in report["checks"])
    report["status"] = "pass" if report["violations"] == 0 else "fail"
    report["tables"] = {name: len(rows) for name, rows in sorted(t.items())}
    return report


def to_markdown(r: dict, title: str) -> str:
    out = [f"# {title}", "", f"Status: **{r['status'].upper()}** - {r['violations']} violations, {r['labelled']} "
           "labelled defects reported as expected (each belongs to a labelled scenario in ground truth).", "",
           "| Check | Status | Violations | Labelled (expected) | Examples |", "|---|---|---|---|---|"]
    for i in r["checks"]:
        ex = "; ".join(i["examples"] or i["labelled_examples"])[:160]
        out.append(f"| {i['check']} | {i['status']} | {i['violations']} | {i['labelled']} | {ex} |")
    out += ["", "## Rows per table", "", "| Table | Rows |", "|---|---|"]
    out += [f"| {k} | {v} |" for k, v in r["tables"].items()]
    return "\n".join(out) + "\n"
