"""The volume and mix math is exact and feasible at both scales."""
from __future__ import annotations

import pytest

from invoice_ap.common import enums
from invoice_ap.common.docsync import block_in_sync
from invoice_ap.common.paths import DOCS_DIR
from invoice_ap.generator.allocation import (ARCHETYPES, AllocationError, allocate, apportion,
                                             line_histogram)
from invoice_ap.generator.allocation_report import render_markdown
from invoice_ap.generator.catalogue import CATEGORY_WEIGHTS, SUBSCENARIOS

SCALES = ["full", "starter", "0.25", "0.5", "2"]
PLACEMENTS = {"S11", "PAIR11", "S22_2", "SPLIT_PARTIAL", "SPLIT_FINAL", "S21", "S12", "F", "NPO", "DUP"}


def test_full_scale_volumes_are_the_assignment_numbers():
    t = allocate("full").targets
    assert (t.vendors, t.pos, t.po_lines, t.grns, t.invoices) == (300, 1500, 2200, 1800, 2000)


def test_starter_scale_is_one_tenth():
    t = allocate("starter").targets
    assert (t.vendors, t.pos, t.po_lines, t.grns, t.invoices) == (30, 150, 220, 180, 200)


def test_full_scale_mix_is_exact():
    cats = allocate("full").categories
    assert cats == {"CLEAN": 1350, "PRICE_VARIANCE": 200, "QTY_MISMATCH": 160, "DUPLICATE": 100,
                    "MISSING_RECEIPT": 80, "TAX_VENDOR": 60, "ARITHMETIC": 20, "INVOICE_BEFORE_PO": 20,
                    "CAPTURE_REVIEW": 10}
    assert cats["CLEAN"] >= 1340  # floor for the carve-out variant (67%)
    # the five named exception categories hit their exact shares: 10/8/5/4/3 percent
    assert [cats[c] * 100 // 2000 for c in ("PRICE_VARIANCE", "QTY_MISMATCH", "DUPLICATE",
                                            "MISSING_RECEIPT", "TAX_VENDOR")] == [10, 8, 5, 4, 3]


@pytest.mark.parametrize("scale", SCALES)
def test_every_identity_holds(scale):
    a = allocate(scale)
    t = a.targets
    assert sum(a.categories.values()) == t.invoices
    assert sum(a.subscenarios.values()) == t.invoices
    for category in a.categories:
        assert sum(a.subscenarios[s.code] for s in SUBSCENARIOS if s.category == category) \
            == a.categories[category]
    arch = a.archetypes
    assert sum(arch.values()) == t.pos
    assert sum(n * ARCHETYPES[k][0] for k, n in arch.items()) == t.grns
    assert sum(n * ARCHETYPES[k][1] for k, n in arch.items()) == a.po_backed_originals
    assert a.po_backed_originals + a.non_po_originals + a.duplicates == t.invoices
    assert sum(a.subscenarios[s.code] for s in SUBSCENARIOS if s.placement == "NPO") == a.non_po_originals
    assert sum(a.subscenarios[s.code] for s in SUBSCENARIOS if s.placement == "DUP") == a.duplicates
    assert a.subscenarios["MR-NO-GRN"] == arch["A01"]
    assert a.subscenarios["C-CONSOLIDATED"] == arch["A21"]
    assert a.subscenarios["C-PARTIAL-BILLING"] == 2 * arch["A12"]
    s22 = sum(a.subscenarios[s.code] for s in SUBSCENARIOS if s.placement == "S22_2")
    assert s22 <= arch["A22"]
    assert a.subscenarios["C-SPLIT-PARTIAL"] + a.subscenarios["C-SPLIT-FINAL"] + s22 \
        == 2 * arch["A22"] + 3 * arch["A33"]
    s11 = sum(a.subscenarios[s.code] for s in SUBSCENARIOS if s.placement in ("S11", "PAIR11"))
    assert s11 == arch["A11"]
    assert a.subscenarios["C-TN-SAME-DAY"] % 2 == 0
    assert sum(a.line_histogram.values()) == t.pos
    assert sum(k * n for k, n in a.line_histogram.items()) == t.po_lines
    assert set(a.line_histogram) == set(range(1, 9))
    assert sum(a.vendor_tiers.values()) == sum(a.vendor_segments.values()) == t.vendors


