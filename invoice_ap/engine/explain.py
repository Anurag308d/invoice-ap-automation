"""`python -m invoice_ap explain <invoice_id>`: one invoice's decision, reconstructed only from the
engine's own output (processed/), so the explanation is exactly what the engine recorded."""
from __future__ import annotations

import json
from pathlib import Path

from ..spec.io import read_table


def explain(processed: Path, invoice_id: str) -> str:
    processed = Path(processed)
    cap = next((c for c in read_table(processed, "captured_invoice") if c["invoice_id"] == invoice_id), None)
    if cap is None:
        raise KeyError(f"{invoice_id} is not in {processed}")
    dec = next(d for d in read_table(processed, "invoice_decision") if d["invoice_id"] == invoice_id)
    out = [f"{invoice_id}  (document {cap['doc_id']}, {cap['channel']}, captured {cap['captured_at']})",
           f"  vendor {cap['vendor_id'] or '-'} from printed tax registration {cap['vendor_tax_id']} (VEN-01, ID-01)",
           f"  invoice no {cap['vendor_invoice_number']} dated {cap['invoice_date']}; PO {cap['po_id'] or '-'}; "
           f"gross {cap['header_gross_amount']} {cap['currency']}; capture {cap['capture_status']} "
           f"(min confidence {cap['min_field_confidence']})",
           f"  STATUS {dec['status_as_of']} | primary issue {dec['primary_issue']} | match {dec['match_status']} | "
           f"band {dec['approval_band'] or '-'} {dec['approval_levels'] or ''} | payment {dec['payment_id'] or '-'}",
           f"  rules: {dec['rule_ids']}  (policy {dec['policy_version']})"]
    if dec["duplicate_of_invoice_id"]:
        out.append(f"  duplicate of {dec['duplicate_of_invoice_id']}")
    out.append("Exceptions:")
    for e in read_table(processed, "ap_exception"):
        if e["invoice_id"] == invoice_id:
            out.append(f"  {e['exception_id']} {e['exception_type']} [{e['rule_id']}] {e['invoice_line_id'] or 'header'}: "
                       f"expected {e['expected_value'] or '-'}, actual {e['actual_value'] or '-'}"
                       f"{', variance ' + e['variance'] if e['variance'] else ''}"
                       f"{', tolerance ' + e['tolerance'] if e['tolerance'] else ''} -> {e['assigned_role']} "
                       f"{e['assigned_user_id']} / {e['queue']}, SLA {e['sla_due_date']}, {e['status_as_of']}"
                       f"{' primary' if e['is_primary'] == 'true' else ''}")
    out.append("Line match:")
    for m in read_table(processed, "match_result"):
        if m["invoice_id"] == invoice_id:
            out.append(f"  {m['invoice_line_id']} -> {m['po_line_id'] or '-'}: price {m['price_status']} "
                       f"({m['invoice_unit_price'] or '-'} vs {m['po_unit_price'] or '-'}, {m['price_variance_pct'] or '-'}%), "
                       f"qty {m['qty_status']} (billed {m['invoiced_qty'] or '-'}, prior {m['prior_invoiced_qty'] or '-'}, "
                       f"received {m['received_qty'] or '-'}, max {m['max_qty_vs_po'] or '-'}), tax {m['tax_status']} "
                       f"=> {m['line_match_status']}")
    allocs = [a for a in read_table(processed, "match_allocation") if a["invoice_line_id"].startswith(f"INVL-{invoice_id}-")]
    for a in allocs:
        out.append(f"  bridge {a['allocation_id']}: {a['invoice_line_id']} <- {a['grn_line_id']} qty {a['allocated_qty']}")
    out.append("Approvals and payment:")
    for a in read_table(processed, "approval"):
        if a["invoice_id"] == invoice_id:
            out.append(f"  {a['approval_id']} {a['level']} by {a['approver_role']} {a['approver_user_id']}: requested "
                       f"{a['requested_at']}, {a['status_as_of']} {a['decided_at']}")
    for p in read_table(processed, "payment"):
        if p["invoice_id"] == invoice_id:
            out.append(f"  {p['payment_id']} {p['amount']} {p['payment_method']} due {p['due_date']} scheduled "
                       f"{p['scheduled_date']} -> {p['status_as_of']} {p['paid_at']}")
    out.append("Event log:")
    for e in read_table(processed, "ap_event"):
        if e["invoice_id"] == invoice_id:
            out.append(f"  {e['event_at']} {e['entity_type']} {e['entity_id']}: {e['from_status'] or '-'} -> "
                       f"{e['to_status']} by {e['actor_role']} {e['actor_id']} [{e['rule_id'] or '-'}] {e['reason'] or ''}")
    out.append("Decision trace:")
    with open(processed / "decision_trace.jsonl", encoding="utf-8") as fh:
        for line in fh:
            t = json.loads(line)
            if t["invoice_id"] == invoice_id:
                out.append(f"  {t['rule_id']}: {json.dumps(t['inputs'], sort_keys=True)} -> "
                           f"{json.dumps(t['outcome'], sort_keys=True)}")
    return "\n".join(out) + "\n"
