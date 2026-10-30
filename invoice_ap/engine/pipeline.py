"""Engine entry point. Stage 3 scope: intake, extraction (CAP-01), vendor resolution (VEN-01), invoice
ID assignment (ID-01) and the sender cross-check (VEN-04), with capture-stage exceptions routed by
RTE-01. Stage 4 adds duplicates, validation, matching, approvals, payments and the event log.

The engine is given only the master and inbox folders (narrow entry point, architecture section 5).
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

from ..common.policy import Policy
from ..spec import BY_NAME
from ..spec.io import csv_bytes, read_table
from .adapters import ADAPTERS
from .capture import build_rows, field_row
from .routing import Router
from .vendor_identity import resolve

CAPTURE_LATENCY = timedelta(minutes=1)          # synthetic processing time after arrival (no wall clock)
OUTPUT_TABLES = ("captured_invoice", "captured_invoice_line", "extraction_field", "ap_exception")


def _naive(ts: str) -> datetime:
    return datetime.fromisoformat(ts[:19])


def run_engine(master_dir: Path, inbox_dir: Path, out_dir: Path, policy: Policy) -> dict:
    master_dir, inbox_dir, out_dir = Path(master_dir), Path(inbox_dir), Path(out_dir)
    threshold = Decimal(policy.raw["extraction"]["min_field_confidence"])
    sender_channels = tuple(policy.raw["vendor"]["sender_check_channels"])
    vendors = {v["tax_registration_id"]: v["vendor_id"] for v in read_table(master_dir, "vendor")}
    pos = {p["po_id"]: p for p in read_table(master_dir, "purchase_order")}
    po_lines = {p["po_line_id"] for p in read_table(master_dir, "purchase_order_line")}
    users = read_table(master_dir, "app_user")
    user_ids = {u["user_id"] for u in users}
    router = Router(policy, users)
    manifest = sorted(read_table(inbox_dir, "intake_manifest"), key=lambda m: int(m["intake_seq"]))
    out = {t: [] for t in OUTPUT_TABLES}
    trace: list[dict] = []
    n_field = 0
    for m in manifest:
        data = (inbox_dir / m["file_path"]).read_bytes()
        raw = ADAPTERS[m["file_format"]](data)
        seq = int(m["intake_seq"])
        tax_id = raw.header["vendor_tax_id"].value if "vendor_tax_id" in raw.header else None
        identity = resolve(tax_id, seq, m, vendors, sender_channels)
        captured_at = _naive(m["received_at"]) + CAPTURE_LATENCY
        invoice, lines, fields = build_rows(raw, m, identity.invoice_id, identity.vendor_id, captured_at, threshold,
                                            set(pos), po_lines, user_ids)
        out["captured_invoice"].append(invoice)
        out["captured_invoice_line"] += lines
        for line_id, name, ext in fields:
            n_field += 1
            out["extraction_field"].append(field_row(n_field, m["doc_id"], identity.invoice_id, line_id, name, ext,
                                                     threshold))
        inv_id, gated = identity.invoice_id, invoice["capture_status"] == "LOW_CONFIDENCE"
        floor = invoice["min_field_confidence"]
        low = sorted({name for _, name, ext in fields if ext.confidence < threshold})
        trace.append({"doc_id": m["doc_id"], "invoice_id": inv_id, "rule_id": "CAP-01",
                      "inputs": {"min_field_confidence": str(floor), "low_fields": low},
                      "threshold": str(threshold), "outcome": "LOW_CONFIDENCE" if gated else "OK"})
        trace.append({"doc_id": m["doc_id"], "invoice_id": inv_id, "rule_id": "VEN-01",
                      "inputs": {"printed_tax_registration_id": tax_id}, "threshold": None,
                      "outcome": identity.vendor_id or "NOT_FOUND"})
        trace.append({"doc_id": m["doc_id"], "invoice_id": inv_id, "rule_id": "ID-01",
                      "inputs": {"vendor_id": identity.vendor_id, "intake_seq": seq}, "threshold": None,
                      "outcome": inv_id})
        requester = (pos[invoice["po_id"]]["requester_id"] if invoice["po_id"] else None) or invoice["attention_user_id"]
        if gated:
            out["ap_exception"].append(router.raise_exception(
                "EXT_LOW_CONFIDENCE", inv_id, captured_at, primary=True, expected=f">= {threshold}",
                actual=f"{floor} ({', '.join(low)})", tolerance=str(threshold)))
            continue                                   # CAP-01 is a gate: no later check trusts these values
        if identity.vendor_id is None:
            out["ap_exception"].append(router.raise_exception(
                "VENDOR_NOT_FOUND", inv_id, captured_at, primary=True, expected="vendor master tax registration",
                actual=tax_id))
            continue                                   # VEN-01 is a gate
        trace.append({"doc_id": m["doc_id"], "invoice_id": inv_id, "rule_id": "VEN-04",
                      "inputs": {"channel": m["channel"], "checked": identity.sender_checked}, "threshold": None,
                      "outcome": "MISMATCH" if identity.sender_mismatch else ("MATCH" if identity.sender_checked
                                                                              else "NOT_APPLICABLE")})
        if identity.sender_mismatch:
            out["ap_exception"].append(router.raise_exception(
                "VENDOR_SENDER_MISMATCH", inv_id, captured_at, primary=True, expected=identity.sender_vendor,
                actual=identity.vendor_id, requester=requester))
    out_dir.mkdir(parents=True, exist_ok=True)
    digests = {}
    for table in OUTPUT_TABLES:
        data = csv_bytes(table, out[table])
        (out_dir / f"{table}.csv").write_bytes(data)
        digests[BY_NAME[table].file] = hashlib.sha256(data).hexdigest()
    lines = "".join(json.dumps(t, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n" for t in trace)
    (out_dir / "decision_trace.jsonl").write_bytes(lines.encode("utf-8"))
    digests["processed/decision_trace.jsonl"] = hashlib.sha256(lines.encode("utf-8")).hexdigest()
    return {"documents": len(manifest), "low_confidence": sum(1 for i in out["captured_invoice"]
                                                              if i["capture_status"] == "LOW_CONFIDENCE"),
            "vendor_not_found": sum(1 for i in out["captured_invoice"] if i["vendor_id"] is None),
            "exceptions": len(out["ap_exception"]), "sha256": digests}
