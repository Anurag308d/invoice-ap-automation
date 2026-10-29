"""Exact volume and scenario-mix allocation for the synthetic dataset.

Pure integer and Fraction arithmetic: no randomness and no floats. Given a scale it returns exact
counts for every table total, PO fulfilment archetype, PO line-count histogram, scenario category
and sub-scenario. The Stage-2 generator consumes these counts and only uses its seeded RNG to
decide *which* PO, vendor or date gets each slot, never *how many*. docs/data_generation.md embeds
the tables rendered by render_markdown(); tests/test_allocation.py proves every identity.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from fractions import Fraction
from typing import Mapping, Sequence

from .catalogue import CATEGORY_WEIGHTS, CLEAN_S11_PAIRS_FULL, SUBSCENARIOS, SubScenario


class AllocationError(ValueError):
    """Raised when a scale cannot satisfy the exact-count or coverage constraints."""


@dataclass(frozen=True)
class Targets:
    vendors: int
    pos: int
    po_lines: int
    grns: int
    invoices: int


FULL = Targets(vendors=300, pos=1500, po_lines=2200, grns=1800, invoices=2000)
SCALES: dict[str, Fraction] = {"full": Fraction(1), "starter": Fraction(1, 10)}
MAX_LINES_PER_PO = 8
# Full-scale PO line-count histogram (1..8 lines). It is the weight vector at every scale.
LINE_WEIGHTS = ((1, 1090), (2, 260), (3, 80), (4, 35), (5, 15), (6, 10), (7, 5), (8, 5))
NON_PO_SHARE = Fraction(5, 100)        # share of all invoices that are non-PO originals
OPEN_PO_SHARE = Fraction(4, 100)       # POs neither received nor invoiced at the as-of date
THREE_DELIVERY_SHARE = Fraction(1, 30)  # POs delivered and invoiced in three parts
VENDOR_TIER_WEIGHTS = (("STRATEGIC", 10), ("CORE", 30), ("TAIL", 60))
VENDOR_SEGMENT_WEIGHTS = (("GOODS", 90), ("SERVICES", 10))

# PO fulfilment archetypes: (GRNs per PO, original invoices per PO)
ARCHETYPES = {
    "A11": (1, 1, "single delivery, single invoice"),
    "A22": (2, 2, "split delivery, one invoice per delivery"),
    "A33": (3, 3, "three deliveries, one invoice per delivery"),
    "A21": (2, 1, "split delivery, one consolidated invoice (N:M allocation)"),
    "A01": (0, 1, "invoiced but never received (missing receipt)"),
    "A10": (1, 0, "received, invoice not yet arrived at the as-of date"),
    "A00": (0, 0, "open PO: neither received nor invoiced at the as-of date"),
}


def round_half_up(x: Fraction) -> int:
    if x < 0:
        raise AllocationError("negative quantity")
    return math.floor(x + Fraction(1, 2))


def parse_scale(scale: str | int | Fraction) -> tuple[str, Fraction]:
    """'full' (factor 1), 'starter' (factor 1/10) or an explicit factor such as '0.25'."""
    if isinstance(scale, str) and scale in SCALES:
        return scale, SCALES[scale]
    factor = Fraction(str(scale))
    if not Fraction(0) < factor <= Fraction(5):
        raise AllocationError(f"scale factor must be in (0, 5], got {scale!r}")
    return f"x{factor}", factor


def scale_targets(factor: Fraction) -> Targets:
    return Targets(*(round_half_up(Fraction(v) * factor) for v in (
        FULL.vendors, FULL.pos, FULL.po_lines, FULL.grns, FULL.invoices)))


def apportion(total: int, weights: Sequence[tuple[str, int]],
              minimum: int | Mapping[str, int] = 1) -> dict[str, int]:
    """Largest-remainder (Hamilton) apportionment with exact integer arithmetic.

    Ties go to the earlier key. Minimums are then enforced by moving single units from the
    largest bucket that can spare one (ties: earlier key). Result always sums to total.
    """
    keys = [k for k, _ in weights]
    wsum = sum(w for _, w in weights)
    mins = {k: (minimum if isinstance(minimum, int) else minimum.get(k, 0)) for k in keys}
    if wsum <= 0 or total < sum(mins.values()):
        raise AllocationError(f"cannot apportion {total} over {keys} with minimums {mins}")
    counts = {k: total * w // wsum for k, w in weights}
    remainders = {k: total * w % wsum for k, w in weights}
    leftover = total - sum(counts.values())
    order = sorted(range(len(keys)), key=lambda i: (-remainders[keys[i]], i))
    for i in order[:leftover]:
        counts[keys[i]] += 1
    for k in keys:
        while counts[k] < mins[k]:
            donor = max((j for j, d in enumerate(keys) if counts[d] > mins[d]),
                        key=lambda j: (counts[keys[j]], -j))
            counts[keys[donor]] -= 1
            counts[k] += 1
    assert sum(counts.values()) == total
    return counts


def line_histogram(pos: int, lines: int) -> dict[int, int]:
    """Exact PO line-count histogram: skewed weights, then a deterministic repair to the total."""
    if not pos <= lines <= MAX_LINES_PER_PO * pos:
        raise AllocationError(f"{lines} lines cannot be spread over {pos} POs with 1..8 lines each")
    mins = {"1": 1, "8": 1} if pos >= 2 else {"1": 1}
    raw = apportion(pos, [(str(k), w) for k, w in LINE_WEIGHTS], minimum=mins)
    hist = {int(k): v for k, v in raw.items()}
    floor = {k: mins.get(str(k), 0) for k in hist}
    diff = lines - sum(k * n for k, n in hist.items())
    def movable(ks: range) -> int:
        # Prefer keeping the 1-line and 8-line coverage floors; relax them only when the
        # requested total leaves no other choice (for example every PO needing 8 lines).
        return next((k for k in ks if hist[k] > floor[k]), None) or next(k for k in ks if hist[k] > 0)

    while diff > 0:  # move one PO up one line count, from the smallest movable bucket
        k = movable(range(1, MAX_LINES_PER_PO))
        hist[k] -= 1
        hist[k + 1] += 1
        diff -= 1
    while diff < 0:  # move one PO down one line count, from the smallest movable bucket >= 2
        k = movable(range(2, MAX_LINES_PER_PO + 1))
        hist[k] -= 1
        hist[k - 1] += 1
        diff += 1
    return hist


@dataclass(frozen=True)
class Allocation:
    scale: str
    factor: Fraction
    targets: Targets
    categories: dict[str, int]
    subscenarios: dict[str, int]
    archetypes: dict[str, int]
    line_histogram: dict[int, int]
    non_po_originals: int
    po_backed_originals: int
    duplicates: int
    vendor_tiers: dict[str, int]
    vendor_segments: dict[str, int]
    clean_pairs: int

    def subscenario(self, code: str) -> SubScenario:
        return next(s for s in SUBSCENARIOS if s.code == code)


def _subs(category: str) -> list[SubScenario]:
    return [s for s in SUBSCENARIOS if s.category == category]


def allocate(scale: str | int | Fraction = "full") -> Allocation:
    label, factor = parse_scale(scale)
    t = scale_targets(factor)
    cats = apportion(t.invoices, CATEGORY_WEIGHTS, minimum=1)
    subs: dict[str, int] = {}
    for category, count in cats.items():
        if category == "CLEAN":
            continue  # CLEAN is resolved from the PO structure below
        subs.update(apportion(count, [(s.code, s.full_weight) for s in _subs(category)], 1))

    dup = cats["DUPLICATE"]
    npo = round_half_up(t.invoices * NON_PO_SHARE)
    npo_anomalies = sum(subs[s.code] for s in SUBSCENARIOS if s.placement == "NPO" and s.code in subs)
    npo_clean_specs = [s for s in _subs("CLEAN") if s.placement == "NPO"]
    subs.update(apportion(npo - npo_anomalies, [(s.code, s.full_weight) for s in npo_clean_specs],
                          {"C-NPO-RECURRING": 2, "C-NPO-ONEOFF": 1}))
    po_backed = t.invoices - dup - npo
    missing = subs["MR-NO-GRN"]

    # Archetype counts solve three linear identities exactly (see docs/data_generation.md):
    #   POs:      n11 + n22 + n33 + n21 + n01 + n10 + n00 = pos
    #   GRNs:     n11 + 2*n22 + 3*n33 + 2*n21 + n10      = grns
    #   invoices: n11 + 2*n22 + 3*n33 + n21 + n01        = po_backed originals
    n01 = missing
    spare = t.grns - po_backed + n01                    # = n21 + n10
    if spare < 0:
        raise AllocationError("too few GRNs for the PO-backed invoices")
    n21, n10 = spare // 2, spare - spare // 2
    n00 = round_half_up(t.pos * OPEN_PO_SHARE)
    n33 = round_half_up(t.pos * THREE_DELIVERY_SHARE)
    n22 = po_backed - t.pos + n10 + n00 - 2 * n33
    n11 = po_backed - n01 - n21 - 2 * n22 - 3 * n33
    arch = {"A11": n11, "A22": n22, "A33": n33, "A21": n21, "A01": n01, "A10": n10, "A00": n00}
    if min(arch.values()) < 0:
        raise AllocationError(f"infeasible archetype counts {arch}")

    s22_demand = sum(subs[s.code] for s in SUBSCENARIOS if s.placement == "S22_2" and s.code in subs)
    if s22_demand > n22:
        raise AllocationError("not enough split-delivery POs for second-invoice scenarios")
    s11_anomalies = sum(subs[s.code] for s in SUBSCENARIOS
                        if s.placement == "S11" and s.category != "CLEAN")
    clean_s11 = n11 - s11_anomalies
    pairs = max(1, round_half_up(CLEAN_S11_PAIRS_FULL * factor))
    clean_s11_specs = [s for s in _subs("CLEAN") if s.placement == "S11"]
    if clean_s11 - 2 * pairs < len(clean_s11_specs):
        raise AllocationError("scale too small to cover every clean single-delivery scenario")
    subs["C-TN-SAME-DAY"] = 2 * pairs
    subs.update(apportion(clean_s11 - 2 * pairs,
                          [(s.code, s.full_weight) for s in clean_s11_specs], 1))
    subs["C-SPLIT-PARTIAL"] = n22 + 2 * n33            # first of two, first two of three
    subs["C-SPLIT-FINAL"] = (n22 - s22_demand) + n33    # completing invoices still clean
    subs["C-CONSOLIDATED"] = n21

    clean_total = sum(subs[s.code] for s in _subs("CLEAN"))
    if clean_total != cats["CLEAN"]:
        raise AllocationError(f"clean slots {clean_total} != clean category {cats['CLEAN']}")
    ordered = {s.code: subs[s.code] for s in SUBSCENARIOS}
    return Allocation(
        scale=label, factor=factor, targets=t, categories=cats, subscenarios=ordered,
        archetypes=arch, line_histogram=line_histogram(t.pos, t.po_lines),
        non_po_originals=npo, po_backed_originals=po_backed, duplicates=dup,
        vendor_tiers=apportion(t.vendors, VENDOR_TIER_WEIGHTS, 1),
        vendor_segments=apportion(t.vendors, VENDOR_SEGMENT_WEIGHTS, 1),
        clean_pairs=pairs,
    )
