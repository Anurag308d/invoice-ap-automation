"""Quick, defect-aware self-checks over a built dataset (the full suite is suite.py).

Works on the rows exactly as written to CSV (strings), so it checks what an evaluator will read.
Deliberately labelled defects (from ground truth) are reported as "labelled", never as violations.
"""
from __future__ import annotations

import csv
import re
from collections import Counter, defaultdict
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from ..common import ids, lifecycle
from ..common.enums import UOM_DECIMALS
from ..common.money import line_net, tax_amount
from ..common.policy import Policy
from ..generator.catalogue import CATEGORY_WEIGHTS, SUBSCENARIOS
from ..generator.tables import normalize_invoice_number
from ..spec import BY_NAME, TABLES

D = Decimal
CODE = {s.code: s for s in SUBSCENARIOS}


def load(root: Path) -> dict[str, list[dict[str, str]]]:
    out = {}
    for t in TABLES:
        path = root / t.file
        if path.exists():
            with path.open(encoding="utf-8", newline="") as fh:
                out[t.name] = list(csv.DictReader(fh))
    return out


class Checks:
    def __init__(self):
        self.items = []

    def add(self, name: str, violations: list[str], labelled: list[str] = (), note: str = ""):
        self.items.append({"check": name, "status": "fail" if violations else "pass",
                           "violations": len(violations), "labelled": len(labelled),
                           "examples": violations[:5], "labelled_examples": list(labelled)[:3], "note": note})


def validate(t: dict[str, list[dict[str, str]]], policy: Policy, alloc=None) -> dict:
    c = Checks()
    gt = {r["invoice_id"]: r for r in t.get("ground_truth", [])}
    code_of = {i: r["scenario_code"] for i, r in gt.items()}
    # A labelled duplicate is a copy of its original, defects included: it inherits the original's label.
    allowed = {i: {r["scenario_code"]} | ({code_of[r["expected_duplicate_of"]]} if r["expected_duplicate_of"] else set())
               for i, r in gt.items()}
    as_of_end = datetime.fromisoformat(f"{policy.as_of_date.isoformat()}T23:59:59+05:30")
    _keys(t, c)
    _domains(t, c)
    _ids(t, c)
    _timeline(t, c, as_of_end, allowed)
    _arithmetic(t, c, allowed)
    _lifecycles(t, c)
    if gt:
        _mix(t, c, alloc)
        _intent(t, c, policy)
        _duplicates(t, c, code_of)
    status = "fail" if any(i["status"] == "fail" for i in c.items) else "pass"
    return {"status": status, "violations": sum(i["violations"] for i in c.items),
            "labelled": sum(i["labelled"] for i in c.items), "checks": c.items}


def _keys(t, c):
    dup, orphans = [], []
    for name, rows in t.items():
        spec = BY_NAME[name]
        seen = Counter(tuple(r[k] for k in spec.primary_key) for r in rows)
        dup += [f"{name} {k}" for k, n in seen.items() if n > 1]
        for group in spec.unique_together:
            seen = Counter(tuple(r[k] for k in group) for r in rows)
            dup += [f"{name} {group}={k}" for k, n in seen.items() if n > 1]
        for f in spec.fields:
            if f.unique and not (f.name,) == spec.primary_key:
                seen = Counter(r[f.name] for r in rows if r[f.name])
                dup += [f"{name}.{f.name}={k}" for k, n in seen.items() if n > 1]
    c.add("primary and unique keys", dup)
    for name, rows in t.items():
        for f in BY_NAME[name].fields:
            target, _, col = f.fk.partition(".")
            if f.fk and target in t:
                values = {r[col] for r in t[target]}
                orphans += [f"{name}.{f.name}={r[f.name]}" for r in rows if r[f.name] and r[f.name] not in values]
    c.add("foreign keys (every declared FK)", orphans)


def _domains(t, c):
    bad = []
    for name, rows in t.items():
        for f in BY_NAME[name].fields:
            pattern = re.compile(f.pattern) if f.pattern else None
            for r in rows:
                v = r[f.name]
                if v == "":
                    if f.required:                      # lists are never required: empty = none
                        bad.append(f"{name}.{f.name} empty")
                    continue
                items = v.split("|") if f.type == "list" else [v]
                if f.allowed and any(i not in f.allowed for i in items):
                    bad.append(f"{name}.{f.name}={v}")
                if pattern and not pattern.match(v):
                    bad.append(f"{name}.{f.name}={v} !~ {f.pattern}")
                if f.type in ("money", "pct") and not re.fullmatch(r"-?\d+\.\d{2}", v):
                    bad.append(f"{name}.{f.name}={v} is not d.dd")
                if f.type == "qty" and "uom" in r and len(v.partition(".")[2]) != UOM_DECIMALS[r["uom"]]:
                    bad.append(f"{name}.{f.name}={v} has the wrong precision for {r['uom']}")
                if f.type in ("money", "qty", "pct", "decimal", "int") and f.min_value and D(v) < D(f.min_value):
                    bad.append(f"{name}.{f.name}={v} < {f.min_value}")
                if f.type in ("money", "qty", "pct", "decimal", "int") and f.max_value and D(v) > D(f.max_value):
                    bad.append(f"{name}.{f.name}={v} > {f.max_value}")
    c.add("allowed values, formats, ranges, required", bad)


