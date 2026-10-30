"""VEN-01 vendor resolution, ID-01 invoice ID assignment and the VEN-04 sender cross-check (ADR-037).

The vendor comes only from the tax registration number printed on the document. The invoice ID is
an output of that resolution. The channel's authenticated sender (PORTAL and EDI only) is read here
and nowhere else in the engine, and only to cross-check the resolved vendor: it never fills a gap.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..common import ids


@dataclass
class Identity:
    vendor_id: str | None              # VEN-01 result (None = not found)
    invoice_id: str                    # ID-01
    sender_checked: bool               # VEN-04 evaluated (authenticated channel with a sender on record)
    sender_mismatch: bool
    sender_vendor: str | None          # the authenticated sender, for the exception's expected value


def resolve(printed_tax_id: str | None, intake_seq: int, manifest_row: dict[str, str],
            vendors_by_tax_id: dict[str, str], sender_channels: tuple[str, ...]) -> Identity:
    vendor = vendors_by_tax_id.get(printed_tax_id) if printed_tax_id else None
    invoice_id = ids.invoice_id(vendor or ids.UNRESOLVED_VENDOR, intake_seq)
    sender = manifest_row.get("sender_vendor_id") or None
    checked = manifest_row["channel"] in sender_channels and sender is not None and vendor is not None
    return Identity(vendor, invoice_id, checked, checked and sender != vendor, sender if checked else None)
