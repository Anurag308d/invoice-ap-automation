"""Documented lifecycle state machines for every stateful entity.

The generator (ERP events), the engine (AP events) and the validation suite all use this one
definition; docs/schema.md renders it. A creation event has from_status None. Each transition has
a short diagram label (complete words, never truncated), the full trigger description, and a flag
for transitions that are legal but never produced by the deterministic simulation, because no
policy rule triggers them (ADR-011).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Transition:
    label: str
    detail: str
    simulated: bool = True


T = Transition
TRANSITIONS: dict[str, dict[tuple[str | None, str], Transition]] = {
    "VENDOR": {
        (None, "ACTIVE"): T("ONBOARDED", "system administrator onboards the vendor; effective = onboarded_date"),
        ("ACTIVE", "BLOCKED"): T("KYC_DOCUMENTS_EXPIRED", "system administrator blocks the vendor"),
        ("BLOCKED", "ACTIVE"): T("KYC_RENEWED", "system administrator reinstates the vendor"),
        ("ACTIVE", "CLOSED"): T("RELATIONSHIP_ENDED", "system administrator closes the vendor"),
        ("BLOCKED", "CLOSED"): T("RELATIONSHIP_ENDED", "system administrator closes a blocked vendor"),
    },
    "PURCHASE_ORDER": {
        (None, "ISSUED"): T("PO_ISSUED", "business requester raises and issues the PO"),
        ("ISSUED", "PARTIALLY_RECEIVED"): T("GOODS_RECEIVED partly", "a GRN leaves some ordered quantity open"),
        ("ISSUED", "RECEIVED"): T("GOODS_RECEIVED in full", "a GRN receives every line in full or over"),
        ("PARTIALLY_RECEIVED", "RECEIVED"): T("GOODS_RECEIVED rest", "a later GRN receives the remaining quantity"),
    },
    "GOODS_RECEIPT": {
        (None, "POSTED"): T("GRN_POSTED", "the business requester who confirmed the receipt posts the GRN"),
    },
    "INVOICE": {
        (None, "RECEIVED"): T("intake registers document", "intake registers the document (SYSTEM)"),
        ("RECEIVED", "CAPTURED"): T("CAP-01 extraction done", "extraction finished and ID-01 assigned the invoice ID (SYSTEM)"),
        ("CAPTURED", "ON_HOLD"): T("blocking exception open", "at least one blocking exception is open (SYSTEM)"),
        ("CAPTURED", "REJECTED"): T("DUP-01 exact duplicate", "exact resubmission of an earlier invoice (SYSTEM)"),
        ("CAPTURED", "PENDING_APPROVAL"): T("all checks passed", "APR-01 approval chain requested (SYSTEM)"),
        ("PENDING_APPROVAL", "APPROVED"): T("last level approved", "the last required approval level approved"),
        ("PENDING_APPROVAL", "REJECTED"): T("approver rejects", "an approver rejects the invoice", False),
        ("APPROVED", "PAYMENT_READY"): T("PAY-01 ready", "readiness satisfied and payment scheduled (SYSTEM)"),
        ("APPROVED", "ON_HOLD"): T("PAY-03 vendor not payable", "vendor not payable on the ready date (SYSTEM)"),
        ("ON_HOLD", "PENDING_APPROVAL"): T("exceptions resolved", "owners resolve every blocking exception", False),
        ("ON_HOLD", "REJECTED"): T("rejected after review", "rejected after the owner's review", False),
        ("PAYMENT_READY", "PAID"): T("PAY-05 payment run", "payment run releases the payment (SYSTEM)"),
    },
    "EXCEPTION": {
        (None, "OPEN"): T("raised and routed", "RTE-01 routes it to a role and queue (SYSTEM)"),
        ("OPEN", "CLOSED"): T("closed", "auto-closed when the invoice is REJECTED, or resolved by its owner"),
    },
    "APPROVAL": {
        (None, "PENDING"): T("requested", "requested in sequence (SYSTEM)"),
        ("PENDING", "APPROVED"): T("approved", "approver decides after the level's turnaround (APR-SIM-01); AUTO at once"),
        ("PENDING", "REJECTED"): T("rejected", "approver rejects", False),
    },
    "PAYMENT": {
        (None, "SCHEDULED"): T("PAY-02 scheduled", "payment created and scheduled (PAY-01, PAY-02; SYSTEM)"),
        ("SCHEDULED", "PAID"): T("PAY-05 released", "payment run on a scheduled date on or before the as-of date (SYSTEM)"),
    },
}
del T

TERMINAL: dict[str, tuple[str, ...]] = {
    "VENDOR": ("CLOSED",),
    "PURCHASE_ORDER": (),
    "GOODS_RECEIPT": (),
    "INVOICE": ("REJECTED", "PAID"),
    "EXCEPTION": ("CLOSED",),
    "APPROVAL": ("APPROVED", "REJECTED"),
    "PAYMENT": ("PAID",),
}


def is_allowed(entity: str, from_status: str | None, to_status: str) -> bool:
    return (from_status, to_status) in TRANSITIONS[entity]


def sequence_errors(entity: str, statuses: list[str]) -> list[str]:
    """Check an entity's ordered to_status sequence: creation first, then allowed transitions."""
    errors: list[str] = []
    previous: str | None = None
    for i, status in enumerate(statuses):
        if not is_allowed(entity, previous, status):
            errors.append(f"{entity}: step {i + 1} {previous} -> {status} is not allowed")
        previous = status
    return errors
