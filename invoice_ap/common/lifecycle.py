"""Documented lifecycle state machines for every stateful entity.

The generator (ERP events), the engine (AP events) and the validation suite all use this one
definition; docs/schema.md renders it. A creation event has from_status None. Transitions marked
"(not simulated)" are legal in the model but the deterministic simulation never produces them,
because no rule in the policy triggers them (see ADR-011).
"""
from __future__ import annotations

TRANSITIONS: dict[str, dict[tuple[str | None, str], str]] = {
    "VENDOR": {
        (None, "ACTIVE"): "ONBOARDED by the system administrator (effective = onboarded_date)",
        ("ACTIVE", "BLOCKED"): "KYC_DOCUMENTS_EXPIRED (system administrator)",
        ("BLOCKED", "ACTIVE"): "KYC_RENEWED (system administrator)",
        ("ACTIVE", "CLOSED"): "RELATIONSHIP_ENDED (system administrator)",
        ("BLOCKED", "CLOSED"): "RELATIONSHIP_ENDED (system administrator)",
    },
    "PURCHASE_ORDER": {
        (None, "ISSUED"): "PO_ISSUED by the business requester",
        ("ISSUED", "PARTIALLY_RECEIVED"): "GOODS_RECEIVED: some ordered quantity still open",
        ("ISSUED", "RECEIVED"): "GOODS_RECEIVED: every line received in full or over",
        ("PARTIALLY_RECEIVED", "RECEIVED"): "GOODS_RECEIVED: remaining quantity received",
    },
    "GOODS_RECEIPT": {
        (None, "POSTED"): "GRN_POSTED by the business requester who confirmed the receipt",
    },
    "INVOICE": {
        (None, "RECEIVED"): "intake registers the document (SYSTEM)",
        ("RECEIVED", "CAPTURED"): "CAP-01 extraction finished (SYSTEM)",
        ("CAPTURED", "ON_HOLD"): "at least one blocking exception is open (SYSTEM)",
        ("CAPTURED", "REJECTED"): "DUP-01 exact resubmission (SYSTEM)",
        ("CAPTURED", "PENDING_APPROVAL"): "every check passed; APR-01 chain requested (SYSTEM)",
        ("PENDING_APPROVAL", "APPROVED"): "the last required approval level approved",
        ("PENDING_APPROVAL", "REJECTED"): "an approver rejects (not simulated)",
        ("APPROVED", "PAYMENT_READY"): "PAY-01 satisfied and payment scheduled (SYSTEM)",
        ("APPROVED", "ON_HOLD"): "PAY-03 vendor not payable on the ready date (SYSTEM)",
        ("ON_HOLD", "PENDING_APPROVAL"): "blocking exceptions resolved by their owners (not simulated)",
        ("ON_HOLD", "REJECTED"): "rejected after review (not simulated)",
        ("PAYMENT_READY", "PAID"): "PAY-05 payment run releases the payment (SYSTEM)",
    },
    "EXCEPTION": {
        (None, "OPEN"): "raised and routed by RTE-01 (SYSTEM)",
        ("OPEN", "CLOSED"): "auto-closed when the invoice is REJECTED, or resolved by its owner",
    },
    "APPROVAL": {
        (None, "PENDING"): "requested in sequence (SYSTEM)",
        ("PENDING", "APPROVED"): "approver decides after the level's turnaround (APR-SIM-01); AUTO at once",
        ("PENDING", "REJECTED"): "approver rejects (not simulated)",
    },
    "PAYMENT": {
        (None, "SCHEDULED"): "PAY-01 and PAY-02 (SYSTEM)",
        ("SCHEDULED", "PAID"): "PAY-05 payment run on the scheduled date, on or before the as-of date (SYSTEM)",
    },
}

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
