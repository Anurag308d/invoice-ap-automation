"""Render the exact allocation tables (both scales) as markdown for docs/data_generation.md."""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from ..common.enums import EDGE_CASES
from .allocation import ARCHETYPES, Allocation, allocate
from .catalogue import CATEGORY_WEIGHTS, SUBSCENARIOS

TARGET_SHARES = {"CLEAN": "~70%", "PRICE_VARIANCE": "10%", "QTY_MISMATCH": "8%",
                 "DUPLICATE": "5%", "MISSING_RECEIPT": "4%", "TAX_VENDOR": "3%",
                 "ARITHMETIC": "(edge case EC-02)", "INVOICE_BEFORE_PO": "(edge case EC-03)",
                 "CAPTURE_REVIEW": "(degraded scans)"}


def _pct(part: int, whole: int) -> str:
    if not whole:
        return "-"
    value = (Decimal(part) * 100 / Decimal(whole)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    return f"{value:f}%"


def _table(header: list[str], rows: list[list[object]]) -> str:
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    lines += ["| " + " | ".join(str(c) for c in row) + " |" for row in rows]
    return "\n".join(lines)


def render_markdown(full: Allocation | None = None, starter: Allocation | None = None) -> str:
    f = full or allocate("full")
    s = starter or allocate("starter")
    out: list[str] = []

    out.append("**Table G1 - table totals** (starter = round_half_up(full x 0.1))\n")
    names = ("vendors", "pos", "po_lines", "grns", "invoices")
    out.append(_table(["Table", "Full", "Starter"],
                      [[n, getattr(f.targets, n), getattr(s.targets, n)] for n in names]))

    out.append("\n**Table G2 - scenario-category mix** (one primary category per invoice)\n")
    rows = [[c, TARGET_SHARES[c], f.categories[c], _pct(f.categories[c], f.targets.invoices),
             s.categories[c], _pct(s.categories[c], s.targets.invoices)] for c, _ in CATEGORY_WEIGHTS]
    rows.append(["**Total**", "100%", f.targets.invoices, "100.0%", s.targets.invoices, "100.0%"])
    out.append(_table(["Category", "Target", "Full", "Full %", "Starter", "Starter %"], rows))

    out.append("\n**Table G3 - invoice population split**\n")
    out.append(_table(["Population", "Full", "Starter"], [
        ["Duplicate documents (DUPLICATE category)", f.duplicates, s.duplicates],
        ["Non-PO original invoices (5% of invoices)", f.non_po_originals, s.non_po_originals],
        ["PO-backed original invoices", f.po_backed_originals, s.po_backed_originals],
        ["**Total invoice documents**", f.targets.invoices, s.targets.invoices]]))

    out.append("\n**Table G4 - PO fulfilment archetypes** (solves the PO, GRN and invoice identities exactly)\n")
    rows = []
    tot = {"f": [0, 0, 0], "s": [0, 0, 0]}
    for code, (g, i, desc) in ARCHETYPES.items():
        nf, ns = f.archetypes[code], s.archetypes[code]
        rows.append([code, desc, g, i, nf, nf * g, nf * i, ns, ns * g, ns * i])
        for key, n in (("f", nf), ("s", ns)):
            tot[key][0] += n
            tot[key][1] += n * g
            tot[key][2] += n * i
    rows.append(["**Total**", "", "", "", *tot["f"], *tot["s"]])
    out.append(_table(["Archetype", "Meaning", "GRNs/PO", "Invoices/PO", "Full POs", "Full GRNs",
                       "Full invoices", "Starter POs", "Starter GRNs", "Starter invoices"], rows))

    out.append("\n**Table G5 - PO line-count histogram** (each PO has 1-8 lines)\n")
    rows = [[k, f.line_histogram[k], k * f.line_histogram[k], s.line_histogram[k],
             k * s.line_histogram[k]] for k in range(1, 9)]
    rows.append(["**Total**", sum(f.line_histogram.values()),
                 sum(k * n for k, n in f.line_histogram.items()), sum(s.line_histogram.values()),
                 sum(k * n for k, n in s.line_histogram.items())])
    out.append(_table(["Lines per PO", "Full POs", "Full lines", "Starter POs", "Starter lines"], rows))

    out.append("\n**Table G6 - sub-scenario allocation** (intended labels are asserted against the oracle)\n")
    rows = [[sc.code, sc.category, sc.placement, ", ".join(sc.edge_cases) or "-",
             ", ".join(sc.intended_issues) or "none", sc.decision,
             f.subscenarios[sc.code], s.subscenarios[sc.code]] for sc in SUBSCENARIOS]
    rows.append(["**Total**", "", "", "", "", "", sum(f.subscenarios.values()),
                 sum(s.subscenarios.values())])
    out.append(_table(["Sub-scenario", "Category", "Placement", "Edge cases", "Intended issue labels",
                       "Decision", "Full", "Starter"], rows))

    out.append("\n**Table G7 - required edge-case coverage**\n")
    rows = []
    for ec, name in EDGE_CASES.items():
        codes = [sc.code for sc in SUBSCENARIOS if ec in sc.edge_cases]
        rows.append([ec, name, ", ".join(codes), sum(f.subscenarios[c] for c in codes),
                     sum(s.subscenarios[c] for c in codes)])
    out.append(_table(["Edge case", "Assignment wording", "Sub-scenarios", "Full", "Starter"], rows))

    out.append("\n**Table G8 - vendor mix**\n")
    rows = [[k, f.vendor_tiers[k], s.vendor_tiers[k]] for k in f.vendor_tiers]
    rows += [[f"segment {k}", f.vendor_segments[k], s.vendor_segments[k]] for k in f.vendor_segments]
    out.append(_table(["Vendor group", "Full", "Starter"], rows))
    return "\n".join(out) + "\n"
