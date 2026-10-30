"""Engine entry point: every document in intake order goes through intake, extraction (CAP-01),
vendor resolution (VEN-01), invoice ID assignment (ID-01), the duplicate gates (DUP-01..03), the sender
cross-check (VEN-04) and the collected checks, then the outcome (MS-01, PRI-01), routing (RTE-01),
approvals (APR-01, APR-SIM-01), payment (PAY-01..06) and the append-only event log.

The engine is given only the master and inbox folders (narrow entry point, architecture section 5).
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

from ..common.policy import Policy
from ..spec import BY_NAME
from ..spec.io import csv_bytes, read_table
from .adapters import ADAPTERS
from .capture import build_rows, field_row
from .decide import Decider
from .master import Master
from .routing import Router
from .validate import Issue, Validator
from .vendor_identity import resolve

CAPTURE_LATENCY = timedelta(minutes=1)          # synthetic processing time after arrival (no wall clock)
OUTPUT_TABLES = ("captured_invoice", "captured_invoice_line", "extraction_field", "invoice_decision", "match_result",
                 "match_allocation", "duplicate_pair", "ap_exception", "approval", "payment", "ap_event",
                 "policy_version")


def _naive(ts: str) -> datetime:
    return datetime.fromisoformat(ts[:19])


def _trace(inv_id, doc_id, rule, inputs, outcome, threshold=None) -> dict:
    return {"doc_id": doc_id, "invoice_id": inv_id, "rule_id": rule, "inputs": inputs, "threshold": threshold,
            "outcome": outcome}


def run_engine(master_dir: Path, inbox_dir: Path, out_dir: Path, policy: Policy) -> dict:
    master_dir, inbox_dir, out_dir = Path(master_dir), Path(inbox_dir), Path(out_dir)
    threshold = Decimal(policy.raw["extraction"]["min_field_confidence"])
    sender_channels = tuple(policy.raw["vendor"]["sender_check_channels"])
    master = Master(master_dir)
    vendors = {v["tax_registration_id"]: v["vendor_id"] for v in master.vendors.values()}
    users = list(master.users.values())
    router = Router(policy, users)
    validator, decider = Validator(master, policy), Decider(master, policy, router)
    manifest = sorted(read_table(inbox_dir, "intake_manifest"), key=lambda m: int(m["intake_seq"]))
    out = {t: [] for t in ("captured_invoice", "captured_invoice_line", "extraction_field")}
    trace: list[dict] = []
    n_field = 0
    for m in manifest:
        data = (inbox_dir / m["file_path"]).read_bytes()
        raw = ADAPTERS[m["file_format"]](data)
        seq = int(m["intake_seq"])
        tax_id = raw.header["vendor_tax_id"].value if "vendor_tax_id" in raw.header else None
        identity = resolve(tax_id, seq, m, vendors, sender_channels)
        received_at = _naive(m["received_at"])
        captured_at = received_at + CAPTURE_LATENCY
        invoice, lines, fields = build_rows(raw, m, identity.invoice_id, identity.vendor_id, captured_at, threshold,
                                            set(master.pos), set(master.po_lines), set(master.users))
        out["captured_invoice"].append(invoice)
        out["captured_invoice_line"] += lines
        for line_id, name, ext in fields:
            n_field += 1
            out["extraction_field"].append(field_row(n_field, m["doc_id"], identity.invoice_id, line_id, name, ext,
                                                     threshold))
        inv_id, doc_id = identity.invoice_id, m["doc_id"]
        gated = invoice["capture_status"] == "LOW_CONFIDENCE"
        floor = invoice["min_field_confidence"]
        low = sorted({name for _, name, ext in fields if ext.confidence < threshold})
        trace.append(_trace(inv_id, doc_id, "CAP-01", {"min_field_confidence": str(floor), "low_fields": low},
                            "LOW_CONFIDENCE" if gated else "OK", str(threshold)))
        trace.append(_trace(inv_id, doc_id, "VEN-01", {"printed_tax_registration_id": tax_id},
                            identity.vendor_id or "NOT_FOUND"))
        trace.append(_trace(inv_id, doc_id, "ID-01", {"vendor_id": identity.vendor_id, "intake_seq": seq}, inv_id))
        issues, states, evaluated, duplicate = [], {}, False, None
        if gated:                                      # CAP-01 gate: no later check trusts these values
            issues.append(Issue("EXT_LOW_CONFIDENCE", expected=f">= {threshold}", actual=f"{floor} ({', '.join(low)})",
                                tolerance=str(threshold)))
        elif identity.vendor_id is None:               # VEN-01 gate
            issues.append(Issue("VENDOR_NOT_FOUND", expected="a vendor-master tax registration", actual=tax_id))
        else:
            duplicate = validator.duplicate(invoice)
            trace.append(_trace(inv_id, doc_id, "DUP-01..03", {"normalized_number": invoice["normalized_invoice_number"],
                                                               "invoice_date": str(invoice["invoice_date"]),
                                                               "gross": f"{invoice['header_gross_amount']:f}"},
                                f"{duplicate.type} of {duplicate.original}" if duplicate else "NONE"))
            if duplicate:                              # duplicate gate: never matched, never consumes receipts
                issues.append(Issue(duplicate.type, expected="no earlier document with the same keys",
                                    actual=", ".join(duplicate.keys), related=duplicate.original))
            else:
                trace.append(_trace(inv_id, doc_id, "VEN-04", {"channel": m["channel"],
                                                               "checked": identity.sender_checked},
                                    "MISMATCH" if identity.sender_mismatch else
                                    "MATCH" if identity.sender_checked else "NOT_APPLICABLE"))
                if identity.sender_mismatch:
                    issues.append(Issue("VENDOR_SENDER_MISMATCH", expected=identity.sender_vendor,
                                        actual=identity.vendor_id))
                found, states, evaluated = validator.check(invoice, lines, received_at)
                issues += found
        decision = decider.decide(invoice, lines, seq, received_at, captured_at, issues, states, evaluated, duplicate)
        trace.append(_trace(inv_id, doc_id, "DECISION", {
            "issues": [{"type": i.type, "line": i.line_id, "expected": i.expected, "actual": i.actual,
                        "variance": i.variance, "tolerance": i.tolerance, "related": i.related} for i in issues]},
            {"status_as_of": decision["status_as_of"], "primary_issue": decision["primary_issue"],
             "match_status": decision["match_status"], "approval_band": decision["approval_band"],
             "approval_levels": list(decision["approval_levels"]), "payment_id": decision["payment_id"]}))
    out.update({t: decider.out[t] for t in decider.out})
    out["ap_event"] = decider.event_rows()
    out["policy_version"] = [{"policy_version": policy.version, "policy_id": policy.id,
                              "effective_from": policy.raw["policy"]["effective_from"],
                              "as_of_date": policy.as_of_date, "sha256": policy.sha256}]
    out_dir.mkdir(parents=True, exist_ok=True)
    digests = {}
    for table in OUTPUT_TABLES:
        blob = csv_bytes(table, out[table])
        (out_dir / f"{table}.csv").write_bytes(blob)
        digests[BY_NAME[table].file] = hashlib.sha256(blob).hexdigest()
    lines_out = "".join(json.dumps(t, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n" for t in trace)
    (out_dir / "decision_trace.jsonl").write_bytes(lines_out.encode("utf-8"))
    digests["processed/decision_trace.jsonl"] = hashlib.sha256(lines_out.encode("utf-8")).hexdigest()
    decisions = out["invoice_decision"]
    return {"documents": len(manifest),
            "low_confidence": sum(1 for i in out["captured_invoice"] if i["capture_status"] == "LOW_CONFIDENCE"),
            "vendor_not_found": sum(1 for i in out["captured_invoice"] if i["vendor_id"] is None),
            "exceptions": len(out["ap_exception"]),
            "status": dict(sorted(Counter(d["status_as_of"] for d in decisions).items())),
            "sha256": digests}
