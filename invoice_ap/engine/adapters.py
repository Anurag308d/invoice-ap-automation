"""One adapter per intake channel: document bytes -> RawCapture. Adapters read only the document."""
from __future__ import annotations

import json
import re
from decimal import Decimal

from . import normalize as N
from .fields import CONFIDENCE, CONFLICT, Extracted, RawCapture, make, missing
from .read import read_value
from .textlayout import parse_text

FORWARD = re.compile(r"-{3,}\s*Forwarded message\s*-{3,}", re.IGNORECASE)


def _empty() -> RawCapture:
    return RawCapture({}, [], missing())


# ------------------------------------------------------------------ PORTAL_JSON
def _get(obj, *path):
    for key in path:
        if not isinstance(obj, dict) or key not in obj:
            return None
        obj = obj[key]
    return obj


def _structured(field: str, value, uom: str | None = None) -> Extracted:
    """A portal value: strings go through the field's format rule; v2 numbers are taken as printed."""
    if value is None:
        return missing()
    if isinstance(value, (int, Decimal)) and not isinstance(value, bool):
        number = N.to_decimal(value)
        if field in ("line_number", "po_line_number"):
            return make(str(value), int(number) if number == int(number) else None, "STRUCTURED")
        if field == "quantity":
            return read_value(field, f"{number:f}", "STRUCTURED", uom=uom)
        return make(str(value), number.quantize(Decimal("0.01")) if number == number.quantize(Decimal("0.01"))
                    else None, "STRUCTURED")
    if not isinstance(value, str):
        return make(json.dumps(value), None, "STRUCTURED")
    return read_value(field, value, "STRUCTURED", uom=uom)


PORTAL_MAPS = {
    "v1": {"header": {"vendor_name": ("supplier", "name"), "vendor_tax_id": ("supplier", "tax_registration_id"),
                      "vendor_invoice_number": ("invoice", "number"), "invoice_date": ("invoice", "date"),
                      "po_number": ("invoice", "po_number"), "attention_user_id": ("invoice", "attention"),
                      "currency": ("invoice", "currency"), "header_net_amount": ("invoice", "net_total"),
                      "header_tax_amount": ("invoice", "tax_total"),
                      "header_gross_amount": ("invoice", "grand_total")},
           "lines": "lines",
           "line": {"line_number": "line_no", "po_line_number": "po_line_no", "sku_id": "sku",
                    "description": "description", "uom": "uom", "quantity": "quantity", "unit_price": "unit_price",
                    "line_net_amount": "amount", "tax_code": "tax_code", "tax_amount": "tax_amount"}},
    "v2": {"header": {"vendor_name": ("vendor", "legalName"), "vendor_tax_id": ("vendor", "taxId"),
                      "vendor_invoice_number": ("header", "invoiceNo"), "invoice_date": ("header", "invoiceDate"),
                      "po_number": ("header", "purchaseOrder"), "attention_user_id": ("header", "requesterId"),
                      "currency": ("header", "currencyCode"), "header_net_amount": ("totals", "taxable"),
                      "header_tax_amount": ("totals", "tax"), "header_gross_amount": ("totals", "payable")},
           "lines": "items",
           "line": {"line_number": "seq", "po_line_number": "orderLine", "sku_id": "itemCode",
                    "description": "text", "uom": "unit", "quantity": "qty", "unit_price": "rate",
                    "line_net_amount": "value", "tax_code": "taxCode", "tax_amount": "taxValue"}},
}


def portal(data: bytes) -> RawCapture:
    try:
        obj = json.loads(data.decode("utf-8"), parse_float=Decimal)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return _empty()
    if not isinstance(obj, dict):
        return _empty()
    if str(obj.get("schema", "")) == "buyer-portal/invoice@1":
        spec = PORTAL_MAPS["v1"]
    elif str(obj.get("schemaVersion", "")) == "2.0":
        spec = PORTAL_MAPS["v2"]
    else:
        return _empty()                      # unknown schema: nothing is trusted
    header = {}
    for name, path in spec["header"].items():
        ext = _structured(name, _get(obj, *path))
        if ext.found or name in ("vendor_name", "vendor_tax_id", "vendor_invoice_number", "invoice_date",
                                 "currency", "header_net_amount", "header_tax_amount", "header_gross_amount"):
            header[name] = ext
    lines = []
    items = obj.get(spec["lines"])
    if not isinstance(items, list) or not items:
        return RawCapture(header, [], missing())
    for item in items:
        item = item if isinstance(item, dict) else {}
        uom = _structured("uom", item.get(spec["line"]["uom"]))
        row = {"uom": uom}
        for name, key in spec["line"].items():
            if name == "uom":
                continue
            ext = _structured(name, item.get(key), uom=uom.value)
            if ext.found or name not in ("po_line_number", "sku_id"):
                row[name] = ext
        lines.append(row)
    return RawCapture(header, lines, _count(lines, "STRUCTURED"))