@pytest.mark.parametrize("scale", ["full", "starter"])
def test_every_scenario_and_edge_case_appears_at_least_once(scale):
    a = allocate(scale)
    assert min(a.subscenarios.values()) >= 1
    for ec in enums.EDGE_CASES:
        assert sum(a.subscenarios[s.code] for s in SUBSCENARIOS if ec in s.edge_cases) >= 1, ec
    assert a.line_histogram[1] >= 1 and a.line_histogram[8] >= 1
    assert a.subscenarios["C-NPO-RECURRING"] >= 2  # a recurring series needs two invoices


def test_each_edge_case_has_at_least_ten_invoices_at_full_scale():
    a = allocate("full")  # >= 10 at full scale, >= 1 at starter (previous test)
    for ec in enums.EDGE_CASES:
        assert sum(a.subscenarios[s.code] for s in SUBSCENARIOS if ec in s.edge_cases) >= 10, ec


@pytest.mark.parametrize("scale", ["full", "starter"])
def test_many_to_many_bridge_is_exercised_in_both_directions(scale):
    a = allocate(scale)  # A21: 1 invoice line -> 2 GRN lines; A12: 1 GRN line -> 2 invoice lines
    assert a.archetypes["A21"] >= 1 and a.archetypes["A12"] >= 1
    if scale == "full":
        assert a.archetypes["A12"] >= 10


def test_allocation_is_deterministic():
    assert allocate("starter") == allocate("starter")
    assert allocate("full") == allocate("full")


def test_apportion_is_exact_and_honours_minimums():
    assert apportion(10, [("a", 1), ("b", 1), ("c", 1)]) == {"a": 4, "b": 3, "c": 3}
    assert apportion(6, [("a", 15), ("b", 5), ("c", 15), ("d", 10), ("e", 10), ("f", 5)]) \
        == {k: 1 for k in "abcdef"}
    assert apportion(2000, list(CATEGORY_WEIGHTS)) == dict(CATEGORY_WEIGHTS)
    with pytest.raises(AllocationError):
        apportion(2, [("a", 1), ("b", 1), ("c", 1)], minimum=1)


def test_line_histogram_rejects_infeasible_totals():
    with pytest.raises(AllocationError):
        line_histogram(10, 9)
    with pytest.raises(AllocationError):
        line_histogram(10, 81)
    assert sum(k * n for k, n in line_histogram(10, 80).items()) == 80


def test_tiny_scale_fails_loudly_instead_of_dropping_scenarios():
    with pytest.raises(AllocationError):
        allocate("0.01")


def test_catalogue_is_consistent_with_vocabulary():
    assert tuple(s.code for s in SUBSCENARIOS) == enums.SCENARIO_CODES
    assert tuple(c for c, _ in CATEGORY_WEIGHTS) == enums.SCENARIO_CATEGORIES
    for s in SUBSCENARIOS:
        assert s.category in enums.SCENARIO_CATEGORIES
        assert s.placement in PLACEMENTS
        assert set(s.edge_cases) <= set(enums.EDGE_CASES)
        assert set(s.intended_issues) <= set(enums.EXCEPTION_TYPES)
        assert s.decision in ("APPROVAL_PATH", "HOLD", "REJECT")


def test_clean_means_no_issue_and_the_approval_path():
    """CLEAN sub-scenarios intend no issue and go to approval; every other one is held or rejected."""
    for s in SUBSCENARIOS:
        if s.category == "CLEAN":
            assert not s.intended_issues and s.decision == "APPROVAL_PATH", s.code
        else:
            assert s.intended_issues and s.decision in ("HOLD", "REJECT"), s.code


def test_generated_tables_in_docs_are_current():
    assert block_in_sync(DOCS_DIR / "data_generation.md", "allocation-tables", render_markdown()), \
        "run: python -m invoice_ap docs"
