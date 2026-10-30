"""Read one printed value into an `Extracted` field, using only that field's format rule."""
from __future__ import annotations

from . import normalize as N
from .fields import CONFIDENCE, PRECISION, Extracted, make

OPTIONAL_DASH = ("po_line_number", "sku_id")        # a printed "-" means "none" for these cells
REPAIRABLE = ("invoice_date", "header_net_amount", "header_tax_amount", "header_gross_amount", "line_number",
              "po_line_number", "quantity", "unit_price", "line_net_amount", "tax_amount")
AMOUNTS = ("header_net_amount", "header_tax_amount", "header_gross_amount", "unit_price", "line_net_amount",
           "tax_amount")


def _parse(field: str, raw: str, uom: str | None, implied: bool):
    """(value, precision_ok); value None when unreadable."""
    if field in AMOUNTS:
        return N.amount(raw, implied), True
    if field == "quantity":
        return N.quantity(raw, uom)
    simple = {"vendor_name": lambda s: s.strip() or None, "vendor_tax_id": N.trn,
              "vendor_invoice_number": N.invoice_number, "invoice_date": N.invoice_date,
              "po_number": N.po_reference, "attention_user_id": N.user_reference, "currency": N.currency,
              "line_number": N.integer, "po_line_number": N.integer, "sku_id": N.sku,
              "description": lambda s: s.strip() or None, "uom": N.uom, "tax_code": N.tax_code}
    return simple[field](raw), True


def read_value(field: str, raw: str | None, method: str, uom: str | None = None, implied: bool = False) -> Extracted:
    if raw is None:
        return make(None, None, "NOT_FOUND")
    raw = raw.strip()
    if field in OPTIONAL_DASH and raw in ("-", ""):
        return Extracted(raw, None, method, CONFIDENCE[method])
    value, precise = _parse(field, raw, uom, implied)
    if value is None and field in REPAIRABLE:
        repaired = N.repair(raw)
        if repaired != raw:
            value, precise = _parse(field, repaired, uom, implied)
            if value is not None:
                return Extracted(raw, value, "OCR_REPAIRED", CONFIDENCE["OCR_REPAIRED"])
    result = make(raw, value, method)
    if value is not None and not precise:
        result.confidence = min(result.confidence, PRECISION)
    return result
