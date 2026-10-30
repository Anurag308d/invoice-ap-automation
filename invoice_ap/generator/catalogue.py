"""Scenario catalogue: what the generator injects and the label it intends each injection to get.

This is generator-side truth. The engine never imports it (enforced by tests/test_boundary.py).
The oracle derives labels independently from the true data under config/ap_policy.toml,
and generation fails loudly unless oracle labels == intended_issues for every invoice.

Placement codes (see docs/data_generation.md section 4):
  S11    one invoice on a single-delivery PO (archetype A11)
  PAIR11 two S11 invoices forming a deliberate true-negative pair
  S22_2  the second invoice of a two-delivery PO (archetype A22); its first invoice is
         C-SPLIT-PARTIAL
  SPLIT_PARTIAL / SPLIT_FINAL  the remaining invoice slots on A22 and A33 POs, resolved from the
         PO structure: non-final deliveries are partial, the last one completes the PO
  S21    a consolidated invoice covering two deliveries (archetype A21)
  S12    the two invoices that bill one delivery in parts (archetype A12)
  F      an invoice on a PO that is never received (archetype A01)
  NPO    a non-PO (services) original invoice
  DUP    an extra document that duplicates an earlier original invoice
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SubScenario:
    code: str
    category: str
    placement: str
    full_weight: int           # exact count at full scale; weight for apportionment elsewhere
    edge_cases: tuple[str, ...]
    intended_issues: tuple[str, ...]
    decision: str              # expected decision family: APPROVAL_PATH | HOLD | REJECT
    description: str


# Five named categories at their exact assignment shares. The two extra required edge cases are
# carved out of CLEAN at 1% each (ADR-005) and degraded scans at 0.5% (ADR-017), so CLEAN is
# 1,350 (67.5%) at full scale.
CATEGORY_WEIGHTS = (
    ("CLEAN", 1350),
    ("PRICE_VARIANCE", 200),
    ("QTY_MISMATCH", 160),
    ("DUPLICATE", 100),
    ("MISSING_RECEIPT", 80),
    ("TAX_VENDOR", 60),
    ("ARITHMETIC", 20),
    ("INVOICE_BEFORE_PO", 20),
    ("CAPTURE_REVIEW", 10),
)
CLEAN_S11_PAIRS_FULL = 5  # true-negative pairs (10 invoices) at full scale

_A, _H, _R = "APPROVAL_PATH", "HOLD", "REJECT"
SUBSCENARIOS: tuple[SubScenario, ...] = (
    # ---- CLEAN (business-clean; the true invoice conforms to PO, receipts and policy)
    SubScenario("C-STD", "CLEAN", "S11", 310, (), (), _A,
                "Full delivery, invoice equals PO price and received quantity"),
    SubScenario("C-PARTIAL-OPEN", "CLEAN", "S11", 60, ("EC-04",), (), _A,
                "Partial delivery; invoice bills exactly the received quantity; PO stays open"),
    SubScenario("C-OVERRECEIPT-WITHIN", "CLEAN", "S11", 20, (), (), _A,
                "Over-receipt inside the 5% tolerance, billed as received"),
    SubScenario("C-QTY-AT-TOL", "CLEAN", "S11", 10, (), (), _A,
                "Boundary: received and billed exactly ordered x 1.05"),
    SubScenario("C-PRICE-AT-TOL", "CLEAN", "S11", 20, (), (), _A,
                "Boundary: unit price exactly +2.00% over PO (inclusive tolerance)"),
    SubScenario("C-PRICE-INSIDE", "CLEAN", "S11", 20, (), (), _A,
                "Boundary: unit price one cent below +2.00% over PO"),
    SubScenario("C-PRICE-SMALL-VAR", "CLEAN", "S11", 40, (), (), _A,
                "Small price differences between -1.5% and +1.5%"),
    SubScenario("C-TAX-ROUNDING", "CLEAN", "S11", 20, (), (), _A,
                "One line's tax printed 0.01 away from round(net x rate): inside rounding tolerance"),
    SubScenario("C-TN-SAME-DAY", "CLEAN", "PAIR11", 10, (), (), _A,
                "True negative: same vendor, date and amount on two different POs (repeat order)"),
    SubScenario("C-SPLIT-PARTIAL", "CLEAN", "SPLIT_PARTIAL", 400, ("EC-04",), (), _A,
                "Non-final delivery of a split PO, invoiced for exactly what was delivered"),
    SubScenario("C-SPLIT-FINAL", "CLEAN", "SPLIT_FINAL", 290, (), (), _A,
                "Final delivery of a split PO; cumulative invoiced reaches the ordered quantity"),
    SubScenario("C-CONSOLIDATED", "CLEAN", "S21", 40, ("EC-04",), (), _A,
                "Two partial deliveries billed on one invoice (one invoice line -> two receipt lines)"),
    SubScenario("C-PARTIAL-BILLING", "CLEAN", "S12", 20, (), (), _A,
                "One delivery billed on two invoices (one receipt line -> two invoice lines)"),
    SubScenario("C-NPO-RECURRING", "CLEAN", "NPO", 57, (), (), _A,
                "Recurring same-amount monthly service invoices: duplicate-check true negatives"),
    SubScenario("C-NPO-ONEOFF", "CLEAN", "NPO", 38, (), (), _A,
                "One-off non-PO service invoice approved by the requester"),
    # ---- PRICE_VARIANCE
    SubScenario("PV-OVER", "PRICE_VARIANCE", "S11", 120, (), ("PRICE_VARIANCE",), _H,
                "Unit price 2.5% to 15% above the PO price"),
    SubScenario("PV-SPLIT-LATER", "PRICE_VARIANCE", "S22_2", 30, (), ("PRICE_VARIANCE",), _H,
                "Price raised on the second delivery's invoice"),
    SubScenario("PV-UNDER", "PRICE_VARIANCE", "S11", 30, (), ("PRICE_VARIANCE",), _H,
                "Unit price more than 2% below the PO price (symmetric tolerance)"),
    SubScenario("PV-BOUNDARY-OUT", "PRICE_VARIANCE", "S11", 20, (), ("PRICE_VARIANCE",), _H,
                "Boundary: unit price one cent above +2.00% over PO"),
    # ---- QTY_MISMATCH
    SubScenario("QM-PARTIAL-BILLED-FULL", "QTY_MISMATCH", "S11", 50, ("EC-04",),
                ("QTY_EXCEEDS_RECEIVED",), _H, "Partial delivery billed as if fully delivered"),
    SubScenario("QM-OVERBILL-RECEIVED", "QTY_MISMATCH", "S11", 30, (),
                ("QTY_EXCEEDS_RECEIVED",), _H, "Full delivery, billed above received but inside PO tolerance"),
    SubScenario("QM-CUMULATIVE", "QTY_MISMATCH", "S22_2", 30, (),
                ("QTY_EXCEEDS_RECEIVED",), _H, "Second invoice pushes cumulative invoiced above cumulative received"),
    SubScenario("QM-EXCEEDS-PO-OVERRECEIPT", "QTY_MISMATCH", "S11", 20, ("EC-07",),
                ("QTY_EXCEEDS_PO",), _H, "Over-receipt beyond tolerance billed in full"),
    SubScenario("QM-EXCEEDS-PO-AND-RECEIVED", "QTY_MISMATCH", "S11", 20, ("EC-07",),
                ("QTY_EXCEEDS_PO", "QTY_EXCEEDS_RECEIVED"), _H,
                "Billed above both the received quantity and ordered x 1.05 (two labels)"),
    SubScenario("QM-BOUNDARY-OUT", "QTY_MISMATCH", "S11", 10, ("EC-07",),
                ("QTY_EXCEEDS_PO",), _H, "Boundary: received and billed one unit above ordered x 1.05"),
    # ---- DUPLICATE
    SubScenario("DUP-EXACT", "DUPLICATE", "DUP", 25, ("EC-08",), ("DUPLICATE_EXACT",), _R,
                "Identical resubmission of an earlier invoice, often through another channel"),
    SubScenario("DUP-EXACT-NORMALIZED", "DUPLICATE", "DUP", 20, ("EC-08",), ("DUPLICATE_EXACT",), _R,
                "Resubmission whose invoice number differs only in case, separators or leading zeros"),
    SubScenario("DUP-EXACT-NPO", "DUPLICATE", "DUP", 5, ("EC-08",), ("DUPLICATE_EXACT",), _R,
                "Resubmission of a recurring non-PO service invoice"),
    SubScenario("DUP-NUMBER-REUSE", "DUPLICATE", "DUP", 35, ("EC-01",), ("DUPLICATE_NUMBER_REUSE",), _H,
                "Same vendor and invoice number with different date or amount"),
    SubScenario("DUP-CONTENT", "DUPLICATE", "DUP", 15, ("EC-08",), ("DUPLICATE_SUSPECTED",), _H,
                "Same vendor, date, amount and PO resubmitted under an altered invoice number"),
    # ---- MISSING_RECEIPT
    SubScenario("MR-NO-GRN", "MISSING_RECEIPT", "F", 80, (), ("MISSING_RECEIPT",), _H,
                "Invoice on a PO with no goods receipt posted by the processing time"),
    # ---- TAX_VENDOR
    SubScenario("TV-CLOSED", "TAX_VENDOR", "S11", 15, ("EC-05",), ("VENDOR_CLOSED",), _H,
                "Invoice dated after the vendor's CLOSED status took effect"),
    SubScenario("TV-BLOCKED", "TAX_VENDOR", "S11", 5, (), ("VENDOR_BLOCKED",), _H,
                "Invoice dated inside a vendor BLOCKED window"),
    SubScenario("TV-TAX-CODE", "TAX_VENDOR", "S11", 15, ("EC-06",), ("TAX_CODE_MISMATCH",), _H,
                "Line tax code differs from the PO line (tax computed consistently with the wrong code)"),
    SubScenario("TV-TAX-AMOUNT", "TAX_VENDOR", "S11", 10, ("EC-06",), ("TAX_AMOUNT_MISMATCH",), _H,
                "Line tax amount differs from round(net x rate) by more than 0.01"),
    SubScenario("TV-VENDOR-PO", "TAX_VENDOR", "S11", 10, (), ("VENDOR_PO_MISMATCH",), _H,
                "Invoice quotes a PO that belongs to a different vendor"),
    SubScenario("TV-NPO-TAX-AMOUNT", "TAX_VENDOR", "NPO", 5, ("EC-06",), ("TAX_AMOUNT_MISMATCH",), _H,
                "Non-PO service invoice with a miscalculated tax amount"),
    # ---- ARITHMETIC (required edge case carved from CLEAN)
    SubScenario("ARITH-HEADER-TOTAL", "ARITHMETIC", "S11", 15, ("EC-02",), ("HEADER_TOTAL_MISMATCH",), _H,
                "Printed invoice total differs from the sum of its lines plus tax"),
    SubScenario("ARITH-LINE-EXTENSION", "ARITHMETIC", "S11", 5, (), ("LINE_AMOUNT_MISMATCH",), _H,
                "Printed line amount differs from quantity x unit price"),
    # ---- INVOICE_BEFORE_PO (required edge case carved from CLEAN)
    SubScenario("DATE-INVOICE-BEFORE-PO", "INVOICE_BEFORE_PO", "S11", 20, ("EC-03",),
                ("INVOICE_BEFORE_PO",), _H, "Invoice dated before the PO it quotes (retrospective PO)"),
    # ---- CAPTURE_REVIEW (degraded documents, carved from CLEAN; ruling on Q2, ADR-017)
    SubScenario("CAP-DEGRADED-SCAN", "CAPTURE_REVIEW", "S11", 10, (), ("EXT_LOW_CONFIDENCE",), _H,
                "Otherwise clean invoice whose scan has an unreadable required field: capture review"),
)
