"""Extracted values with provenance: raw text, normalised value, method and confidence (ADR-032).

Confidence is fixed per method (calibrated in Stage 3, reported by the extraction evaluation):
a structured or segment read is near-certain; a label read is high; an OCR repair or a conflicting
read is below the CAP-01 threshold (0.90), so the document goes to capture review.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

D = Decimal
CONFIDENCE = {
    "STRUCTURED": D("1.00"),     # portal JSON key
    "SEGMENT": D("0.99"),        # EDI segment position
    "LABEL_EXACT": D("0.98"),    # canonical label
    "PATTERN": D("0.97"),        # layout or pattern rule (letterhead name, block number, currency marker)
    "LABEL_SYNONYM": D("0.95"),  # known synonym of the label
    "OCR_REPAIRED": D("0.60"),   # look-alike characters repaired: plausible, never trusted
    "NOT_FOUND": D("0.00"),      # absent or unreadable
}
CONFLICT = D("0.50")             # the same field read twice with different values
PRECISION = D("0.80")            # a quantity printed with more decimals than its unit allows


@dataclass
class Extracted:
    raw: str | None
    value: object | None
    method: str
    confidence: Decimal

    @property
    def found(self) -> bool:
        return self.method != "NOT_FOUND"


def make(raw: str | None, value, method: str) -> Extracted:
    """value None with a raw text means the text was found but could not be read."""
    if value is None and raw not in (None, "-", ""):
        return Extracted(raw, None, "NOT_FOUND", CONFIDENCE["NOT_FOUND"])
    return Extracted(raw, value, method, CONFIDENCE[method])


def missing() -> Extracted:
    return Extracted(None, None, "NOT_FOUND", CONFIDENCE["NOT_FOUND"])


HEADER_FIELDS = ("vendor_name", "vendor_tax_id", "vendor_invoice_number", "invoice_date", "po_number",
                 "attention_user_id", "currency", "header_net_amount", "header_tax_amount", "header_gross_amount")
HEADER_REQUIRED = ("vendor_name", "vendor_tax_id", "vendor_invoice_number", "invoice_date", "currency",
                   "header_net_amount", "header_tax_amount", "header_gross_amount")
LINE_FIELDS = ("line_number", "po_line_number", "sku_id", "description", "uom", "quantity", "unit_price",
               "line_net_amount", "tax_code", "tax_amount")
LINE_REQUIRED = ("line_number", "description", "uom", "quantity", "unit_price", "line_net_amount", "tax_code",
                 "tax_amount")


@dataclass
class RawCapture:
    """What a channel adapter read from one document, before vendor resolution."""
    header: dict[str, Extracted]
    lines: list[dict[str, Extracted]]
    line_items: Extracted          # the line-item block as a whole (NOT_FOUND or conflicting -> flagged)