def _ids(t, c):
    bad = []
    for name, col, parent in (("purchase_order_line", "po_line_id", "po_id"), ("goods_receipt_line", "grn_line_id", "grn_id"),
                              ("invoice_line", "invoice_line_id", "invoice_id")):
        bad += [f"{name} {r[col]}" for r in t.get(name, []) if ids.parent_of_line(r[col]) != r[parent]]
    seq = {m["doc_id"]: int(m["intake_seq"]) for m in t.get("intake_manifest", [])}
    for inv in t.get("invoice", []):
        if ids.vendor_of_invoice(inv["invoice_id"]) != inv["vendor_id"]:
            bad.append(f"vendor code in {inv['invoice_id']} != {inv['vendor_id']}")
        if int(inv["invoice_id"][-6:]) != seq.get(inv["doc_id"]):
            bad.append(f"{inv['invoice_id']} counter != intake_seq of {inv['doc_id']}")
    for m in t.get("intake_manifest", []):
        if m["doc_id"] != ids.doc_id(int(m["intake_seq"])):
            bad.append(f"{m['doc_id']} != DOC-2026-<intake_seq>")
        if (m["channel"] in ("PORTAL", "EDI")) != bool(m["sender_vendor_id"]):
            bad.append(f"{m['doc_id']} sender_vendor_id must be set exactly for PORTAL/EDI")
    c.add("embedded IDs and intake numbering", bad)


def _timeline(t, c, as_of_end, code_of):
    bad, labelled = [], []
    po = {p["po_id"]: p for p in t.get("purchase_order", [])}
    for g in t.get("goods_receipt", []):
        if g["received_date"] < po[g["po_id"]]["po_date"] or g["posted_at"][:10] < g["received_date"]:
            bad.append(f"{g['grn_id']} before its PO or posted before receipt")
    man = {m["doc_id"]: m for m in t.get("intake_manifest", [])}
    for inv in t.get("invoice", []):
        if inv["invoice_date"] > man[inv["doc_id"]]["received_at"][:10]:
            bad.append(f"{inv['invoice_id']} dated after it was received")
        if inv["po_id"] and inv["invoice_date"] < po[inv["po_id"]]["po_date"]:
            (labelled if "DATE-INVOICE-BEFORE-PO" in code_of.get(inv["invoice_id"], ()) else bad).append(
                f"{inv['invoice_id']} dated before {inv['po_id']}")
    rows = sorted(t.get("intake_manifest", []), key=lambda m: int(m["intake_seq"]))
    bad += [f"{b['doc_id']} not after {a['doc_id']}" for a, b in zip(rows, rows[1:])
            if datetime.fromisoformat(b["received_at"]) <= datetime.fromisoformat(a["received_at"])]
    completed = [("vendor_status_history", "recorded_at"), ("goods_receipt", "posted_at"), ("erp_event", "event_at"),
                 ("intake_manifest", "received_at"), ("captured_invoice", "captured_at"), ("ap_event", "event_at"),
                 ("invoice_decision", "decided_at"), ("ap_exception", "created_at"), ("approval", "decided_at"),
                 ("payment", "created_at"), ("payment", "paid_at")]
    for name, col in completed:                 # completed engine events too (forward plans may lie later)
        bad += [f"{name}.{col}={r[col]} after as-of" for r in t.get(name, [])
                if r[col] and datetime.fromisoformat(r[col]) > as_of_end]
    bad += [f"vendor_status_history effective {r['effective_date']} after as-of" for r in t.get("vendor_status_history", [])
            if r["effective_date"] > as_of_end.date().isoformat()]
    bad += [f"{r['vsh_id']} recorded after its effective date" for r in t.get("vendor_status_history", [])
            if r["recorded_at"][:10] > r["effective_date"]]
    c.add("date order and the as-of limit (no completed event after as-of)", bad, labelled)


