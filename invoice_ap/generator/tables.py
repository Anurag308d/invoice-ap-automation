"""Materialize a plan into spec-shaped rows for one phase.

phase "baseline": every invoice is the valid, clean version of its slot (clean variations such as
price-at-tolerance are part of the baseline). phase "final": the labelled anomaly injections are
applied on top, plus the duplicate documents and the injected vendor status changes.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal

from ..common import ids
from ..common.money import line_net, money, tax_amount
from . import params as P
from .planner import Bill, Dup, Plan, part_of, quantum
from .rng import between, stream, weighted_choice
from .world import ROLE_TEXT, TAX_CODES, TERMS_DAYS, ts

TWO_PCT = Decimal("1.02")
SCHEMES = (("INV-YEAR", 4), ("FY", 3), ("PLAIN", 2), ("SI", 1))
FILE_EXT = {"PORTAL": "json", "EDI": "edi", "EMAIL": "eml", "SCAN": "txt"}
ANOMALY = {"PV-OVER", "PV-UNDER", "PV-SPLIT-LATER", "PV-BOUNDARY-OUT", "QM-PARTIAL-BILLED-FULL",
           "QM-OVERBILL-RECEIVED", "QM-CUMULATIVE", "QM-EXCEEDS-PO-OVERRECEIPT", "QM-EXCEEDS-PO-AND-RECEIVED",
           "QM-BOUNDARY-OUT", "TV-TAX-CODE", "TV-TAX-AMOUNT", "TV-NPO-TAX-AMOUNT", "TV-VENDOR-PO",
           "ARITH-HEADER-TOTAL", "ARITH-LINE-EXTENSION", "DATE-INVOICE-BEFORE-PO", "CAP-DEGRADED-SCAN"}


def normalize_invoice_number(number: str) -> str:
    """DUP normalisation: uppercase, split on non-alphanumerics, strip leading zeros of numeric tokens."""
    tokens = [t for t in re.split(r"[^A-Z0-9]+", number.upper()) if t]
    return "".join(str(int(t)) if t.isdigit() else t for t in tokens)


@dataclass
class Doc:
    """One received document and the generator-side facts the oracle needs."""
    kind: str                     # "bill" | "dup"
    key: str
    code: str
    invoice: dict
    lines: list[dict]
    manifest: dict
    overlay: str = "NONE"
    original_key: str | None = None
    description: str = ""


@dataclass
class Dataset:
    phase: str
    tables: dict[str, list[dict]] = field(default_factory=dict)
    docs: list[Doc] = field(default_factory=list)


# ------------------------------------------------------------------ invoice content
def _po_lines_for(bill: Bill, final: bool) -> list[dict]:
    """Baseline billed quantities per PO line, before any anomaly mutation."""
    out = []
    for line in bill.po.lines:
        if not bill.billed:
            qty = line.qty
        else:
            qty = Decimal(0)
            for k in bill.billed:
                d = bill.po.deliveries[k]
                qty += d.final_qty.get(line.number, d.qty[line.number]) if final else d.qty[line.number]
        if bill.share:
            first = part_of(line.qty, bill.share[1], line.uom)
            qty = first if bill.share[0] == "first" else line.qty - first
        out.append({"po_line": line, "sku": line.sku, "description": line.sku.description, "uom": line.uom,
                    "qty": qty, "price": line.price, "tax_code": line.tax_code})
    return out


def _content(bill: Bill, final: bool) -> tuple[object, date, list[dict], dict, str]:
    """(issuing vendor, invoice date, printed lines, printed header, injection description)."""
    c, desc = bill.code, ""
    vendor, inv_date = bill.vendor, bill.invoice_date
    if bill.po:
        lines = _po_lines_for(bill, final)
    else:
        lines = [{"po_line": None, "sku": None, "description": s.description, "uom": s.uom, "qty": s.qty,
                  "price": s.price, "tax_code": s.tax_code} for s in bill.services]
    l1 = lines[0]
    po_price = l1["price"]
    if c == "C-PRICE-AT-TOL":
        l1["price"] = _exact(po_price * TWO_PCT)
    elif c == "C-PRICE-INSIDE":
        l1["price"] = _exact(po_price * TWO_PCT - Decimal("0.01"))
    elif c == "C-PRICE-SMALL-VAR":
        l1["price"] = money(po_price * (1 + bill.params["factor"]))
    if final and c in ANOMALY:
        if c in ("PV-OVER", "PV-UNDER", "PV-SPLIT-LATER"):
            l1["price"] = money(po_price * (1 + bill.params["factor"]))
        elif c == "PV-BOUNDARY-OUT":
            l1["price"] = _exact(po_price * TWO_PCT + Decimal("0.01"))
        elif c == "QM-PARTIAL-BILLED-FULL":
            for ln in lines:
                ln["qty"] = ln["po_line"].qty
        elif c in ("QM-OVERBILL-RECEIVED", "QM-CUMULATIVE"):
            l1["qty"] += bill.params["extra"]
        elif c == "QM-EXCEEDS-PO-AND-RECEIVED":
            l1["qty"] = l1["po_line"].qty + bill.params["extra"]
        elif c == "TV-TAX-CODE":
            l1["tax_code"] = bill.params["tax_code"]
        elif c == "TV-VENDOR-PO":
            vendor = bill.final_vendor
        elif c == "DATE-INVOICE-BEFORE-PO":
            inv_date = bill.final_invoice_date
    for ln in lines:
        rate = TAX_CODES[ln["tax_code"]][0]
        ln["net"] = line_net(ln["qty"], ln["price"])
        ln["expected_net"] = ln["net"]
        if final and c == "ARITH-LINE-EXTENSION" and ln is l1:
            ln["net"] = money(ln["net"] * (1 + bill.params["factor"]))
        ln["tax"] = tax_amount(ln["net"], rate)
        ln["expected_tax"] = ln["tax"]
    if c == "C-TAX-ROUNDING":
        l1["tax"] += bill.params["cents"] if l1["tax"] + bill.params["cents"] >= 0 else Decimal("0.01")
    if final and c in ("TV-TAX-AMOUNT", "TV-NPO-TAX-AMOUNT"):
        delta = max(Decimal("0.02"), money(l1["tax"] * bill.params["pct"] / 100))
        l1["tax"] = l1["tax"] + delta if bill.params["sign"] > 0 or l1["tax"] < delta else l1["tax"] - delta
    net = sum((ln["net"] for ln in lines), Decimal(0))
    tax = sum((ln["tax"] for ln in lines), Decimal(0))
    header = {"net": net, "tax": tax, "gross": net + tax}
    if final and c == "ARITH-HEADER-TOTAL":
        header["gross"] = _wrong_total(header["gross"], lines, bill.params["mode"])
    if final and c in ANOMALY:
        desc = _describe(bill, lines, header, po_price, vendor, inv_date)
    return vendor, inv_date, lines, header, desc


def _exact(value: Decimal) -> Decimal:
    """Boundary prices are whole cents by construction (PO price is a multiple of 0.50)."""
    cents = money(value)
    assert cents == value, f"boundary price {value} is not a whole cent"
    return cents


def _wrong_total(gross: Decimal, lines: list[dict], mode: str) -> Decimal:
    if mode == "omit_line":
        return gross - lines[-1]["net"] - lines[-1]["tax"]
    digits = list(f"{gross:.2f}".replace(".", ""))
    for i in range(len(digits) - 2, -1, -1):           # transpose the right-most unequal adjacent pair
        if digits[i] != digits[i + 1]:
            digits[i], digits[i + 1] = digits[i + 1], digits[i]
            break
    else:
        return gross + Decimal("9.00")
    value = Decimal("".join(digits)) / 100
    return value if abs(value - gross) > Decimal("0.01") else gross + Decimal("9.00")


def _describe(bill: Bill, lines, header, po_price, vendor, inv_date) -> str:
    c, l1 = bill.code, lines[0]
    if c.startswith("PV-"):
        return f"line 1 unit price {l1['price']} vs PO {po_price}"
    if c.startswith("QM-"):
        return f"line 1 billed {l1['qty']} {l1['uom']}, ordered {l1['po_line'].qty}"
    if c == "TV-TAX-CODE":
        return f"line 1 tax code {l1['tax_code']} vs PO {l1['po_line'].tax_code}"
    if c in ("TV-TAX-AMOUNT", "TV-NPO-TAX-AMOUNT"):
        return f"line 1 tax {l1['tax']} vs expected {l1['expected_tax']}"
    if c == "TV-VENDOR-PO":
        return f"sent by {vendor.vendor_id}, quotes {bill.po.po_id} of {bill.vendor.vendor_id}"
    if c == "ARITH-HEADER-TOTAL":
        return f"printed total {header['gross']} vs lines {header['net'] + header['tax']} ({bill.params['mode']})"
    if c == "ARITH-LINE-EXTENSION":
        return f"line 1 amount {l1['net']} vs {l1['qty']} x {l1['price']} = {l1['expected_net']}"
    if c == "DATE-INVOICE-BEFORE-PO":
        return f"invoice date {inv_date} before PO date {bill.po.po_date}"
    if c == "CAP-DEGRADED-SCAN":
        return f"scan with unreadable {bill.params['unreadable_field']}"
    return ""


# ------------------------------------------------------------------ numbering
class Numbering:
    def __init__(self, plan: Plan):
        rng = stream(plan.world.seed, "numbering")
        self.scheme, self.start = {}, {}
        for v in plan.world.vendors:
            self.scheme[v.vendor_id] = weighted_choice(rng, [s for s, _ in SCHEMES], [w for _, w in SCHEMES])
            self.start[v.vendor_id] = (between(rng, 1, 400), between(rng, 1, 3))
        self.prefix = {v.vendor_id: re.sub(r"[^A-Z]", "", v.name.upper())[:3] for v in plan.world.vendors}

    def assign(self, items: list[tuple[str, date, str]]) -> dict[str, str]:
        """items: (vendor_id, invoice_date, key) of original documents -> key: printed number."""
        out, counters = {}, {}
        for vendor_id, inv_date, key in sorted(items):
            scheme = self.scheme[vendor_id]
            fy = "25-26" if inv_date < date(2026, 4, 1) else "26-27"
            ckey = (vendor_id, fy if scheme == "FY" else "")
            first, step = self.start[vendor_id]
            n = counters[ckey] = counters.get(ckey, first - step) + step
            out[key] = {"INV-YEAR": f"INV-2026-{n:04d}", "FY": f"{self.prefix[vendor_id]}/{fy}/{n:03d}",
                        "PLAIN": f"{n:06d}", "SI": f"SI{n:05d}"}[scheme]
        return out


def reformat(number: str) -> str:
    """A different printed form of the same number (case, separators, leading zeros)."""
    if number.isdigit():
        return str(int(number))
    if re.fullmatch(r"SI\d+", number):
        return number.lower()
    parts = re.split(r"([^A-Za-z0-9]+)", number)
    parts = [str(int(p)) if p.isdigit() and len(p) > 2 else p for p in parts]
    out = "".join(parts).lower()
    return out.replace("/", " ", 1) if "/" in out else out.replace("-", "/", 1)


# ------------------------------------------------------------------ materialize
def _status_at(events, day: date) -> str:
    current = None
    for e in events:
        if e.effective <= day:
            current = e.to_status
    return current


def materialize(plan: Plan, phase: str, policy_version: str) -> Dataset:
    final = phase == "final"
    w, ds = plan.world, Dataset(phase)
    t = ds.tables
    system, vm_owner = w.user("SYSTEM_USER"), w.user("VENDOR_MASTER_OWNER")
    t["actor_role"] = [{"role_code": r, "role_name": n, "is_human": r != "SYSTEM", "responsibilities": d}
                       for r, (n, d) in ROLE_TEXT.items()]
    t["app_user"] = [{"user_id": u.user_id, "display_name": u.display_name, "role_code": u.role_code,
                      "responsibility": u.responsibility, "cost_center": u.cost_center,
                      "approval_level": u.approval_level, "email": u.email, "active_from": P.USER_ACTIVE_FROM}
                     for u in w.users]
    t["payment_terms"] = [{"terms_code": k, "net_days": d, "description": f"Net {d} days"}
                          for k, d in TERMS_DAYS.items()]
    t["tax_code"] = [{"tax_code": k, "rate_pct": r, "tax_category": c, "description": f"{k} ({r}%)",
                      "valid_from": vf, "valid_to": vt} for k, (r, c, vf, vt) in TAX_CODES.items()]
    t["sku"] = [{"sku_id": s.sku_id, "description": s.description, "category": s.category, "uom": s.uom,
                 "default_tax_code": s.tax_code, "reference_price": s.reference_price,
                 "lead_time_min_days": s.lead[0], "lead_time_max_days": s.lead[1]} for s in w.skus]

    events = {v.vendor_id: list(v.events) + (plan.final_events.get(v.vendor_id, []) if final else [])
              for v in w.vendors}
    t["vendor"] = [{"vendor_id": v.vendor_id, "vendor_name": v.name, "tax_registration_id": v.trn,
                    "segment": v.segment, "category": v.category, "tier": v.tier, "payment_terms_code": v.terms,
                    "preferred_channel": v.channel, "remit_email": v.remit_email, "onboarded_date": v.onboarded,
                    "snapshot_status": _status_at(events[v.vendor_id], w.as_of), "created_by": vm_owner.user_id}
                   for v in w.vendors]
    t["vendor_status_history"], n = [], 0
    for v in w.vendors:
        for seq, e in enumerate(events[v.vendor_id], start=1):
            n += 1
            t["vendor_status_history"].append({
                "vsh_id": ids.vsh_id(n), "vendor_id": v.vendor_id, "seq": seq, "from_status": e.from_status,
                "to_status": e.to_status, "effective_date": e.effective, "recorded_at": e.recorded_at,
                "actor_role": "SYSTEM_ADMINISTRATOR", "actor_id": vm_owner.user_id, "reason_code": e.reason})
    _purchasing(plan, final, t, system)
    _invoices(plan, final, ds, policy_version)
    return ds


def _purchasing(plan: Plan, final: bool, t: dict, system) -> None:
    cal = plan.world.cal
    t["purchase_order"], t["purchase_order_line"] = [], []
    t["goods_receipt"], t["goods_receipt_line"] = [], []
    erp: list[tuple] = []
    for p in sorted(plan.pos, key=lambda p: p.po_id):
        received = {l.number: Decimal(0) for l in p.lines}
        status = None
        erp.append((ts(p.po_date, p.minute), 0, p.po_id, "PURCHASE_ORDER", None, "ISSUED", "BUSINESS_REQUESTER",
                    p.requester.user_id, "PO_ISSUED", None))
        status = "ISSUED"
        for k, d in enumerate(p.deliveries):
            posted = ts(d.day, d.minute)
            qtys = {n: d.final_qty.get(n, q) if final else q for n, q in d.qty.items()}
            gl = []
            for line in p.lines:
                q = qtys[line.number]
                if q <= 0:
                    continue
                received[line.number] += q
                cum = received[line.number]
                gl.append({"grn_line_id": ids.grn_line_id(d.grn_id, len(gl) + 1), "grn_id": d.grn_id,
                           "po_line_id": line.line_id, "line_number": len(gl) + 1, "received_qty": q,
                           "uom": line.uom, "cumulative_received_qty": cum,
                           "receipt_type": "PARTIAL" if cum < line.qty else "FULL" if cum == line.qty else "OVER"})
            t["goods_receipt_line"] += gl
            t["goods_receipt"].append({"grn_id": d.grn_id, "po_id": p.po_id, "vendor_id": p.vendor.vendor_id,
                                       "received_date": d.day, "posted_at": posted, "received_by": p.requester.user_id,
                                       "delivery_note_number": f"DN-{p.vendor.vendor_id[4:]}-{d.grn_id[-6:]}",
                                       "line_count": len(gl), "snapshot_status": "POSTED"})
            erp.append((posted, 1, d.grn_id, "GOODS_RECEIPT", None, "POSTED", "BUSINESS_REQUESTER",
                        p.requester.user_id, "GRN_POSTED", None))
            new = "RECEIVED" if all(received[l.number] >= l.qty for l in p.lines) else "PARTIALLY_RECEIVED"
            if new != status:
                erp.append((posted + timedelta(minutes=1), 2, p.po_id, "PURCHASE_ORDER", status, new, "SYSTEM",
                            system.user_id, "GOODS_RECEIVED", d.grn_id))
                status = new
        net = tax = Decimal(0)
        for line in p.lines:
            rate = TAX_CODES[line.tax_code][0]
            ln, lt = line_net(line.qty, line.price), tax_amount(line_net(line.qty, line.price), rate)
            net, tax = net + ln, tax + lt
            t["purchase_order_line"].append({
                "po_line_id": line.line_id, "po_id": p.po_id, "line_number": line.number,
                "sku_id": line.sku.sku_id, "description": line.sku.description, "uom": line.uom,
                "ordered_qty": line.qty, "unit_price": line.price, "tax_code": line.tax_code, "tax_rate_pct": rate,
                "line_net_amount": ln, "line_tax_amount": lt, "line_gross_amount": ln + lt,
                "promised_delivery_date": cal.next_business_day(p.po_date + timedelta(days=p.lead), True),
                "snapshot_received_qty": received[line.number].quantize(quantum(line.uom)),
                "snapshot_open_qty": max(line.qty - received[line.number], Decimal(0)).quantize(quantum(line.uom))})
        t["purchase_order"].append({
            "po_id": p.po_id, "vendor_id": p.vendor.vendor_id, "requester_id": p.requester.user_id,
            "cost_center": p.requester.cost_center, "po_date": p.po_date, "currency": "INR",
            "payment_terms_code": p.vendor.terms, "line_count": len(p.lines), "total_net_amount": net,
            "total_tax_amount": tax, "total_gross_amount": net + tax, "snapshot_status": status})
    t["goods_receipt"].sort(key=lambda r: r["grn_id"])
    t["goods_receipt_line"].sort(key=lambda r: r["grn_line_id"])
    erp.sort(key=lambda e: (e[0], e[1], e[2]))
    seqs: dict[str, int] = {}
    t["erp_event"] = []
    for n, (at, _, entity_id, etype, frm, to, role, actor, reason, ref) in enumerate(erp, start=1):
        seqs[entity_id] = seqs.get(entity_id, 0) + 1
        t["erp_event"].append({"event_id": ids.erp_event_id(n), "entity_type": etype, "entity_id": entity_id,
                               "seq": seqs[entity_id], "from_status": frm, "to_status": to, "event_at": at,
                               "actor_role": role, "actor_id": actor, "reason_code": reason, "ref_id": ref})


def _sender(doc_channel: str, vendor, bill: Bill, received: date) -> tuple[str, str | None]:
    if doc_channel in ("PORTAL", "EDI"):
        return f"{doc_channel.lower()}/{vendor.vendor_id.lower()}", vendor.vendor_id
    if doc_channel == "EMAIL":
        if bill.forward_mailbox:
            forwarder = bill.attention or (bill.po.requester if bill.po else None)
            return (forwarder.email if forwarder else "ap.inbox@example.com"), None
        return vendor.remit_email, None
    return f"MAILROOM-BATCH-{received:%Y%m%d}", None


def _invoices(plan: Plan, final: bool, ds: Dataset, policy_version: str) -> None:
    content = {b.key: _content(b, final) for b in plan.bills}
    docs: list[tuple] = [(b.received_date, b.minute, b.key, "bill", b) for b in plan.bills]
    if final:
        docs += [(d.received_date, d.minute, d.key, "dup", d) for d in plan.dups]
    docs.sort(key=lambda x: x[:3])
    numbers = Numbering(plan).assign([(content[b.key][0].vendor_id, content[b.key][1], b.key) for b in plan.bills])
    manifest, invoices, lines = [], [], []
    last = None
    for seq, (day, minute, key, kind, obj) in enumerate(docs, start=1):
        at = ts(day, minute)
        if last and at <= last:
            at = last + timedelta(seconds=1)
        last = at
        bill = obj if kind == "bill" else obj.original
        vendor, inv_date, inv_lines, header, desc = content[bill.key]
        number, code = numbers[bill.key], obj.code
        channel = obj.channel
        if kind == "dup":
            inv_lines = [dict(ln) for ln in inv_lines]
            header, desc = dict(header), f"resubmission of {bill.key}"
            if code == "DUP-EXACT-NORMALIZED":
                number = reformat(number)
            elif code == "DUP-CONTENT":
                number += obj.params["suffix"]
            elif code == "DUP-NUMBER-REUSE":
                inv_date = obj.params["rebill_date"]
                l1 = inv_lines[0]
                l1["price"] = money(l1["price"] * (1 + obj.params["price_factor"]))
                l1["net"] = l1["expected_net"] = line_net(l1["qty"], l1["price"])
                l1["tax"] = l1["expected_tax"] = tax_amount(l1["net"], TAX_CODES[l1["tax_code"]][0])
                net = sum((ln["net"] for ln in inv_lines), Decimal(0))
                tax = sum((ln["tax"] for ln in inv_lines), Decimal(0))
                header = {"net": net, "tax": tax, "gross": net + tax}
        doc_id, invoice_id = ids.doc_id(seq), ids.invoice_id(vendor.vendor_id, seq)
        sender, sender_vendor = _sender(channel, vendor, bill, day)
        manifest_row = {"doc_id": doc_id, "intake_seq": seq, "channel": channel,
                        "file_format": {"PORTAL": "PORTAL_JSON", "EDI": "EDI_FLAT", "EMAIL": "EMAIL_TEXT",
                                        "SCAN": "OCR_TEXT"}[channel],
                        "received_at": at, "sender_address": sender, "sender_vendor_id": sender_vendor,
                        "file_path": f"documents/{channel.lower()}/{doc_id}.{FILE_EXT[channel]}",
                        "file_sha256": None, "file_bytes": None}      # filled when the documents are rendered
        line_rows = []
        for n, ln in enumerate(inv_lines, start=1):
            rate = TAX_CODES[ln["tax_code"]][0]
            line_rows.append({
                "invoice_line_id": ids.invoice_line_id(invoice_id, n), "invoice_id": invoice_id, "line_number": n,
                "po_line_id": ln["po_line"].line_id if ln["po_line"] else None,
                "sku_id": ln["sku"].sku_id if ln["sku"] else None, "description": ln["description"],
                "uom": ln["uom"], "quantity": ln["qty"], "unit_price": ln["price"], "line_net_amount": ln["net"],
                "tax_code": ln["tax_code"], "tax_rate_pct": rate, "tax_amount": ln["tax"],
                "expected_line_net_amount": line_net(ln["qty"], ln["price"]),
                "expected_tax_amount": tax_amount(ln["net"], rate), "line_gross_amount": ln["net"] + ln["tax"]})
        lines_net = sum((r["line_net_amount"] for r in line_rows), Decimal(0))
        lines_tax = sum((r["tax_amount"] for r in line_rows), Decimal(0))
        invoice_row = {
            "invoice_id": invoice_id, "doc_id": doc_id, "vendor_id": vendor.vendor_id,
            "vendor_invoice_number": number, "invoice_date": inv_date,
            "po_id": bill.po.po_id if bill.po else None,
            "attention_user_id": bill.attention.user_id if bill.attention else None, "currency": "INR",
            "header_net_amount": header["net"], "header_tax_amount": header["tax"],
            "header_gross_amount": header["gross"], "lines_net_amount": lines_net, "lines_tax_amount": lines_tax,
            "lines_gross_amount": lines_net + lines_tax, "line_count": len(line_rows),
            "is_po_backed": bill.po is not None}
        overlay = "DEGRADED_SCAN" if final and kind == "bill" and code == "CAP-DEGRADED-SCAN" else "NONE"
        ds.docs.append(Doc(kind, key, code, invoice_row, line_rows, manifest_row, overlay,
                           bill.key if kind == "dup" else None, desc))
        manifest.append(manifest_row)
        invoices.append(invoice_row)
        lines += line_rows
    ds.tables["intake_manifest"], ds.tables["invoice"], ds.tables["invoice_line"] = manifest, invoices, lines
