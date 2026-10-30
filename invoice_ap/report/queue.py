"""Role-based work queues at the snapshot (R6): what each of the five actors has to do on the as-of date.

- BUSINESS_REQUESTER: open price, receipt and PO-line exceptions; REQ approvals pending.
- PROCESS_OWNER: open policy exceptions (invoice before PO, PO quantity overrun).
- APPROVER: approval levels pending.
- OPERATIONS_ANALYST: capture review, duplicates, header and tax validation, payment watch.
- SYSTEM_ADMINISTRATOR: vendor-master exceptions (closed, blocked, unknown or not payable vendors).
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

from ..common.calendar import BusinessCalendar
from ..spec.io import read_table

ROLES = ("BUSINESS_REQUESTER", "PROCESS_OWNER", "APPROVER", "OPERATIONS_ANALYST", "SYSTEM_ADMINISTRATOR")


def queue_items(root: Path, role: str, as_of: date, policy_raw: dict, user: str | None = None) -> list[dict]:
    root = Path(root)
    cal = BusinessCalendar.from_policy(policy_raw)
    cap = {c["invoice_id"]: c for c in read_table(root / "processed", "captured_invoice")}
    items = []
    for e in read_table(root / "processed", "ap_exception"):
        if e["assigned_role"] == role and e["status_as_of"] == "OPEN" and (user is None or e["assigned_user_id"] == user):
            age = len(cal.business_days(date.fromisoformat(e["created_at"][:10]), as_of)) - 1
            items.append({"kind": "exception", "id": e["exception_id"], "invoice_id": e["invoice_id"],
                          "what": e["exception_type"], "queue": e["queue"], "user": e["assigned_user_id"],
                          "due": e["sla_due_date"], "age_business_days": age,
                          "past_sla": e["is_overdue_as_of"] == "true",
                          "detail": f"expected {e['expected_value'] or '-'}, actual {e['actual_value'] or '-'}",
                          "amount": cap[e["invoice_id"]]["header_gross_amount"]})
    for a in read_table(root / "processed", "approval"):
        if a["approver_role"] == role and a["status_as_of"] == "PENDING" and (user is None or a["approver_user_id"] == user):
            age = len(cal.business_days(date.fromisoformat(a["requested_at"][:10]), as_of)) - 1
            items.append({"kind": "approval", "id": a["approval_id"], "invoice_id": a["invoice_id"],
                          "what": f"approve {a['level']} ({a['approval_band']})", "queue": "APPROVALS",
                          "user": a["approver_user_id"], "due": "", "age_business_days": age, "past_sla": False,
                          "detail": f"requested {a['requested_at'][:16]}",
                          "amount": cap[a["invoice_id"]]["header_gross_amount"]})
    return sorted(items, key=lambda i: (i["due"] or "9999", i["id"]))


def render(items: list[dict], role: str, user: str | None) -> str:
    who = f"{role}{' / ' + user if user else ''}"
    if not items:
        return f"{who}: nothing open at the snapshot\n"
    past = sum(i["past_sla"] for i in items)
    out = [f"{who}: {len(items)} open items ({past} open and past SLA at the snapshot; no resolutions simulated)",
           f"{'ID':<16} {'INVOICE':<27} {'WHAT':<28} {'QUEUE':<21} {'USER':<9} {'DUE':<10} {'AGE':>4}  AMOUNT"]
    for i in items:
        out.append(f"{i['id']:<16} {i['invoice_id']:<27} {i['what'][:28]:<28} {i['queue']:<21} {i['user']:<9} "
                   f"{i['due']:<10} {i['age_business_days']:>4}  {i['amount']}{'  PAST SLA' if i['past_sla'] else ''}")
    return "\n".join(out) + "\n"
