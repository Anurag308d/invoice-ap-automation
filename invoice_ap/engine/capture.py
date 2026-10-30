"""CAP-01: turn a RawCapture into captured_invoice, captured_invoice_line and extraction_field rows.

Printed values are copied as read; nothing is recomputed or corrected (ADR-032). References are
resolved against master data only to the extent of "does this ID exist": the printed PO number
becomes po_id when that PO exists, and the printed PO line number becomes po_line_id when that line
exists on it. Whether the PO belongs to the vendor is a later rule (PO-02).
"""
from __future__ import annotations

import re
from datetime import date
from decimal import Decimal

from ..common import ids
from .fields import HEADER_REQUIRED, LINE_REQUIRED, Extracted, RawCapture, missing


def dup_number(number: str | None) -> str:
    """DUP normalisation: upper case, split on non-alphanumerics, strip leading zeros of numeric tokens."""
    if not number:
        return ""
    tokens = [t for t in re.split(r"[^A-Z0-9]+", number.upper()) if t]
    return "".join(str(int(t)) if t.isdigit() else t for t in tokens)


def text_of(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return f"{value:f}"
    return str(value)


def confidence_floor(raw: RawCapture) -> Decimal:
    """Lowest confidence over the required fields, every optional field that was printed, and the
    line-item block. A required field that is absent counts as 0.00."""
    values = [raw.header.get(f, missing()).confidence for f in HEADER_REQUIRED]
    values += [e.confidence for k, e in raw.header.items() if k not in HEADER_REQUIRED]
    values.append(raw.line_items.confidence)
    for row in raw.lines:
        values += [row.get(f, missing()).confidence for f in LINE_REQUIRED]
        values += [e.confidence for k, e in row.items() if k not in LINE_REQUIRED]
    return min(values)


def _v(ext: Extracted | None):
    return ext.value if ext is not None else None


def build_rows(raw: RawCapture, manifest: dict, invoice_id: str, vendor_id: str | None, captured_at,
               threshold: Decimal, po_ids: set[str], po_line_ids: set[str], user_ids: set[str]):
    h = raw.header
    floor = confidence_floor(raw)
    po_number = h.get("po_number")
    po_id = _v(po_number) if _v(po_number) in po_ids else None
    attention = _v(h.get("attention_user_id"))
    invoice = {
        "invoice_id": invoice_id, "doc_id": manifest["doc_id"], "channel": manifest["channel"],
        "captured_at": captured_at, "capture_status": "LOW_CONFIDENCE" if floor < threshold else "OK",
        "min_field_confidence": floor,
        "vendor_name": _v(h.get("vendor_name")) or "",
        "vendor_tax_id": _v(h.get("vendor_tax_id")) or (h["vendor_tax_id"].raw if h.get("vendor_tax_id") else "") or "",
        "vendor_id": vendor_id,
        "vendor_invoice_number": _v(h.get("vendor_invoice_number")),
        "normalized_invoice_number": dup_number(_v(h.get("vendor_invoice_number"))),
        "invoice_date": _v(h.get("invoice_date")),
        "po_number": po_number.raw if po_number is not None else None,
        "po_id": po_id,
        "attention_user_id": attention if attention in user_ids else None,
        "currency": _v(h.get("currency")) or "INR",
        "header_net_amount": _v(h.get("header_net_amount")),
        "header_tax_amount": _v(h.get("header_tax_amount")),
        "header_gross_amount": _v(h.get("header_gross_amount")),
        "line_count": len(raw.lines)}
    lines, fields = [], []
    numbers = [_v(r.get("line_number")) for r in raw.lines]
    positional = len(set(numbers)) != len(numbers) or None in numbers
    for pos, row in enumerate(raw.lines, start=1):
        number = pos if positional else numbers[pos - 1]
        line_id = ids.invoice_line_id(invoice_id, number)
        po_line_no = _v(row.get("po_line_number"))
        candidate = ids.po_line_id(po_id, po_line_no) if po_id and po_line_no else None
        lines.append({
            "invoice_line_id": line_id, "invoice_id": invoice_id, "line_number": number,
            "po_line_number": po_line_no, "po_line_id": candidate if candidate in po_line_ids else None,
            "sku_id": _v(row.get("sku_id")), "description": _v(row.get("description")) or "",
            "uom": _v(row.get("uom")) or "", "quantity": _v(row.get("quantity")), "unit_price": _v(row.get("unit_price")),
            "line_net_amount": _v(row.get("line_net_amount")), "tax_code": _v(row.get("tax_code")) or "",
            "tax_amount": _v(row.get("tax_amount")),
            "min_field_confidence": min([row.get(f, missing()).confidence for f in LINE_REQUIRED]
                                        + [e.confidence for k, e in row.items() if k not in LINE_REQUIRED])})
        fields += [(line_id, name, ext) for name, ext in row.items()]
    header_fields = [(None, name, ext) for name, ext in sorted(raw.header.items(), key=lambda kv: kv[0])]
    header_fields += [(None, name, missing()) for name in HEADER_REQUIRED if name not in raw.header]
    header_fields.append((None, "line_items", raw.line_items))
    return invoice, lines, header_fields + fields


def field_row(n: int, doc_id: str, invoice_id: str, line_id: str | None, name: str, ext: Extracted,
              threshold: Decimal) -> dict:
    return {"extraction_field_id": ids.extraction_field_id(n), "doc_id": doc_id, "invoice_id": invoice_id,
            "invoice_line_id": line_id, "field_name": name, "raw_text": ext.raw, "normalized_value": text_of(ext.value),
            "confidence": ext.confidence, "method": ext.method, "is_low_confidence": ext.confidence < threshold}
