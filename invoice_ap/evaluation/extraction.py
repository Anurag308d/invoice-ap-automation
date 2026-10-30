"""E1/E2 extraction evaluation: captured values vs the invoices as issued (source/), per field, per
channel and per document, with every mismatch listed (R34a, evaluation_plan section 2).

A mismatch is *flagged* when the document went to capture review, the field itself is below the
CAP-01 threshold, or (for vendor fields) VEN-01 raised VENDOR_NOT_FOUND. A *silent error* is a
mismatch that is not flagged: the target is zero. Degraded scans (CAPTURE_REVIEW) are expected to
be flagged; every other document is expected to match on every field.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path

from ..spec.io import read_table

HEADER_COMPARE = ("vendor_id", "invoice_id", "vendor_name", "vendor_tax_id", "vendor_invoice_number", "invoice_date",
                  "po_id", "attention_user_id", "currency", "header_net_amount", "header_tax_amount",
                  "header_gross_amount", "line_count")
LINE_COMPARE = ("po_line_id", "sku_id", "description", "uom", "quantity", "unit_price", "line_net_amount", "tax_code",
                "tax_amount")
SOURCE_OF = {"line_net_amount": "line_net_amount"}
EXTRACTED_AS = {"vendor_id": "vendor_tax_id", "invoice_id": "vendor_tax_id", "po_id": "po_number",
                "po_line_id": "po_line_number", "line_count": "line_items"}
NUMERIC = {"header_net_amount", "header_tax_amount", "header_gross_amount", "quantity", "unit_price",
           "line_net_amount", "tax_amount", "line_count"}
VENDOR_FIELDS = {"vendor_id", "invoice_id", "vendor_name", "vendor_tax_id"}


def _same(field: str, a: str, b: str) -> bool:
    if field in NUMERIC and a and b:
        return Decimal(a) == Decimal(b)
    if field == "vendor_name":
        return a.casefold() == b.casefold()
    return a == b


def _pct(n: int, d: int) -> str:
    return f"{(Decimal(n) * 100 / Decimal(d)).quantize(Decimal('0.01'))}%" if d else "-"


def evaluate(root: Path, threshold: Decimal = Decimal("0.90")) -> dict:
    root = Path(root)
    src = {r["doc_id"]: r for r in read_table(root / "source", "invoice")}
    src_lines = defaultdict(dict)
    for r in read_table(root / "source", "invoice_line"):
        src_lines[r["invoice_id"]][int(r["line_number"])] = r
    vendors = {v["vendor_id"]: v for v in read_table(root / "master", "vendor")}
    degraded = {g["doc_id"] for g in read_table(root / "ground_truth", "ground_truth")
                if g["scenario_category"] == "CAPTURE_REVIEW"}
    expected_capture = {g["doc_id"] for g in read_table(root / "ground_truth", "ground_truth")
                        if "EXT_LOW_CONFIDENCE" in g["expected_issue_types"].split("|")}
    cap = {c["doc_id"]: c for c in read_table(root / "processed", "captured_invoice")}
    cap_lines = defaultdict(dict)
    for r in read_table(root / "processed", "captured_invoice_line"):
        cap_lines[r["invoice_id"]][int(r["line_number"])] = r
    conf = {}
    for f in read_table(root / "processed", "extraction_field"):
        conf[(f["doc_id"], f["invoice_line_id"], f["field_name"])] = (Decimal(f["confidence"]), f["is_low_confidence"])
    channel_of = {m["doc_id"]: m["channel"] for m in read_table(root / "inbox", "intake_manifest")}

    per_field = defaultdict(Counter)
    per_channel = defaultdict(Counter)
    buckets = defaultdict(Counter)
    mismatches, doc_ok, doc_bad = [], Counter(), set()
    for doc_id, s in sorted(src.items()):
        c, channel = cap[doc_id], channel_of[doc_id]
        v = vendors[s["vendor_id"]]
        truth = dict(s, vendor_name=v["vendor_name"], vendor_tax_id=v["tax_registration_id"])
        gated = c["capture_status"] == "LOW_CONFIDENCE"
        pairs = [(None, f, truth[f], c[f]) for f in HEADER_COMPARE]
        for n, sl in sorted(src_lines[s["invoice_id"]].items()):
            cl = cap_lines[c["invoice_id"]].get(n)
            line_ref = cl["invoice_line_id"] if cl else None
            pairs += [(line_ref or f"line {n} (not captured)", f, sl[SOURCE_OF.get(f, f)], cl[f] if cl else "")
                      for f in LINE_COMPARE]
        extra = set(cap_lines[c["invoice_id"]]) - set(src_lines[s["invoice_id"]])
        pairs += [(f"line {n} (extra)", "line_count", "", str(n)) for n in sorted(extra)]
        doc_match = True
        for line_ref, field, expected, got in pairs:
            ok = _same(field, expected, got)
            key = (doc_id, line_ref if line_ref and line_ref.startswith("INVL-") else "",
                   EXTRACTED_AS.get(field, field))
            fc, low = conf.get(key, ("not printed", "false"))   # an absent field is never "flagged"
            flagged = gated or low == "true" or (field in VENDOR_FIELDS and not c["vendor_id"])
            per_field[field]["fields"] += 1
            per_field[field]["match"] += ok
            per_channel[channel]["fields"] += 1
            per_channel[channel]["match"] += ok
            buckets[str(fc)]["fields"] += 1
            buckets[str(fc)]["match"] += ok
            if not ok:
                doc_match = False
                per_field[field]["silent"] += not flagged
                per_channel[channel]["silent"] += not flagged
                mismatches.append({"doc_id": doc_id, "channel": channel, "invoice_line": line_ref or "", "field": field,
                                   "expected": expected, "captured": got, "flagged": flagged,
                                   "degraded_scan": doc_id in degraded})
        per_channel[channel]["documents"] += 1
        per_channel[channel]["documents_exact"] += doc_match
        doc_ok["exact"] += doc_match
        if not doc_match:
            doc_bad.add(doc_id)
    routed = {d for d, c in cap.items() if c["capture_status"] == "LOW_CONFIDENCE"}
    silent = [m for m in mismatches if not m["flagged"]]
    non_degraded_bad = sorted(doc_bad - degraded)
    report = {
        "documents": len(src), "documents_exact": doc_ok["exact"],
        "document_exact_rate": _pct(doc_ok["exact"], len(src)),
        "non_degraded_documents": len(src) - len(degraded),
        "non_degraded_documents_with_mismatch": non_degraded_bad,
        "degraded_scans": len(degraded), "degraded_scans_flagged": len(degraded & routed),
        "silent_errors": len(silent),
        "fields_compared": sum(c["fields"] for c in per_field.values()),
        "field_match_rate": _pct(sum(c["match"] for c in per_field.values()),
                                 sum(c["fields"] for c in per_field.values())),
        "vendor_resolution_rate": _pct(per_field["vendor_id"]["match"], per_field["vendor_id"]["fields"]),
        "invoice_id_agreement_rate": _pct(per_field["invoice_id"]["match"], per_field["invoice_id"]["fields"]),
        "per_field": {f: {"fields": c["fields"], "match": c["match"], "accuracy": _pct(c["match"], c["fields"]),
                          "silent_errors": c["silent"]} for f, c in per_field.items()},
        "per_channel": {ch: {"documents": c["documents"], "documents_exact": c["documents_exact"],
                             "fields": c["fields"], "accuracy": _pct(c["match"], c["fields"]),
                             "silent_errors": c["silent"]} for ch, c in sorted(per_channel.items())},
        "confidence_calibration": {b: {"fields": c["fields"], "accuracy": _pct(c["match"], c["fields"])}
                                   for b, c in sorted(buckets.items(), key=lambda kv: Decimal(kv[0]) if kv[0][0].isdigit() else Decimal(-1),
                                          reverse=True)},
        "capture_routing": {"routed": len(routed), "documents_with_any_mismatch": len(doc_bad),
                            "precision": _pct(len(routed & doc_bad), len(routed)),
                            "recall": _pct(len(routed & doc_bad), len(doc_bad)),
                            "routed_equals_ground_truth": routed == expected_capture},
        "threshold": str(threshold),
        "mismatches": mismatches,
    }
    return report


def to_markdown(r: dict, title: str) -> str:
    out = [f"# {title}", "",
           f"- Documents: {r['documents']}; exact document match {r['documents_exact']} ({r['document_exact_rate']}).",
           f"- Non-degraded documents with any mismatch: {len(r['non_degraded_documents_with_mismatch'])} "
           f"(target 0).",
           f"- Degraded scans: {r['degraded_scans']}, flagged for capture review: {r['degraded_scans_flagged']}.",
           f"- Fields compared: {r['fields_compared']}; field match rate {r['field_match_rate']}.",
           f"- **Silent errors: {r['silent_errors']}** (mismatch without a flag; target 0).",
           f"- Vendor resolution (VEN-01): {r['vendor_resolution_rate']}; invoice ID agreement (ID-01): "
           f"{r['invoice_id_agreement_rate']}.",
           f"- Capture routing: {r['capture_routing']['routed']} routed; precision {r['capture_routing']['precision']},"
           f" recall {r['capture_routing']['recall']}; equals ground truth: "
           f"{r['capture_routing']['routed_equals_ground_truth']}.", "",
           "## Per channel", "", "| Channel | Documents | Exact | Fields | Accuracy | Silent errors |",
           "|---|---|---|---|---|---|"]
    out += [f"| {ch} | {c['documents']} | {c['documents_exact']} | {c['fields']} | {c['accuracy']} | "
            f"{c['silent_errors']} |" for ch, c in r["per_channel"].items()]
    out += ["", "## Per field", "", "| Field | Compared | Match | Accuracy | Silent errors |", "|---|---|---|---|---|"]
    out += [f"| {f} | {c['fields']} | {c['match']} | {c['accuracy']} | {c['silent_errors']} |"
            for f, c in r["per_field"].items()]
    out += ["", "## Confidence calibration", "", "| Confidence | Fields | Accuracy |", "|---|---|---|"]
    out += [f"| {b} | {c['fields']} | {c['accuracy']} |" for b, c in r["confidence_calibration"].items()]
    out += ["", "## Mismatches", "", "| Document | Channel | Line | Field | Source | Captured | Flagged |",
            "|---|---|---|---|---|---|---|"]
    out += [f"| {m['doc_id']} | {m['channel']} | {m['invoice_line']} | {m['field']} | {m['expected']} | "
            f"{m['captured']} | {'yes' if m['flagged'] else '**NO**'} |" for m in r["mismatches"]]
    return "\n".join(out) + "\n"
