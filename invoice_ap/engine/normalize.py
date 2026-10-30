"""Format rules: turn printed text into canonical values, or None when it cannot be read.

Rules never consult master data or the PO (ADR-032). Ambiguity is never resolved by guessing: dates
are day-first (Indian convention); a value that fails its format is unreadable. `repair` replaces OCR
look-alike letters inside tokens that already contain a digit, and its result is never trusted
(OCR_REPAIRED confidence < CAP-01 threshold).
"""
from __future__ import annotations

import re
from datetime import date
from decimal import Decimal, InvalidOperation

from ..common.enums import UOM_DECIMALS

MONTHS = {m: i for i, m in enumerate(("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov",
                                      "dec"), start=1)}
LOOKALIKE = str.maketrans({"O": "0", "o": "0", "D": "0", "l": "1", "I": "1", "|": "1", "S": "5", "s": "5",
                           "B": "8", "Z": "2", "z": "2"})
TAX_CODES = ("GST0", "GST5", "GST12", "GST18", "EXEMPT")
INVOICE_NUMBER = re.compile(r"[A-Za-z0-9][A-Za-z0-9/\-. ]*")


def label_key(text: str) -> str:
    """Normalised label: lower case, punctuation as spaces, collapsed. '#' alone stays '#'."""
    key = " ".join(re.sub(r"[^a-z0-9]+", " ", text.lower()).split())
    return key or ("#" if "#" in text else "")


def repair(text: str) -> str:
    return re.sub(r"\S+", lambda m: m.group(0).translate(LOOKALIKE) if re.search(r"\d", m.group(0))
                  else m.group(0), text)


def amount(text: str, implied: bool = False) -> Decimal | None:
    s = text.strip()
    s = re.sub(r"^(?:INR|Rs\.?|₹)\s*", "", s, flags=re.IGNORECASE)
    if implied:
        return Decimal(s) / 100 if re.fullmatch(r"\d+", s) else None
    if not re.fullmatch(r"\d{1,3}(?:,\d{2,3})*(?:\.\d{1,2})?|\d+(?:\.\d{1,2})?", s):
        return None
    return Decimal(s.replace(",", "")).quantize(Decimal("0.01"))


def quantity(text: str, uom: str | None) -> tuple[Decimal | None, bool]:
    """(value, precision_ok). The value is never rounded: extra decimals are kept and flagged."""
    s = text.strip().replace(",", "")
    if not re.fullmatch(r"\d+(?:\.\d+)?", s):
        return None, True
    value = Decimal(s)
    places = UOM_DECIMALS.get(uom or "", None)
    if places is None:
        return value, True
    exponent = -value.as_tuple().exponent if value.as_tuple().exponent < 0 else 0
    if exponent > places:
        return value, False
    return value.quantize(Decimal(1).scaleb(-places)), True


def integer(text: str) -> int | None:
    s = text.strip()
    return int(s) if re.fullmatch(r"\d{1,6}", s) else None


def _safe_date(y: int, m: int, d: int) -> date | None:
    try:
        return date(y, m, d)
    except ValueError:
        return None


def invoice_date(text: str) -> date | None:
    s = text.strip()
    if m := re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})(?:T[\d:]{8}(?:[+-]\d{2}:\d{2})?)?", s):
        return _safe_date(int(m[1]), int(m[2]), int(m[3]))
    if m := re.fullmatch(r"(\d{8})", s):                                   # EDI CCYYMMDD
        return _safe_date(int(s[:4]), int(s[4:6]), int(s[6:]))
    if m := re.fullmatch(r"(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{4})", s):    # day first
        return _safe_date(int(m[3]), int(m[2]), int(m[1]))
    if m := re.fullmatch(r"(\d{1,2})[ \-]([A-Za-z]{3,9})[ \-](\d{4})", s):
        month = MONTHS.get(m[2][:3].lower())
        return _safe_date(int(m[3]), month, int(m[1])) if month and _month_ok(m[2]) else None
    if m := re.fullmatch(r"([A-Za-z]{3,9})\.? (\d{1,2}),? (\d{4})", s):
        month = MONTHS.get(m[1][:3].lower())
        return _safe_date(int(m[3]), month, int(m[2])) if month and _month_ok(m[1]) else None
    return None


def _month_ok(name: str) -> bool:
    full = ("january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
            "november", "december")
    n = name.lower()
    return len(n) == 3 or n in full


def tax_code(text: str) -> str | None:
    s = re.sub(r"\s+", "", text.upper())
    if s in ("EXEMPT", "EXEMPTED", "NIL", "NILRATED"):
        return "EXEMPT"
    m = re.fullmatch(r"(?:GST)?(\d{1,2})%?", s)
    if m and f"GST{int(m[1])}" in TAX_CODES and (s.startswith("GST") or s.endswith("%")):
        return f"GST{int(m[1])}"
    return None


def trn(text: str) -> str | None:
    m = re.fullmatch(r"(?:TRN[\s\-]?)?(\d{9})", text.strip().upper())
    return f"TRN-{m[1]}" if m else None


def po_reference(text: str) -> str | None:
    m = re.fullmatch(r"(?:P\.?O\.?[\s/\-#:]*)?(\d{4})[/\-](\d{6})", text.strip(), flags=re.IGNORECASE)
    return f"PO-{m[1]}-{m[2]}" if m else None


def user_reference(text: str) -> str | None:
    m = re.fullmatch(r".*?\b(USR-\d{4})\b.*", text.strip())
    return m[1] if m else None


def sku(text: str) -> str | None:
    s = text.strip()
    return s if re.fullmatch(r"SKU-\d{5}", s) else None


def uom(text: str) -> str | None:
    s = text.strip().upper()
    return s if s in UOM_DECIMALS else None


def invoice_number(text: str) -> str | None:
    s = text.strip()
    return s if INVOICE_NUMBER.fullmatch(s) else None


def currency(text: str) -> str | None:
    return "INR" if text.strip().upper() in ("INR", "RS", "RS.", "₹") else None


def to_decimal(value) -> Decimal | None:
    """Portal v2 JSON numbers arrive as Decimal or int; anything else is unreadable."""
    if isinstance(value, bool) or not isinstance(value, (int, Decimal)):
        return None
    try:
        return Decimal(value)
    except InvalidOperation:
        return None
