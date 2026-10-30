"""The extractor's label synonyms (normalised by `normalize.label_key`). The first entry of each list
is the canonical label (LABEL_EXACT); the others are synonyms (LABEL_SYNONYM).

This list belongs to the engine and is maintained independently of any vendor template: an unknown
label is simply not read, so the field is NOT_FOUND and the document goes to capture review.
"""
from __future__ import annotations

HEADER = {
    "vendor_name": ("supplier", "vendor", "seller", "sold by", "supplier name", "vendor name"),
    "vendor_tax_id": ("tax registration number", "trn", "tax reg no", "tax regn no", "tax registration no",
                      "tax id", "gst reg no"),
    "vendor_invoice_number": ("invoice number", "invoice no", "inv", "inv no", "bill no", "bill number",
                              "tax invoice no", "tax invoice number", "invoice ref"),
    "invoice_date": ("invoice date", "date", "inv date", "bill date", "dated", "invoice dt"),
    "po_number": ("po number", "po no", "po", "purchase order", "purchase order no", "your order ref",
                  "order ref", "p o", "p o no"),
    "attention_user_id": ("attention", "attn", "kind attn", "requested by", "requester"),
    "currency": ("currency",),
}
TOTALS = {
    "header_net_amount": ("net amount", "subtotal", "sub total", "taxable value", "total before tax",
                          "taxable amount"),
    "header_tax_amount": ("total tax", "tax", "gst", "tax amount", "tax total"),
    "header_gross_amount": ("invoice total", "total", "grand total", "amount payable", "total amount due",
                            "amount due", "total payable"),
}
COLUMNS = {
    "line_number": ("line", "#", "sr", "s no", "sl no"),
    "po_line_number": ("po line", "po ln", "order line", "po line no"),
    "sku_id": ("item code", "sku", "item", "product code"),
    "description": ("description", "particulars", "item description", "details"),
    "uom": ("uom", "unit", "units"),
    "quantity": ("quantity", "qty"),
    "unit_price": ("unit price", "rate", "price"),
    "line_net_amount": ("amount", "taxable amt", "value", "line amount"),
    "tax_code": ("tax code", "gst rate", "tax rate", "gst code"),
    "tax_amount": ("tax amount", "tax amt", "gst amt", "tax", "gst"),
}
BLOCK_START = ("item", "line", "sr", "s no")


def lookup(table: dict, key: str) -> tuple[str, str] | None:
    """(field, method) for a normalised label, or None when unknown."""
    for name, labels in table.items():
        if key in labels:
            return name, "LABEL_EXACT" if key == labels[0] else "LABEL_SYNONYM"
    return None
