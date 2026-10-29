"""ID conventions (R19) and exact Decimal arithmetic (ADR-014)."""
from __future__ import annotations

from decimal import Decimal

import pytest

from invoice_ap.common import ids
from invoice_ap.common.money import (D, fmt, line_net, money, pct_change, qty, round_half_up_int,
                                     tax_amount, within_pct)


def test_assignment_id_examples():
    inv = ids.invoice_id("VND-00001", 1)
    assert ids.vendor_id(1) == "VND-00001"
    assert ids.po_id(1) == "PO-2026-000001"
    assert ids.grn_id(1) == "GRN-2026-000001"
    assert inv == "INV-VND-00001-2026-000001"
    assert ids.invoice_line_id(inv, 1) == "INVL-INV-VND-00001-2026-000001-01"


def test_every_formatter_matches_its_documented_pattern():
    po = ids.po_id(42)
    grn = ids.grn_id(7)
    inv = ids.invoice_id(ids.vendor_id(300), 2000)
    samples = {
        "vendor_id": ids.vendor_id(300), "sku_id": ids.sku_id(12), "user_id": ids.user_id(3),
        "vsh_id": ids.vsh_id(9), "po_id": po, "po_line_id": ids.po_line_id(po, 8), "grn_id": grn,
        "grn_line_id": ids.grn_line_id(grn, 2), "invoice_id": inv,
        "invoice_line_id": ids.invoice_line_id(inv, 3), "doc_id": ids.doc_id(5),
        "erp_event_id": ids.erp_event_id(1), "ap_event_id": ids.ap_event_id(1),
        "exception_id": ids.exception_id(1), "approval_id": ids.approval_id(1),
        "payment_id": ids.payment_id(1), "allocation_id": ids.allocation_id(1),
        "duplicate_pair_id": ids.duplicate_pair_id(1), "extraction_field_id": ids.extraction_field_id(1),
    }
    assert set(samples) == set(ids.PATTERNS)
    for kind, value in samples.items():
        assert ids.matches(kind, value), (kind, value)


def test_embedded_references_are_recoverable():
    inv = ids.invoice_id("VND-00042", 137)
    assert ids.vendor_of_invoice(inv) == "VND-00042"
    assert ids.parent_of_line(ids.invoice_line_id(inv, 2)) == inv
    assert ids.parent_of_line(ids.po_line_id("PO-2026-000009", 1)) == "PO-2026-000009"
    assert ids.parent_of_line(ids.grn_line_id("GRN-2026-000003", 4)) == "GRN-2026-000003"


def test_unresolved_vendor_code_is_reserved():
    inv = ids.invoice_id(ids.UNRESOLVED_VENDOR, 12)
    assert inv == "INV-VND-00000-2026-000012" and ids.matches("invoice_id", inv)
    with pytest.raises(ValueError):
        ids.vendor_id(0)  # real vendor counters start at 1, so VND-00000 never collides


@pytest.mark.parametrize("bad", [0, -1, 100000])
def test_counters_refuse_overflow_and_non_positive(bad):
    with pytest.raises(ValueError):
        ids.vendor_id(bad)


def test_money_rounds_half_up_and_rejects_floats():
    assert money("2.675") == Decimal("2.68")   # exact decimal, so no binary surprise
    assert money("0.005") == Decimal("0.01")
    assert line_net(D("3"), D("33.335")) == Decimal("100.01")
    assert tax_amount(D("100.01"), D("18")) == Decimal("18.00")
    assert qty("2.345", "KG") == Decimal("2.35") and qty("2.5", "EA") == Decimal("3")
    assert fmt(Decimal("1234.5")) == "1234.50"
    assert round_half_up_int(5, 2) == 3 and round_half_up_int(4, 3) == 1
    with pytest.raises(TypeError):
        D(1.1)


def test_tolerance_is_inclusive_at_the_boundary():
    po = D("100.00")
    assert within_pct(D("102.00"), po, D("2.00"))        # exactly at +2%
    assert within_pct(D("101.99"), po, D("2.00"))        # just inside
    assert not within_pct(D("102.01"), po, D("2.00"))    # just outside
    assert within_pct(D("98.00"), po, D("2.00")) and not within_pct(D("97.99"), po, D("2.00"))
    assert pct_change(D("102.01"), po) == Decimal("2.01")
