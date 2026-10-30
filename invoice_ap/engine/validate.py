"""Duplicate gates and the collected checks (DUP-01..03, VEN-02/03, PO-01..03, DATE-01..02, ARI-01..02,
TAX-01..03, MAT-01..04), applied to captured values only, in intake order (business_rules section 2).

Cumulative state lives here: the duplicate indexes (every earlier capture-trusted document), the
prior-invoiced quantity per PO line (every earlier invoice that reached line matching, on hold or
not) and the receipt allocations of the N:M bridge (FIFO over GRN lines posted before processing).
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal

from ..common.money import line_net, tax_amount
from .master import Master

HUNDRED = Decimal(100)


@dataclass
class Issue:
    type: str
    line_id: str | None = None
    expected: str | None = None
    actual: str | None = None
    variance: str | None = None
    tolerance: str | None = None
    related: str | None = None


@dataclass
class LineState:
    price: str = "NOT_EVALUATED"
    qty: str = "NOT_EVALUATED"
    tax: str = "NOT_EVALUATED"
    po_line_id: str | None = None
    ordered: Decimal | None = None
    received: Decimal | None = None
    prior: Decimal | None = None
    max_qty: Decimal | None = None
    po_price: Decimal | None = None
    variance: Decimal | None = None
    po_tax_code: str | None = None
    expected_tax: Decimal | None = None
    within_qty: bool = False
    rules: list[str] = field(default_factory=list)
    allocations: list[tuple[str, Decimal]] = field(default_factory=list)


@dataclass
class Duplicate:
    type: str
    original: str
    match_type: str
    keys: tuple[str, ...]


DUP_RULES = (("DUPLICATE_EXACT", "EXACT", ("header_gross_amount", "invoice_date", "normalized_number", "vendor_id")),
             ("DUPLICATE_NUMBER_REUSE", "NUMBER_REUSE", ("normalized_number", "vendor_id")),
             ("DUPLICATE_SUSPECTED", "CONTENT", ("header_gross_amount", "invoice_date", "po_id", "vendor_id")))


class Validator:
    def __init__(self, master: Master, policy):
        raw = policy.raw
        self.m = master
        self.price_tol = Decimal(raw["matching"]["price_tolerance_pct"])
        self.over_tol = Decimal(raw["matching"]["over_receipt_tolerance_pct"])
        self.tax_abs = Decimal(raw["tax"]["amount_abs"])
        self.line_abs = Decimal(raw["arithmetic"]["line_amount_abs"])
        self.header_abs = Decimal(raw["arithmetic"]["header_amount_abs"])
        self.indexes: list[dict] = [{}, {}, {}]
        self.invoiced: dict[str, Decimal] = defaultdict(Decimal)
        self.consumed: dict[str, Decimal] = defaultdict(Decimal)

    # ------------------------------------------------------------------ DUP-01..03 (gates)
    def duplicate(self, inv: dict) -> Duplicate | None:
        values = {"vendor_id": inv["vendor_id"], "normalized_number": inv["normalized_invoice_number"],
                  "invoice_date": inv["invoice_date"], "header_gross_amount": inv["header_gross_amount"],
                  "po_id": inv["po_id"] or inv["po_number"] or ""}
        found = None
        for (kind, match_type, keys), index in zip(DUP_RULES, self.indexes):
            key = tuple(values[k] for k in keys)
            if found is None and key in index:
                found = Duplicate(kind, index[key], match_type, keys)
            index.setdefault(key, inv["invoice_id"])          # the earliest document stays the original
        return found

    # ------------------------------------------------------------------ collected checks
    def check(self, inv: dict, lines: list[dict], at: datetime) -> tuple[list[Issue], dict[str, LineState], bool]:
        issues: list[Issue] = []
        states = {ln["invoice_line_id"]: LineState() for ln in lines}
        day: date = inv["invoice_date"]
        received_day = at.date()
        status = self.m.vendor_status(inv["vendor_id"], day, at)
        if status == "CLOSED":
            issues.append(Issue("VENDOR_CLOSED", expected="ACTIVE", actual=f"CLOSED on {day}"))
        elif status == "BLOCKED":
            issues.append(Issue("VENDOR_BLOCKED", expected="ACTIVE", actual=f"BLOCKED on {day}"))
        po, po_ok = None, False
        if inv["po_number"] is not None:
            po = self.m.po_known(inv["po_id"], received_day)
            if po is None:
                issues.append(Issue("PO_NOT_FOUND", expected="PO issued before processing", actual=inv["po_number"]))
            elif po["vendor_id"] != inv["vendor_id"]:
                issues.append(Issue("VENDOR_PO_MISMATCH", expected=po["vendor_id"], actual=inv["vendor_id"]))
            else:
                po_ok = True
        if day > received_day:
            issues.append(Issue("INVOICE_DATE_IN_FUTURE", expected=f"<= {received_day}", actual=str(day)))
        if po_ok and day < date.fromisoformat(po["po_date"]):
            issues.append(Issue("INVOICE_BEFORE_PO", expected=f">= {po['po_date']}", actual=str(day)))
        nets = sum((ln["line_net_amount"] for ln in lines), Decimal(0))
        taxes = sum((ln["tax_amount"] for ln in lines), Decimal(0))
        printed = (inv["header_net_amount"], inv["header_tax_amount"], inv["header_gross_amount"])
        if any(abs(p - s) > self.header_abs for p, s in zip(printed, (nets, taxes, nets + taxes))):
            issues.append(Issue("HEADER_TOTAL_MISMATCH", expected=f"{nets + taxes:f}", actual=f"{printed[2]:f}",
                                variance=f"{printed[2] - nets - taxes:f}", tolerance=f"{self.header_abs:f}"))
        for ln in lines:
            s, lid = states[ln["invoice_line_id"]], ln["invoice_line_id"]
            extension = line_net(ln["quantity"], ln["unit_price"])
            if abs(ln["line_net_amount"] - extension) > self.line_abs:
                issues.append(Issue("LINE_AMOUNT_MISMATCH", lid, f"{extension:f}", f"{ln['line_net_amount']:f}",
                                    f"{ln['line_net_amount'] - extension:f}", f"{self.line_abs:f}"))
            rate = self.m.tax_rate(ln["tax_code"])
            s.expected_tax = tax_amount(ln["line_net_amount"], rate)
            diff = abs(ln["tax_amount"] - s.expected_tax)
            s.tax = "OK" if diff == 0 else "WITHIN_ROUNDING" if diff <= self.tax_abs else "AMOUNT_MISMATCH"
            s.rules += ["TAX-01", "TAX-03"]
            if not self.m.tax_valid(ln["tax_code"], day):
                issues.append(Issue("TAX_CODE_INVALID", lid, f"tax code valid on {day}", ln["tax_code"]))
                s.tax = "CODE_MISMATCH"
            if diff > self.tax_abs:
                issues.append(Issue("TAX_AMOUNT_MISMATCH", lid, f"{s.expected_tax:f}", f"{ln['tax_amount']:f}",
                                    f"{ln['tax_amount'] - s.expected_tax:f}", f"{self.tax_abs:f}"))
        if not po_ok:
            return issues, states, False
        for ln in lines:
            self._match_line(inv, ln, states[ln["invoice_line_id"]], at, issues)
        for ln in lines:                       # every invoice that reached matching is a claim on the PO line
            s = states[ln["invoice_line_id"]]
            if s.po_line_id:
                self._allocate(s, ln["quantity"], at)
                self.invoiced[s.po_line_id] += ln["quantity"]
        return issues, states, True

    def _resolve_line(self, inv: dict, ln: dict) -> str | None:
        """PO-03: the printed PO line number, else a unique SKU on the PO."""
        if ln["po_line_id"]:
            return ln["po_line_id"]
        if ln["po_line_number"] is None and ln["sku_id"]:
            hits = self.m.po_line_by_sku.get((inv["po_id"], ln["sku_id"]), [])
            return hits[0] if len(hits) == 1 else None
        return None

    def _match_line(self, inv: dict, ln: dict, s: LineState, at: datetime, issues: list[Issue]) -> None:
        lid = ln["invoice_line_id"]
        pol_id = self._resolve_line(inv, ln)
        pol = self.m.po_lines.get(pol_id or "")
        if pol is None or pol["po_id"] != inv["po_id"]:
            issues.append(Issue("PO_LINE_UNMATCHED", lid, "a line of " + inv["po_id"], str(ln["po_line_number"])))
            return
        s.po_line_id, s.po_tax_code = pol_id, pol["tax_code"]
        s.rules += ["PO-03", "TAX-02", "MAT-01", "MAT-02", "MAT-03", "MAT-04"]
        if ln["tax_code"] != pol["tax_code"]:
            issues.append(Issue("TAX_CODE_MISMATCH", lid, pol["tax_code"], ln["tax_code"]))
            s.tax = "CODE_MISMATCH"
        s.ordered = Decimal(pol["ordered_qty"])
        s.received = sum((q for _, _, q in self.m.receipts_until(pol_id, at)), Decimal(0))
        s.prior = self.invoiced[pol_id]
        s.max_qty = s.ordered * (HUNDRED + self.over_tol) / HUNDRED
        cum = s.prior + ln["quantity"]
        if s.received == 0:
            issues.append(Issue("MISSING_RECEIPT", lid, "> 0 received", "0"))
            s.qty = "NO_RECEIPT"
        else:
            s.qty = "OK"
            if cum * HUNDRED > s.ordered * (HUNDRED + self.over_tol):
                issues.append(Issue("QTY_EXCEEDS_PO", lid, f"<= {s.max_qty.normalize():f}", f"{cum:f}",
                                    f"{cum - s.max_qty:f}", f"{self.over_tol:f}%"))
                s.qty = "EXCEEDS_PO"
            if cum > s.received:
                issues.append(Issue("QTY_EXCEEDS_RECEIVED", lid, f"<= {s.received:f}", f"{cum:f}",
                                    f"{cum - s.received:f}"))
                s.qty = "EXCEEDS_PO" if s.qty == "EXCEEDS_PO" else "EXCEEDS_RECEIVED"
            s.within_qty = s.qty == "OK" and cum > s.ordered
        s.po_price = Decimal(pol["unit_price"])
        diff = ln["unit_price"] - s.po_price
        s.variance = diff * HUNDRED / s.po_price
        if abs(diff) * HUNDRED <= s.po_price * self.price_tol:
            s.price = "EXACT" if diff == 0 else "WITHIN_TOLERANCE"
        else:
            s.price = "OUT_OF_TOLERANCE"
            issues.append(Issue("PRICE_VARIANCE", lid, f"{s.po_price:f}", f"{ln['unit_price']:f}",
                                f"{s.variance.quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP):f}%", f"{self.price_tol:f}%"))

    def _allocate(self, s: LineState, quantity: Decimal, at: datetime) -> None:
        """N:M bridge: FIFO over the GRN lines of the PO line posted before processing."""
        remaining = quantity
        for _, grn_line, qty in self.m.receipts_until(s.po_line_id, at):
            free = qty - self.consumed[grn_line]
            if remaining <= 0:
                break
            if free <= 0:
                continue
            take = min(free, remaining)
            self.consumed[grn_line] += take
            remaining -= take
            s.allocations.append((grn_line, take))


def match_status(po_backed: bool, evaluated: bool, states) -> str:
    """MS-01 at invoice level (or for one line when given one state)."""
    if not po_backed:
        return "NOT_APPLICABLE"
    if not evaluated:
        return "NOT_EVALUATED"
    st = list(states)
    if any(s.tax in ("CODE_MISMATCH", "AMOUNT_MISMATCH") for s in st):
        return "TAX_MISMATCH"
    if any(s.qty == "NO_RECEIPT" for s in st):
        return "MISSING_RECEIPT"
    if any(s.qty in ("EXCEEDS_PO", "EXCEEDS_RECEIVED") for s in st):
        return "QTY_MISMATCH"
    if any(s.price == "OUT_OF_TOLERANCE" for s in st):
        return "PRICE_VARIANCE"
    if any(s.po_line_id is None for s in st):
        return "NOT_EVALUATED"
    if all(s.price == "EXACT" and s.tax == "OK" and not s.within_qty for s in st):
        return "MATCHED"
    return "MATCHED_WITHIN_TOLERANCE"