def _arithmetic(t, c, code_of):
    bad, labelled = [], []
    lines_by_po = defaultdict(list)
    for l in t.get("purchase_order_line", []):
        lines_by_po[l["po_id"]].append(l)
        net = line_net(D(l["ordered_qty"]), D(l["unit_price"]))
        tax = tax_amount(net, D(l["tax_rate_pct"]))
        if (D(l["line_net_amount"]), D(l["line_tax_amount"]), D(l["line_gross_amount"])) != (net, tax, net + tax):
            bad.append(f"{l['po_line_id']} amounts")
    for p in t.get("purchase_order", []):
        ls = lines_by_po[p["po_id"]]
        net, tax = sum(D(l["line_net_amount"]) for l in ls), sum(D(l["line_tax_amount"]) for l in ls)
        if (D(p["total_net_amount"]), D(p["total_tax_amount"]), int(p["line_count"])) != (net, tax, len(ls)):
            bad.append(f"{p['po_id']} totals")
    pol = {l["po_line_id"]: l for l in t.get("purchase_order_line", [])}
    over_ok = {inv["po_id"] for inv in t.get("invoice", [])
               if code_of.get(inv["invoice_id"], set()) & {"QM-EXCEEDS-PO-OVERRECEIPT", "QM-BOUNDARY-OUT"}}
    cum = defaultdict(D)
    for g in sorted(t.get("goods_receipt_line", []), key=lambda g: g["grn_line_id"]):
        line = pol[g["po_line_id"]]
        cum[g["po_line_id"]] += D(g["received_qty"])
        ordered = D(line["ordered_qty"])
        kind = "PARTIAL" if cum[g["po_line_id"]] < ordered else "FULL" if cum[g["po_line_id"]] == ordered else "OVER"
        if D(g["cumulative_received_qty"]) != cum[g["po_line_id"]] or g["receipt_type"] != kind:
            bad.append(f"{g['grn_line_id']} cumulative/receipt type")
        if cum[g["po_line_id"]] * 100 > ordered * 105:
            (labelled if line["po_id"] in over_ok else bad).append(f"{g['grn_line_id']} received beyond 5% tolerance")
    for l in t.get("purchase_order_line", []):
        if D(l["snapshot_received_qty"]) != cum[l["po_line_id"]]:
            bad.append(f"{l['po_line_id']} snapshot_received_qty")
    inv_lines = defaultdict(list)
    for l in t.get("invoice_line", []):
        inv_lines[l["invoice_id"]].append(l)
        code = code_of.get(l["invoice_id"], set())
        if D(l["expected_line_net_amount"]) != line_net(D(l["quantity"]), D(l["unit_price"])):
            bad.append(f"{l['invoice_line_id']} expected_line_net_amount")
        if D(l["expected_tax_amount"]) != tax_amount(D(l["line_net_amount"]), D(l["tax_rate_pct"])):
            bad.append(f"{l['invoice_line_id']} expected_tax_amount")
        if D(l["line_net_amount"]) != D(l["expected_line_net_amount"]):
            (labelled if "ARITH-LINE-EXTENSION" in code else bad).append(f"{l['invoice_line_id']} line amount")
        if abs(D(l["tax_amount"]) - D(l["expected_tax_amount"])) > D("0.01"):
            (labelled if code & {"TV-TAX-AMOUNT", "TV-NPO-TAX-AMOUNT"} else bad).append(f"{l['invoice_line_id']} tax")
    for inv in t.get("invoice", []):
        ls = inv_lines[inv["invoice_id"]]
        net, tax = sum(D(l["line_net_amount"]) for l in ls), sum(D(l["tax_amount"]) for l in ls)
        if (D(inv["lines_net_amount"]), D(inv["lines_tax_amount"]), int(inv["line_count"])) != (net, tax, len(ls)):
            bad.append(f"{inv['invoice_id']} derived line sums")
        printed = (D(inv["header_net_amount"]), D(inv["header_tax_amount"]), D(inv["header_gross_amount"]))
        if printed != (net, tax, net + tax):
            (labelled if "ARITH-HEADER-TOTAL" in code_of.get(inv["invoice_id"], ()) else bad).append(
                f"{inv['invoice_id']} header vs lines")
    c.add("arithmetic (lines -> headers, PO and receipt balances)", bad, labelled)


