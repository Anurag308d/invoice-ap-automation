"""Render every received document into its channel's file format (Stage 3, ADR-040).

Four heterogeneous formats, one per intake channel:
- PORTAL -> PORTAL_JSON: the buyer portal's JSON (schema v1 snake_case strings, v2 camelCase with
  numeric amounts);
- EDI    -> EDI_FLAT: segment file whose separator, terminator and amount mode (decimal or implied
  two decimals) vary by trading partner;
- EMAIL  -> EMAIL_TEXT: an RFC 822 message whose plain-text body follows the vendor's template,
  optionally forwarded by an internal mailbox;
- SCAN   -> OCR_TEXT: the OCR text of a scanned paper invoice (upper-case labels, two label pairs per
  line, fixed-width tables that break across pages).

Each vendor has one template per channel (labels, date format, amount style, tax-code style, table
style, PO style), drawn once from a seeded stream. All variation is recoverable by the documented
label synonyms and format rules, except the CAPTURE_REVIEW scans, where one required header field is
unreadable (smudged, or printed with OCR look-alike characters).

Documents never contain scenario codes, categories or label words; they print only what a real
invoice would print. Rendering draws only from its own streams, so it never shifts any other draw.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from .rng import stream
from .tables import Dataset, Doc

MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
          "November", "December")
WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
CITIES = ("Pune 411019", "Chennai 600058", "Ahmedabad 382445", "Lucknow 226010", "Nagpur 440016",
          "Coimbatore 641021", "Faridabad 121003", "Vadodara 390010", "Indore 452015", "Hosur 635126")
BUYER = "Bill To: YF Components Manufacturing Pvt Ltd, Plant 2, Pune 411026"

# Vendor-side label variants (what vendors print). The engine has its own, independent synonym list.
LABELS = {
    "supplier": ("Supplier", "Vendor", "Seller", None),                 # None = letterhead without label
    "tax_id": ("TRN", "Tax Reg No", "Tax Registration Number", "Tax Regn. No."),
    "number": ("Invoice No", "Invoice Number", "Inv #", "Bill No", "Tax Invoice No"),
    "date": ("Invoice Date", "Date", "Inv Date", "Bill Date", "Dated"),
    "po": ("PO Number", "PO No", "Purchase Order", "Your Order Ref", "P.O. #"),
    "attention": ("Attention", "Attn", "Kind Attn", "Requested By"),
    "net": ("Subtotal", "Taxable Value", "Net Amount", "Total Before Tax"),
    "tax": ("Tax", "GST", "Total Tax", "Tax Amount"),
    "gross": ("Total", "Grand Total", "Invoice Total", "Amount Payable", "Total Amount Due"),
}
COLUMNS = {
    "line": ("#", "Sr", "S.No", "Line"),
    "po_line": ("PO Ln", "PO Line", "Order Line"),
    "sku": ("Item Code", "SKU", "Item"),
    "description": ("Description", "Particulars", "Item Description"),
    "uom": ("UOM", "Unit"),
    "qty": ("Qty", "Quantity"),
    "price": ("Rate", "Unit Price", "Price"),
    "amount": ("Amount", "Taxable Amt", "Value"),
    "tax_code": ("Tax Code", "GST Rate", "Tax Rate"),
    "tax": ("Tax Amt", "GST Amt", "Tax"),
}
DATE_FORMATS = ("iso", "dmy_slash", "dmy_dash", "dmy_dot", "d_mon_y", "d-mon-y", "month_d_y")
AMOUNT_STYLES = ("plain", "western", "indian")
CURRENCY_STYLES = ("code", "rs", "symbol", "line")
LOOKALIKE = {"0": "O", "1": "l", "5": "S", "8": "B", "2": "Z"}
SMUDGE = "?#~"
SCAN_ROWS_PER_PAGE = 2      # the letterhead fills most of a scanned first page


@dataclass(frozen=True)
class TextTemplate:
    labels: dict
    columns: dict
    date_format: str
    amount_style: str
    currency_style: str
    tax_style: str           # "code" (GST18) | "rate" (18%) | "spaced" (GST 18%)
    table: str               # "pipe" | "columns" | "block"
    po_style: str            # "dash" | "slash" | "space"
    sep: str                 # separator between label and value
    upper: bool              # upper-case labels (scans)
    pairs: bool              # two label pairs on one meta line (scans)
    city: str


@dataclass(frozen=True)
class EdiTemplate:
    sep: str
    terminator: str
    implied: bool            # amounts with two implied decimals


# ------------------------------------------------------------------ formatting
def fmt_date(d: date, style: str) -> str:
    return {"iso": d.isoformat(), "dmy_slash": f"{d.day:02d}/{d.month:02d}/{d.year}",
            "dmy_dash": f"{d.day:02d}-{d.month:02d}-{d.year}", "dmy_dot": f"{d.day:02d}.{d.month:02d}.{d.year}",
            "d_mon_y": f"{d.day:02d} {MONTHS[d.month - 1][:3]} {d.year}",
            "d-mon-y": f"{d.day:02d}-{MONTHS[d.month - 1][:3]}-{d.year}",
            "month_d_y": f"{MONTHS[d.month - 1]} {d.day:02d}, {d.year}"}[style]


def fmt_amount(v: Decimal, style: str) -> str:
    whole, frac = f"{v:.2f}".split(".")
    sign = "-" if whole.startswith("-") else ""
    whole = whole.lstrip("-")
    if style == "western":
        groups = []
        while len(whole) > 3:
            groups.insert(0, whole[-3:])
            whole = whole[:-3]
        whole = ",".join([whole] + groups)
    elif style == "indian" and len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        whole = ",".join([head] + groups + [tail])
    return f"{sign}{whole}.{frac}"


def fmt_money(v: Decimal, t: TextTemplate) -> str:
    s = fmt_amount(v, t.amount_style)
    return {"code": f"INR {s}", "rs": f"Rs. {s}", "symbol": f"₹{s}", "line": s}[t.currency_style]


def fmt_tax_code(code: str, style: str) -> str:
    if code == "EXEMPT":
        return "EXEMPT" if style == "code" else "Exempt"
    rate = code[3:]
    return {"code": code, "rate": f"{rate}%", "spaced": f"GST {rate}%"}[style]


def fmt_po(po_id: str, style: str) -> str:
    _, year, num = po_id.split("-")
    return {"dash": po_id, "slash": f"PO/{year}/{num}", "space": f"PO {year}-{num}"}[style]


def po_line_number(po_line_id: str | None) -> str:
    return str(int(po_line_id.rsplit("-", 1)[1])) if po_line_id else ""


def _rfc2822(at: datetime) -> str:
    return (f"{WEEKDAYS[at.weekday()]}, {at.day:02d} {MONTHS[at.month - 1][:3]} {at.year} "
            f"{at:%H:%M:%S} +0530")


# ------------------------------------------------------------------ templates
def _pick(rng, items):
    return items[rng.randrange(len(items))]


def _text_template(rng, scan: bool) -> TextTemplate:
    labels = {k: _pick(rng, v) for k, v in LABELS.items()}
    columns = {k: _pick(rng, v) for k, v in COLUMNS.items()}
    return TextTemplate(
        labels=labels, columns=columns, date_format=_pick(rng, DATE_FORMATS),
        amount_style=_pick(rng, AMOUNT_STYLES), currency_style=_pick(rng, CURRENCY_STYLES),
        tax_style=_pick(rng, ("code", "rate", "spaced")),
        table=_pick(rng, ("columns", "columns", "block")) if scan else _pick(rng, ("pipe", "columns", "block")),
        po_style=_pick(rng, ("dash", "slash", "space")),
        sep=_pick(rng, (": ", " : ", "  ")) if scan else _pick(rng, (": ", " : ", ":  ")),
        upper=scan and rng.randrange(3) > 0, pairs=scan and rng.randrange(2) == 0, city=_pick(rng, CITIES))


def build_templates(world) -> dict[tuple[str, str], object]:
    """One template per (vendor, channel), drawn in vendor-id order from a dedicated stream."""
    rng = stream(world.seed, "doc-templates")
    out: dict[tuple[str, str], object] = {}
    for v in sorted(world.vendors, key=lambda v: v.vendor_id):
        out[(v.vendor_id, "PORTAL")] = _pick(rng, ("v1", "v2"))
        out[(v.vendor_id, "EDI")] = EdiTemplate(_pick(rng, ("*", "|", "^", "+")), _pick(rng, ("\n", "~", "~\n")),
                                                rng.randrange(3) == 0)
        out[(v.vendor_id, "EMAIL")] = _text_template(rng, scan=False)
        out[(v.vendor_id, "SCAN")] = _text_template(rng, scan=True)
    return out


# ------------------------------------------------------------------ channel renderers
def _portal(doc: Doc, vendor, version: str) -> bytes:
    inv, lines = doc.invoice, doc.lines
    po = inv["po_id"]
    if version == "v1":
        obj = {"schema": "buyer-portal/invoice@1",
               "supplier": {"name": vendor.name, "tax_registration_id": vendor.trn},
               "invoice": {"number": inv["vendor_invoice_number"], "date": inv["invoice_date"].isoformat(),
                           "po_number": po, "attention": inv["attention_user_id"], "currency": inv["currency"],
                           "net_total": f"{inv['header_net_amount']:.2f}", "tax_total": f"{inv['header_tax_amount']:.2f}",
                           "grand_total": f"{inv['header_gross_amount']:.2f}"},
               "lines": [{"line_no": ln["line_number"], "po_line_no": po_line_number(ln["po_line_id"]) or None,
                          "sku": ln["sku_id"], "description": ln["description"], "uom": ln["uom"],
                          "quantity": f"{ln['quantity']:f}", "unit_price": f"{ln['unit_price']:.2f}",
                          "amount": f"{ln['line_net_amount']:.2f}", "tax_code": ln["tax_code"],
                          "tax_amount": f"{ln['tax_amount']:.2f}"} for ln in lines]}
        return (json.dumps(obj, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    # v2: camelCase, numbers as JSON numbers (written verbatim from Decimal), timestamps for dates
    num = {}

    def n(value: Decimal) -> str:
        token = f"@@{len(num)}@@"
        num[token] = f"{value:f}"
        return token
    obj = {"schemaVersion": "2.0",
           "vendor": {"legalName": vendor.name, "taxId": vendor.trn},
           "header": {"invoiceNo": inv["vendor_invoice_number"],
                      "invoiceDate": f"{inv['invoice_date'].isoformat()}T00:00:00+05:30",
                      "purchaseOrder": po, "requesterId": inv["attention_user_id"], "currencyCode": inv["currency"]},
           "totals": {"taxable": n(inv["header_net_amount"]), "tax": n(inv["header_tax_amount"]),
                      "payable": n(inv["header_gross_amount"])},
           "items": [{"seq": ln["line_number"],
                      "orderLine": int(po_line_number(ln["po_line_id"])) if ln["po_line_id"] else None,
                      "itemCode": ln["sku_id"], "text": ln["description"], "unit": ln["uom"],
                      "qty": n(ln["quantity"]), "rate": n(ln["unit_price"]), "value": n(ln["line_net_amount"]),
                      "taxCode": ln["tax_code"], "taxValue": n(ln["tax_amount"])} for ln in lines]}
    text = json.dumps(obj, indent=1, ensure_ascii=False)
    for token, value in num.items():
        text = text.replace(f'"{token}"', value)
    return (text + "\n").encode("utf-8")


def _edi(doc: Doc, vendor, t: EdiTemplate) -> bytes:
    inv, s = doc.invoice, t.sep

    def amt(v: Decimal) -> str:
        return str(int(v * 100)) if t.implied else f"{v:.2f}"
    segs = [["UNB", "2", "IMP2" if t.implied else "DEC"],
            ["NAD", "SU", vendor.trn, vendor.name],
            ["BGM", "380", inv["vendor_invoice_number"], inv["invoice_date"].strftime("%Y%m%d")],
            ["CUX", inv["currency"]]]
    if inv["po_id"]:
        segs.append(["RFF", "ON", inv["po_id"]])
    if inv["attention_user_id"]:
        segs.append(["RFF", "ATT", inv["attention_user_id"]])
    for ln in doc.lines:
        segs.append(["LIN", str(ln["line_number"]), ln["sku_id"] or "", po_line_number(ln["po_line_id"]), ln["uom"],
                     f"{ln['quantity']:f}", amt(ln["unit_price"]), amt(ln["line_net_amount"]), ln["tax_code"],
                     amt(ln["tax_amount"])])
        segs.append(["IMD", str(ln["line_number"]), ln["description"]])
    segs += [["MOA", "125", amt(inv["header_net_amount"])], ["MOA", "124", amt(inv["header_tax_amount"])],
             ["MOA", "77", amt(inv["header_gross_amount"])], ["CNT", "2", str(len(doc.lines))], ["UNZ", "1"]]
    body = t.terminator.join(s.join(seg) for seg in segs)
    return (body + ("" if body.endswith("\n") else "\n")).encode("utf-8")


def _label(t: TextTemplate, key: str) -> str:
    label = t.labels[key]
    return label.upper() if t.upper else label


def _col(t: TextTemplate, key: str) -> str:
    label = t.columns[key]
    return label.upper() if t.upper else label


def _items(doc: Doc, t: TextTemplate, scan: bool) -> list[str]:
    po_backed = bool(doc.invoice["po_id"])
    keys = ["line"] + (["po_line"] if po_backed else []) + ["sku", "description", "uom", "qty", "price", "amount",
                                                             "tax_code", "tax"]

    def cells(ln) -> dict:
        return {"line": str(ln["line_number"]), "po_line": po_line_number(ln["po_line_id"]) or "-",
                "sku": ln["sku_id"] or "-", "description": ln["description"], "uom": ln["uom"],
                "qty": f"{ln['quantity']:f}", "price": fmt_amount(ln["unit_price"], t.amount_style),
                "amount": fmt_amount(ln["line_net_amount"], t.amount_style),
                "tax_code": fmt_tax_code(ln["tax_code"], t.tax_style),
                "tax": fmt_amount(ln["tax_amount"], t.amount_style)}
    rows = [cells(ln) for ln in doc.lines]
    head = {k: _col(t, k) for k in keys}
    if t.table == "block":
        out = []
        for r in rows:
            out.append(f"{'ITEM' if t.upper else 'Item'} {r['line']}")
            out += [f"  {head[k]}{t.sep if t.sep.strip() else ': '}{r[k]}" for k in keys if k != "line"]
        return out
    if t.table == "pipe":
        out = ["| " + " | ".join(head[k] for k in keys) + " |", "|" + "|".join("---" for _ in keys) + "|"]
        return out + ["| " + " | ".join(r[k] for k in keys) + " |" for r in rows]
    widths = {k: max([len(head[k])] + [len(r[k]) for r in rows]) for k in keys}

    def line(values: dict) -> str:
        return "   ".join(values[k].ljust(widths[k]) for k in keys).rstrip()
    out = [line(head)]
    page_size = SCAN_ROWS_PER_PAGE if scan else len(rows) or 1
    pages = [rows[i:i + page_size] for i in range(0, len(rows), page_size)] or [[]]
    for p, chunk in enumerate(pages, start=1):
        if p > 1:
            out += [f"-- Page {p - 1} of {len(pages)} --", "", line(head)]
        out += [line(r) for r in chunk]
    return out


def _text_body(doc: Doc, vendor, t: TextTemplate, scan: bool, garble: dict) -> list[str]:
    inv = doc.invoice
    meta = [("number", garble.get("number", inv["vendor_invoice_number"])),
            ("date", garble.get("date", fmt_date(inv["invoice_date"], t.date_format)))]
    if inv["po_id"]:
        meta.append(("po", fmt_po(inv["po_id"], t.po_style)))
    if inv["attention_user_id"]:
        meta.append(("attention", inv["attention_user_id"]))
    if t.currency_style == "line":
        meta.append(("currency", "INR"))
    out = []
    name = vendor.name.upper() if scan and t.upper else vendor.name
    if t.labels["supplier"] is None:
        out.append(name)
    else:
        out.append(f"{_label(t, 'supplier')}{t.sep}{name}")
    out += [f"{_label(t, 'tax_id')}{t.sep}{vendor.trn}", f"Plot {int(vendor.vendor_id[4:]) % 97 + 3}, Industrial Area, "
            f"{t.city}", "", "TAX INVOICE" if scan or t.upper else "Tax Invoice", ""]

    def pair(key, value):
        label = "CURRENCY" if key == "currency" and t.upper else ("Currency" if key == "currency" else _label(t, key))
        return f"{label}{t.sep}{value}"
    if t.pairs:
        sep = t.sep if ":" in t.sep else ": "
        for i in range(0, len(meta), 2):
            chunk = meta[i:i + 2]
            out.append("      ".join(f"{(_label(t, k) if k != 'currency' else 'CURRENCY')}{sep}{v}" for k, v in chunk))
    else:
        out += [pair(k, v) for k, v in meta]
    out += [BUYER.upper() if scan and t.upper else BUYER, ""]
    out += _items(doc, t, scan)
    out.append("")
    gross = garble.get("gross", fmt_money(inv["header_gross_amount"], t))
    totals = [("net", fmt_money(inv["header_net_amount"], t)), ("tax", fmt_money(inv["header_tax_amount"], t)),
              ("gross", gross)]
    out += [f"{_label(t, k)}{t.sep}{v}" for k, v in totals]
    out += ["", "Payment terms as per purchase agreement.", "Thank you for your business."]
    if scan:
        out += ["", "Page 1 of 1" if t.table != "columns" or len(doc.lines) <= SCAN_ROWS_PER_PAGE
                else "-- end of document --"]
    return out


def _garble(doc: Doc, t: TextTemplate, field_name: str, rng) -> dict:
    """CAPTURE_REVIEW: one required header field is unreadable on the scan. Look-alike digits are
    repairable but untrusted (OCR_REPAIRED); smudges cannot be read at all. Invoice numbers are only
    ever smudged: look-alike letters would be indistinguishable from a real alphanumeric number."""
    inv = doc.invoice
    if field_name == "header_gross_amount":
        text, key = fmt_money(inv["header_gross_amount"], t), "gross"
    elif field_name == "invoice_date":
        text, key = fmt_date(inv["invoice_date"], t.date_format), "date"
    else:
        text, key = inv["vendor_invoice_number"], "number"
    mode = "smudge" if key == "number" or rng.randrange(2) == 0 else "lookalike"
    allowed = LOOKALIKE if mode == "lookalike" else "0123456789"
    positions = [i for i, ch in enumerate(text) if ch in allowed]
    if not positions:                                   # no digit has a look-alike: smudge instead
        mode, positions = "smudge", [i for i, ch in enumerate(text) if ch.isdigit()]
    chars = list(text)
    for i in sorted({positions[rng.randrange(len(positions))] for _ in range(2)}):
        chars[i] = SMUDGE[rng.randrange(len(SMUDGE))] if mode == "smudge" else LOOKALIKE[chars[i]]
    return {key: "".join(chars)}


def _email(doc: Doc, vendor, t: TextTemplate, rng) -> bytes:
    m, inv = doc.manifest, doc.invoice
    sender = m["sender_address"]
    head = [f"From: {sender}", "To: invoices@buyer.example", f"Date: {_rfc2822(m['received_at'])}",
            f"Subject: Invoice {inv['vendor_invoice_number']}", f"Message-ID: <{m['doc_id'].lower()}@mail.example>",
            "MIME-Version: 1.0", "Content-Type: text/plain; charset=utf-8", ""]
    body: list[str] = []
    if not sender.startswith("ap@vnd-"):          # forwarded by an internal mailbox
        body += ["FYI - forwarding the invoice below for processing.", "",
                 "---------- Forwarded message ---------",
                 f"From: {vendor.name} <ap@{vendor.vendor_id.lower()}.example>",
                 f"Date: {_rfc2822(m['received_at'])}", f"Subject: Invoice {inv['vendor_invoice_number']}",
                 "To: " + sender, ""]
    body += [_pick(rng, ("Dear Sir/Madam,", "Hello AP team,", "Dear Accounts Payable,")), "",
             "Please find our invoice details below.", ""]
    body += _text_body(doc, vendor, t, scan=False, garble={})
    body += ["", "Regards,", "Accounts Team", vendor.name]
    return ("\n".join(head + body) + "\n").encode("utf-8")


def _scan(doc: Doc, vendor, t: TextTemplate, unreadable: str | None, rng) -> bytes:
    garble = _garble(doc, t, unreadable, rng) if unreadable else {}
    lines = _text_body(doc, vendor, t, scan=True, garble=garble)
    return ("\n".join(lines) + "\n").encode("utf-8")


def render_all(ds: Dataset, plan) -> dict[str, bytes]:
    """Render every document of the final dataset: {manifest file_path: bytes}. Fills the manifest's
    file_sha256 and file_bytes in place."""
    world = plan.world
    templates = build_templates(world)
    vendors = {v.vendor_id: v for v in world.vendors}
    bills = {b.key: b for b in plan.bills}
    rng = stream(world.seed, "doc-render")
    out: dict[str, bytes] = {}
    for doc in ds.docs:
        m = doc.manifest
        vendor = vendors[doc.invoice["vendor_id"]]
        channel = m["channel"]
        template = templates[(vendor.vendor_id, channel)]
        if channel == "PORTAL":
            data = _portal(doc, vendor, template)
        elif channel == "EDI":
            data = _edi(doc, vendor, template)
        elif channel == "EMAIL":
            data = _email(doc, vendor, template, rng)
        else:
            unreadable = bills[doc.key].params["unreadable_field"] if doc.overlay == "DEGRADED_SCAN" else None
            data = _scan(doc, vendor, template, unreadable, rng)
        m["file_sha256"], m["file_bytes"] = hashlib.sha256(data).hexdigest(), len(data)
        out[m["file_path"]] = data
    return out