def _count(lines: list[dict], method: str, declared: int | None = None) -> Extracted:
    numbers = [r["line_number"].value for r in lines if "line_number" in r]
    ok = (len(numbers) == len(lines) and None not in numbers and len(set(numbers)) == len(numbers)
          and (declared is None or declared == len(lines)))
    return Extracted(f"{len(lines)} lines", len(lines), method, CONFIDENCE[method] if ok else CONFLICT)


# ------------------------------------------------------------------ EDI_FLAT
EDI_LINE = ("line_number", "sku_id", "po_line_number", "uom", "quantity", "unit_price", "line_net_amount",
            "tax_code", "tax_amount")


def edi(data: bytes) -> RawCapture:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return _empty()
    if not text.startswith("UNB") or len(text) < 4:
        return _empty()
    sep = text[3]
    segments = [s.strip() for s in (text.split("~") if "~" in text else text.splitlines())]
    segments = [s.split(sep) for s in segments if s]
    unb = segments[0]
    mode = unb[2] if len(unb) > 2 else ""
    if mode not in ("DEC", "IMP2"):
        return _empty()                      # unknown amount mode: amounts cannot be read safely
    implied = mode == "IMP2"
    header: dict[str, Extracted] = {}
    lines: dict[str, dict] = {}
    order: list[str] = []
    declared = None

    def put(name, raw, uom=None, target=None):
        ext = read_value(name, raw, "SEGMENT", uom=uom, implied=implied and name in (
            "header_net_amount", "header_tax_amount", "header_gross_amount", "unit_price", "line_net_amount",
            "tax_amount"))
        (target if target is not None else header)[name] = ext
    for seg in segments[1:]:
        tag, el = seg[0], seg[1:]
        if tag == "NAD" and len(el) >= 3 and el[0] == "SU":
            put("vendor_tax_id", el[1])
            put("vendor_name", sep.join(el[2:]))
        elif tag == "BGM" and len(el) >= 3:
            put("vendor_invoice_number", el[1])
            put("invoice_date", el[2])
        elif tag == "CUX" and el:
            put("currency", el[0])
        elif tag == "RFF" and len(el) >= 2 and el[0] in ("ON", "ATT"):
            put("po_number" if el[0] == "ON" else "attention_user_id", el[1])
        elif tag == "LIN":
            values = dict(zip(EDI_LINE, el))
            key = values.get("line_number", "")
            row = lines.setdefault(key, {})
            order.append(key)
            uom = N.uom(values.get("uom", ""))
            for name in EDI_LINE:
                raw = values.get(name)
                if name in ("sku_id", "po_line_number") and not raw:
                    continue
                put(name, raw, uom=uom, target=row)
        elif tag == "IMD" and len(el) >= 2:
            put("description", sep.join(el[1:]), target=lines.setdefault(el[0], {}))
        elif tag == "MOA" and len(el) >= 2:
            name = {"125": "header_net_amount", "124": "header_tax_amount", "77": "header_gross_amount"}.get(el[0])
            if name:
                put(name, el[1])
        elif tag == "CNT" and len(el) >= 2 and el[0] == "2":
            declared = N.integer(el[1])
    for name in ("vendor_name", "vendor_tax_id", "vendor_invoice_number", "invoice_date", "currency",
                 "header_net_amount", "header_tax_amount", "header_gross_amount"):
        header.setdefault(name, missing())
    rows = [lines[k] for k in dict.fromkeys(order)]
    if len(order) != len(set(order)) or set(lines) - set(order):
        declared = -1                        # repeated LIN, or a description without its line
    for r in rows:
        r.setdefault("description", missing())
    return RawCapture(header, rows, _count(rows, "SEGMENT", declared) if rows else missing())


# ------------------------------------------------------------------ EMAIL_TEXT and OCR_TEXT
def _decode(data: bytes) -> str | None:
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def email(data: bytes) -> RawCapture:
    """RFC 822 headers are transport metadata, never invoice content; a forwarded-message header block
    inside the body is skipped the same way (its Date/From lines are not the invoice's)."""
    text = _decode(data)
    if text is None:
        return _empty()
    lines = text.split("\n")
    body = lines[lines.index("") + 1:] if "" in lines else []
    out, skipping = [], False
    for line in body:
        if FORWARD.fullmatch(line.strip()):
            skipping = True
            continue
        if skipping:
            if not line.strip():
                skipping = False
            continue
        out.append(line)
    return parse_text(out)


def scan(data: bytes) -> RawCapture:
    text = _decode(data)
    return parse_text(text.split("\n")) if text is not None else _empty()


ADAPTERS = {"PORTAL_JSON": portal, "EDI_FLAT": edi, "EMAIL_TEXT": email, "OCR_TEXT": scan}