def _lifecycles(t, c):
    bad = []
    by_vendor = defaultdict(list)
    for h in sorted(t.get("vendor_status_history", []), key=lambda h: (h["vendor_id"], int(h["seq"]))):
        by_vendor[h["vendor_id"]].append(h)
    for v in t.get("vendor", []):
        hist = by_vendor[v["vendor_id"]]
        bad += lifecycle.sequence_errors("VENDOR", [h["to_status"] for h in hist])
        if any(a["effective_date"] > b["effective_date"] for a, b in zip(hist, hist[1:])):
            bad.append(f"{v['vendor_id']} effective dates out of order")
        if not hist or hist[0]["effective_date"] != v["onboarded_date"] or hist[-1]["to_status"] != v["snapshot_status"]:
            bad.append(f"{v['vendor_id']} onboarding or snapshot_status inconsistent with history")
    events = defaultdict(list)
    for e in sorted(t.get("erp_event", []), key=lambda e: (e["entity_id"], int(e["seq"]))):
        events[(e["entity_type"], e["entity_id"])].append(e)
    for (etype, eid), evs in events.items():
        bad += [f"{eid}: {m}" for m in lifecycle.sequence_errors(etype, [e["to_status"] for e in evs])]
        bad += [f"{eid} events out of order" for a, b in zip(evs, evs[1:]) if a["event_at"] > b["event_at"]]
    for name, etype, key in (("purchase_order", "PURCHASE_ORDER", "po_id"), ("goods_receipt", "GOODS_RECEIPT", "grn_id")):
        for r in t.get(name, []):
            evs = events.get((etype, r[key]))
            if not evs or evs[-1]["to_status"] != r["snapshot_status"]:
                bad.append(f"{r[key]} snapshot_status != last event")
    ap = defaultdict(list)
    for e in sorted(t.get("ap_event", []), key=lambda e: e["event_id"]):
        ap[(e["entity_type"], e["entity_id"])].append(e)
    for (etype, eid), evs in ap.items():
        bad += [f"{eid}: {m}" for m in lifecycle.sequence_errors(etype, [e["to_status"] for e in evs])]
        bad += [f"{eid} AP events out of order" for a, b in zip(evs, evs[1:])
                if a["event_at"] > b["event_at"] or int(b["seq"]) != int(a["seq"]) + 1]
    for name, etype, key in (("invoice_decision", "INVOICE", "invoice_id"), ("ap_exception", "EXCEPTION", "exception_id"),
                             ("approval", "APPROVAL", "approval_id"), ("payment", "PAYMENT", "payment_id")):
        for r in t.get(name, []):
            evs = ap.get((etype, r[key]))
            if not evs or evs[-1]["to_status"] != r["status_as_of"]:
                bad.append(f"{r[key]} status_as_of != last AP event")
    c.add("lifecycle events (state machines, order, current = last event)", bad)


def _mix(t, c, alloc):
    bad = []
    gt = t["ground_truth"]
    cats, subs = Counter(r["scenario_category"] for r in gt), Counter(r["scenario_code"] for r in gt)
    if alloc is not None:
        bad += [f"{k}: {cats.get(k, 0)} != {v}" for k, v in alloc.categories.items() if cats.get(k, 0) != v]
        bad += [f"{k}: {subs.get(k, 0)} != {v}" for k, v in alloc.subscenarios.items() if subs.get(k, 0) != v]
        floor = 10 if alloc.scale == "full" else 1
        ec = Counter(e for r in gt for e in r["edge_case_ids"].split("|") if e)
        bad += [f"{e}: {ec.get(e, 0)} < {floor}" for e in ("EC-0%d" % i for i in range(1, 9)) if ec.get(e, 0) < floor]
    c.add("mix and edge-case counts vs target", bad)


def _intent(t, c, policy):
    blocking = {k for k, v in policy.raw["routing"]["types"].items() if v["blocking"]}
    bad = [f"{r['invoice_id']} {r['scenario_code']}" for r in t["ground_truth"]
           if {x for x in r["expected_issue_types"].split("|") if x in blocking}
           != {x for x in r["intended_issue_types"].split("|") if x}]
    bad += [f"{r['invoice_id']} CLEAN with issues" for r in t["ground_truth"]
            if r["scenario_category"] == "CLEAN" and r["intended_issue_types"]]
    c.add("oracle labels == injection intent (blocking issues)", bad)


def _duplicates(t, c, code_of):
    bad, labelled = [], []
    man = {m["doc_id"]: int(m["intake_seq"]) for m in t["intake_manifest"]}
    gt = {r["invoice_id"]: r for r in t["ground_truth"]}
    first: dict[tuple, str] = {}
    for inv in sorted(t["invoice"], key=lambda i: man[i["doc_id"]]):
        norm = normalize_invoice_number(inv["vendor_invoice_number"])
        keys = [("number", inv["vendor_id"], norm),
                ("content", inv["vendor_id"], inv["invoice_date"], inv["header_gross_amount"], inv["po_id"])]
        hits = [first[k] for k in keys if k in first]
        if hits:
            is_dup = CODE[code_of[inv["invoice_id"]]].category == "DUPLICATE"
            target = gt[inv["invoice_id"]]["expected_duplicate_of"]
            (labelled if is_dup and target in hits else bad).append(f"{inv['invoice_id']} collides with {hits[0]}")
        for k in keys:
            first.setdefault(k, inv["invoice_id"])
    c.add("no accidental duplicate pairs (number or content collisions)", bad, labelled)
