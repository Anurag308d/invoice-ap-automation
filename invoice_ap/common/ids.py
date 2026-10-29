"""Deterministic identifier formats.

Assignment conventions: VND-00001, PO-2026-000001, GRN-2026-000001,
INV-<vendor-code>-2026-000001 and INVL-<invoice-id>-01. Decision ADR-002: <vendor-code> is the
vendor_id itself, so INV-VND-00001-2026-000001 embeds a machine-checkable vendor reference.
Counters are zero-padded, never reused, and IDs are immutable once assigned.
"""
from __future__ import annotations

import re

YEAR = 2026  # fiscal/document year embedded in transactional IDs (ADR-004)

PATTERNS: dict[str, str] = {
    "vendor_id": r"^VND-\d{5}$",
    "sku_id": r"^SKU-\d{5}$",
    "user_id": r"^USR-\d{4}$",
    "vsh_id": r"^VSH-\d{6}$",
    "po_id": rf"^PO-{YEAR}-\d{{6}}$",
    "po_line_id": rf"^POL-PO-{YEAR}-\d{{6}}-\d{{2}}$",
    "grn_id": rf"^GRN-{YEAR}-\d{{6}}$",
    "grn_line_id": rf"^GRNL-GRN-{YEAR}-\d{{6}}-\d{{2}}$",
    "invoice_id": rf"^INV-VND-\d{{5}}-{YEAR}-\d{{6}}$",
    "invoice_line_id": rf"^INVL-INV-VND-\d{{5}}-{YEAR}-\d{{6}}-\d{{2}}$",
    "doc_id": rf"^DOC-{YEAR}-\d{{6}}$",
    "erp_event_id": rf"^ERP-{YEAR}-\d{{6}}$",
    "ap_event_id": rf"^EVT-{YEAR}-\d{{6}}$",
    "exception_id": rf"^EXC-{YEAR}-\d{{6}}$",
    "approval_id": rf"^APR-{YEAR}-\d{{6}}$",
    "payment_id": rf"^PAY-{YEAR}-\d{{6}}$",
    "allocation_id": rf"^ALC-{YEAR}-\d{{6}}$",
    "duplicate_pair_id": rf"^DUP-{YEAR}-\d{{6}}$",
    "extraction_field_id": rf"^EXF-{YEAR}-\d{{6}}$",
}
_COMPILED = {name: re.compile(p) for name, p in PATTERNS.items()}


def matches(kind: str, value: str) -> bool:
    """True when value has the documented format for ID kind."""
    return bool(_COMPILED[kind].match(value or ""))


def _counter(n: int, width: int) -> str:
    if not isinstance(n, int) or n < 1 or n >= 10**width:
        raise ValueError(f"counter {n!r} outside 1..{10**width - 1}")
    return f"{n:0{width}d}"


def vendor_id(n: int) -> str:
    return f"VND-{_counter(n, 5)}"


def sku_id(n: int) -> str:
    return f"SKU-{_counter(n, 5)}"


def user_id(n: int) -> str:
    return f"USR-{_counter(n, 4)}"


def vsh_id(n: int) -> str:
    return f"VSH-{_counter(n, 6)}"


def _yearly(prefix: str, n: int) -> str:
    return f"{prefix}-{YEAR}-{_counter(n, 6)}"


def po_id(n: int) -> str:
    return _yearly("PO", n)


def grn_id(n: int) -> str:
    return _yearly("GRN", n)


def doc_id(n: int) -> str:
    return _yearly("DOC", n)


def erp_event_id(n: int) -> str:
    return _yearly("ERP", n)


def ap_event_id(n: int) -> str:
    return _yearly("EVT", n)


def exception_id(n: int) -> str:
    return _yearly("EXC", n)


def approval_id(n: int) -> str:
    return _yearly("APR", n)


def payment_id(n: int) -> str:
    return _yearly("PAY", n)


def allocation_id(n: int) -> str:
    return _yearly("ALC", n)


def duplicate_pair_id(n: int) -> str:
    return _yearly("DUP", n)


def extraction_field_id(n: int) -> str:
    return _yearly("EXF", n)


def po_line_id(po: str, line_no: int) -> str:
    return f"POL-{po}-{_counter(line_no, 2)}"


def grn_line_id(grn: str, line_no: int) -> str:
    return f"GRNL-{grn}-{_counter(line_no, 2)}"


def invoice_id(vendor: str, seq: int) -> str:
    """Global intake-order counter (ADR-003); the vendor code segment is the vendor_id."""
    if not matches("vendor_id", vendor):
        raise ValueError(f"bad vendor id {vendor!r}")
    return f"INV-{vendor}-{YEAR}-{_counter(seq, 6)}"


def invoice_line_id(invoice: str, line_no: int) -> str:
    return f"INVL-{invoice}-{_counter(line_no, 2)}"


def vendor_of_invoice(invoice: str) -> str:
    """Return the vendor_id embedded in an invoice_id (used by referential checks)."""
    if not matches("invoice_id", invoice):
        raise ValueError(f"bad invoice id {invoice!r}")
    return invoice[4:13]


def parent_of_line(line_id: str) -> str:
    """POL-/GRNL-/INVL- ids embed their parent id; strip the prefix and the 2-digit suffix."""
    prefix, _, rest = line_id.partition("-")
    if prefix not in {"POL", "GRNL", "INVL"} or len(rest) < 4:
        raise ValueError(f"not a line id: {line_id!r}")
    return rest[:-3]
