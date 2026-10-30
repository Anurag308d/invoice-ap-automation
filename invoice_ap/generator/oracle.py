"""Rule-based oracle: derives the ground truth from the TRUE data under config/ap_policy.toml.

It walks the documents in intake order and applies the rule catalogue of docs/business_rules.md
(CAP-01, VEN-01..04, DUP-01..03, PO-01..03, DATE-01..02, ARI-01..02, TAX-01..03, MAT-01..04, MS-01,
PRI-01, RTE-01, APR-01, APR-SIM-01, PAY-01..06). It reads only the generated tables plus two
generator-side facts: the capture overlay (rendering metadata) and the planned scenario. Generation
fails loudly unless the oracle's blocking labels equal the injection intent for every invoice and
every duplicate points to its planned original (R11, A-22).
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from ..common.calendar import BusinessCalendar
from ..common.enums import EDGE_CASES, EXCEPTION_TYPES
from ..common.money import line_net, money, tax_amount
from ..common.policy import Policy
from .catalogue import SUBSCENARIOS
from .tables import Dataset, normalize_invoice_number

HUNDRED = Decimal(100)
LINE_ISSUES = {"LINE_AMOUNT_MISMATCH", "TAX_CODE_INVALID", "TAX_CODE_MISMATCH", "TAX_AMOUNT_MISMATCH",
               "PO_LINE_UNMATCHED", "MISSING_RECEIPT", "QTY_EXCEEDS_PO", "QTY_EXCEEDS_RECEIVED", "PRICE_VARIANCE"}
CODE = {s.code: s for s in SUBSCENARIOS}


class OracleMismatch(AssertionError):
    """An injected scenario did not produce its intended label under the documented policy."""


def _ordered(issues) -> list[str]:
    seen = set(issues)
    return [t for t in EXCEPTION_TYPES if t in seen]


class Oracle:
    def __init__(self, ds: Dataset, policy: Policy):
        raw, t = policy.raw, ds.tables
        self.ds, self.policy, self.raw = ds, policy, raw
        self.cal, self.as_of = BusinessCalendar.from_policy(raw), policy.as_of_date
        self.vendors = {v["vendor_id"]: v for v in t["vendor"]}
        self.by_trn = {v["tax_registration_id"]: v["vendor_id"] for v in t["vendor"]}
        self.history = defaultdict(list)
        for h in t["vendor_status_history"]:
            self.history[h["vendor_id"]].append(h)
        self.pos = {p["po_id"]: p for p in t["purchase_order"]}
        self.po_lines = {l["po_line_id"]: l for l in t["purchase_order_line"]}
        posted = {g["grn_id"]: g["posted_at"] for g in t["goods_receipt"]}
        self.receipts = defaultdict(list)
        for g in t["goods_receipt_line"]:
            self.receipts[g["po_line_id"]].append((posted[g["grn_id"]], g["received_qty"]))
        self.tax = {c["tax_code"]: c for c in t["tax_code"]}
        self.terms = {p["terms_code"]: p["net_days"] for p in t["payment_terms"]}
        m = raw["matching"]
        self.price_tol, self.over_tol = Decimal(m["price_tolerance_pct"]), Decimal(m["over_receipt_tolerance_pct"])
        self.tax_abs = Decimal(raw["tax"]["amount_abs"])
        self.line_abs = Decimal(raw["arithmetic"]["line_amount_abs"])
        self.header_abs = Decimal(raw["arithmetic"]["header_amount_abs"])
        self.routing = raw["routing"]["types"]

    def status_at(self, vendor_id: str, day: date) -> str | None:
        current = None
        for h in self.history[vendor_id]:
            if h["effective_date"] <= day:
                current = h["to_status"]
        return current

    def received_until(self, po_line_id: str, moment) -> Decimal:
        return sum((q for at, q in self.receipts[po_line_id] if at <= moment), Decimal(0))

    # -------------------------------------------------------------- per-document rules
    def run(self):
        exact, number, content = {}, {}, {}
        invoiced: dict[str, Decimal] = defaultdict(Decimal)
        key_to_invoice = {d.key: d.invoice["invoice_id"] for d in self.ds.docs if d.kind == "bill"}
        gt, gtl, mismatches = [], [], []
        for doc in sorted(self.ds.docs, key=lambda d: d.manifest["intake_seq"]):
            inv, lines, man = doc.invoice, doc.lines, doc.manifest
            at, rec_day = man["received_at"], man["received_at"].date()
            issues: list[tuple[str, int | None]] = []
            line_state = {ln["line_number"]: {"price": "NOT_EVALUATED", "qty": "NOT_EVALUATED",
                                              "tax": "NOT_EVALUATED", "received": None, "prior": None,
                                              "variance": None, "within_qty": False} for ln in lines}
            dup_of, gated, matched = None, False, False
            vendor = self.by_trn.get(self.vendors[inv["vendor_id"]]["tax_registration_id"])   # VEN-01
            if doc.overlay == "DEGRADED_SCAN":
                issues.append(("EXT_LOW_CONFIDENCE", None))
                gated = True
            elif vendor is None:
                issues.append(("VENDOR_NOT_FOUND", None))
                gated = True
            else:
                norm = normalize_invoice_number(inv["vendor_invoice_number"])
                keys = ((vendor, norm, inv["invoice_date"], inv["header_gross_amount"]), (vendor, norm),
                        (vendor, inv["invoice_date"], inv["header_gross_amount"], inv["po_id"] or ""))
                for (kind, index), k in zip((("DUPLICATE_EXACT", exact), ("DUPLICATE_NUMBER_REUSE", number),
                                             ("DUPLICATE_SUSPECTED", content)), keys):
                    if k in index:
                        issues.append((kind, None))
                        dup_of, gated = index[k], True
                        break
                for index, k in zip((exact, number, content), keys):
                    index.setdefault(k, inv["invoice_id"])
            if not gated:
                matched = self._checks(doc, vendor, rec_day, at, issues, line_state, invoiced)
            gt_row, mism = self._outcome(doc, issues, line_state, gated, matched, dup_of, key_to_invoice)
            gt.append(gt_row)
            mismatches += mism
            for ln in lines:
                s = line_state[ln["line_number"]]
                line_issues = _ordered(t for t, n in issues if n == ln["line_number"])
                gtl.append({"invoice_line_id": ln["invoice_line_id"], "invoice_id": inv["invoice_id"],
                            "expected_line_issue_types": tuple(line_issues), "expected_price_status": s["price"],
                            "expected_qty_status": s["qty"], "expected_tax_status": s["tax"],
                            "expected_received_qty": s["received"], "expected_prior_invoiced_qty": s["prior"],
                            "expected_price_variance_pct": s["variance"]})
        if mismatches:
            raise OracleMismatch(f"{len(mismatches)} oracle/intent mismatches:\n  " + "\n  ".join(mismatches[:25]))
        return gt, gtl

    def _checks(self, doc, vendor, rec_day, at, issues, state, invoiced) -> bool:
        inv, lines, man = doc.invoice, doc.lines, doc.manifest
        if man["channel"] in self.raw["vendor"]["sender_check_channels"] and man["sender_vendor_id"] \
                and man["sender_vendor_id"] != vendor:
            issues.append(("VENDOR_SENDER_MISMATCH", None))                       # VEN-04
        status = self.status_at(vendor, inv["invoice_date"])
        if status == "CLOSED":
            issues.append(("VENDOR_CLOSED", None))                                # VEN-02
        elif status == "BLOCKED":
            issues.append(("VENDOR_BLOCKED", None))                               # VEN-03
        po, po_ok = None, False
        if inv["po_id"]:
            po = self.pos.get(inv["po_id"])
            if po is None or po["po_date"] > rec_day:
                issues.append(("PO_NOT_FOUND", None))                             # PO-01
            elif po["vendor_id"] != vendor:
                issues.append(("VENDOR_PO_MISMATCH", None))                       # PO-02
            else:
                po_ok = True
        if inv["invoice_date"] > rec_day:
            issues.append(("INVOICE_DATE_IN_FUTURE", None))                       # DATE-01
        if po_ok and inv["invoice_date"] < po["po_date"]:
            issues.append(("INVOICE_BEFORE_PO", None))                            # DATE-02
        nets = sum((ln["line_net_amount"] for ln in lines), Decimal(0))
        taxes = sum((ln["tax_amount"] for ln in lines), Decimal(0))
        if (abs(inv["header_net_amount"] - nets) > self.header_abs or abs(inv["header_tax_amount"] - taxes) > self.header_abs
                or abs(inv["header_gross_amount"] - nets - taxes) > self.header_abs):
            issues.append(("HEADER_TOTAL_MISMATCH", None))                        # ARI-02
        for ln in lines:
            n, s = ln["line_number"], state[ln["line_number"]]
            if abs(ln["line_net_amount"] - line_net(ln["quantity"], ln["unit_price"])) > self.line_abs:
                issues.append(("LINE_AMOUNT_MISMATCH", n))                        # ARI-01
            code = self.tax[ln["tax_code"]]
            valid = code["valid_from"] <= inv["invoice_date"] and (code["valid_to"] is None
                                                                  or inv["invoice_date"] <= code["valid_to"])
            diff = abs(ln["tax_amount"] - tax_amount(ln["line_net_amount"], code["rate_pct"]))
            s["tax"] = "OK" if diff == 0 else "WITHIN_ROUNDING" if diff <= self.tax_abs else "AMOUNT_MISMATCH"
            if not valid:
                issues.append(("TAX_CODE_INVALID", n))                            # TAX-01
                s["tax"] = "CODE_MISMATCH"
            if diff > self.tax_abs:
                issues.append(("TAX_AMOUNT_MISMATCH", n))                         # TAX-03
        if not po_ok:
            return False
        for ln in lines:                                                          # three-way match per line
            n, s = ln["line_number"], state[ln["line_number"]]
            pol = self.po_lines.get(ln["po_line_id"] or "")
            if pol is None or pol["po_id"] != inv["po_id"]:
                issues.append(("PO_LINE_UNMATCHED", n))                           # PO-03
                continue
            if ln["tax_code"] != pol["tax_code"]:
                issues.append(("TAX_CODE_MISMATCH", n))                           # TAX-02
                s["tax"] = "CODE_MISMATCH"
            received, prior = self.received_until(pol["po_line_id"], at), invoiced[pol["po_line_id"]]
            cum = prior + ln["quantity"]
            s["received"], s["prior"] = received, prior
            if received == 0:
                issues.append(("MISSING_RECEIPT", n))                             # MAT-01
                s["qty"] = "NO_RECEIPT"
            else:
                s["qty"] = "OK"
                if cum * HUNDRED > pol["ordered_qty"] * (HUNDRED + self.over_tol):
                    issues.append(("QTY_EXCEEDS_PO", n))                          # MAT-04
                    s["qty"] = "EXCEEDS_PO"
                if cum > received:
                    issues.append(("QTY_EXCEEDS_RECEIVED", n))                    # MAT-03
                    s["qty"] = "EXCEEDS_PO" if s["qty"] == "EXCEEDS_PO" else "EXCEEDS_RECEIVED"
                s["within_qty"] = s["qty"] == "OK" and cum > pol["ordered_qty"]
            diff = ln["unit_price"] - pol["unit_price"]
            s["variance"] = (diff * HUNDRED / pol["unit_price"]).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
            if abs(diff) * HUNDRED <= pol["unit_price"] * self.price_tol:          # MAT-02, inclusive
                s["price"] = "EXACT" if diff == 0 else "WITHIN_TOLERANCE"
            else:
                s["price"] = "OUT_OF_TOLERANCE"
                issues.append(("PRICE_VARIANCE", n))
        for ln in lines:                       # cumulative claims: every invoice that reached matching
            if ln["po_line_id"] in self.po_lines:
                invoiced[ln["po_line_id"]] += ln["quantity"]
        return True

    # -------------------------------------------------------------- decision, approval, payment
    def _match_status(self, inv, state, gated, matched) -> str:
        if not inv["po_id"]:
            return "NOT_APPLICABLE"
        if gated or not matched:
            return "NOT_EVALUATED"
        st = list(state.values())                                                   # MS-01
        if any(s["tax"] in ("CODE_MISMATCH", "AMOUNT_MISMATCH") for s in st):
            return "TAX_MISMATCH"
        if any(s["qty"] == "NO_RECEIPT" for s in st):
            return "MISSING_RECEIPT"
        if any(s["qty"] in ("EXCEEDS_PO", "EXCEEDS_RECEIVED") for s in st):
            return "QTY_MISMATCH"
        if any(s["price"] == "OUT_OF_TOLERANCE" for s in st):
            return "PRICE_VARIANCE"
        if any(s["price"] == "NOT_EVALUATED" for s in st):                      # a line without a PO line
            return "NOT_EVALUATED"
        if all(s["price"] == "EXACT" and s["tax"] == "OK" and not s["within_qty"] for s in st):
            return "MATCHED"
        return "MATCHED_WITHIN_TOLERANCE"

    def _band(self, path: str, gross: Decimal) -> dict:
        for b in self.raw["approval"]["bands"]:
            if b["path"] == path and gross > Decimal(b["lower_exclusive"]) and (
                    "upper_inclusive" not in b or gross <= Decimal(b["upper_inclusive"])):
                return b
        raise ValueError(f"no approval band for {path} {gross}")

    def _approve_and_pay(self, inv, rec_day: date) -> dict:
        path = "PO" if inv["po_id"] else "NON_PO"
        band = self._band(path, inv["header_gross_amount"])                        # APR-01
        out = {"band": band["band"], "levels": tuple(band["levels"]), "rules": [band["rule_id"], "APR-SIM-01"],
               "status": "PENDING_APPROVAL", "issues": [], "payment": None}
        moment = rec_day
        for level in band["levels"]:
            moment = self.cal.add_business_days(moment, self.raw["approval"]["levels"][level]["turnaround_business_days"])
            if moment > self.as_of:
                return out                                                          # a level is still pending
        if self.status_at(inv["vendor_id"], moment) not in self.raw["vendor"]["payable_statuses"]:
            out["status"], out["issues"] = "ON_HOLD", ["VENDOR_NOT_PAYABLE"]          # PAY-03
            return out
        terms = self.pos[inv["po_id"]]["payment_terms_code"] if inv["po_id"] else self.vendors[inv["vendor_id"]]["payment_terms_code"]
        due = inv["invoice_date"] + timedelta(days=self.terms[terms])               # PAY-02
        scheduled = self.cal.previous_business_day(due, include_today=True)
        earliest = self.cal.next_business_day(moment)
        out["rules"] += ["PAY-01", "PAY-02"]
        if scheduled < earliest:
            scheduled = earliest
            out["issues"] = ["PAYMENT_DUE_DATE_PASSED"]                              # PAY-06 (non-blocking)
        paid = scheduled <= self.as_of                                              # PAY-05
        if paid:
            out["rules"].append("PAY-05")
        out["status"] = "PAID" if paid else "PAYMENT_READY"
        out["payment"] = {"status": "PAID" if paid else "SCHEDULED", "due": due, "scheduled": scheduled}
        return out

    def _outcome(self, doc, issues, state, gated, matched, dup_of, key_to_invoice):
        inv = doc.invoice
        rec_day = doc.manifest["received_at"].date()
        types = _ordered(t for t, _ in issues)
        blocking = [t for t in types if self.routing[t]["blocking"]]
        decision = {"band": None, "levels": (), "rules": [], "status": None, "issues": [], "payment": None}
        if not blocking:
            decision = self._approve_and_pay(inv, rec_day)
            types = _ordered(types + decision["issues"])
            blocking = [t for t in types if self.routing[t]["blocking"]]
        if blocking:
            status = "REJECTED" if blocking[0] == "DUPLICATE_EXACT" else "ON_HOLD"
        else:
            status = decision["status"]
        spec = CODE[doc.code]
        mism = []
        if set(blocking) != set(spec.intended_issues):
            mism.append(f"{inv['invoice_id']} {doc.code}: oracle {sorted(blocking)} != intended {sorted(spec.intended_issues)}")
        expected_original = key_to_invoice.get(doc.original_key) if doc.kind == "dup" else None
        if dup_of != expected_original:
            mism.append(f"{inv['invoice_id']} {doc.code}: duplicate_of {dup_of} != planned {expected_original}")
        pay = decision["payment"]
        rules = sorted({self.routing[t]["raised_by"] for t in types} | set(decision["rules"]) | {"PRI-01", "RTE-01"}
                       | ({"MS-01"} if inv["po_id"] and matched else set()))
        row = {
            "invoice_id": inv["invoice_id"], "doc_id": inv["doc_id"], "scenario_category": spec.category,
            "scenario_code": doc.code, "edge_case_ids": tuple(e for e in EDGE_CASES if e in spec.edge_cases),
            "is_anomaly": bool(spec.intended_issues), "is_po_backed": inv["is_po_backed"],
            "capture_overlay": doc.overlay, "intended_issue_types": tuple(_ordered(spec.intended_issues)),
            "expected_issue_types": tuple(types), "expected_primary_issue": blocking[0] if blocking else "NONE",
            "expected_blocked": bool(blocking),
            "expected_match_status": self._match_status(inv, state, gated, matched),
            "expected_duplicate_of": dup_of,
            "expected_assigned_roles": tuple(sorted({self.routing[t]["role"] for t in blocking})),
            "expected_queues": tuple(sorted({self.routing[t]["queue"] for t in types})),
            "expected_approval_band": decision["band"], "expected_approval_levels": decision["levels"],
            "expected_final_status": status, "expected_payment_ready": pay is not None,
            "expected_payment_status": pay["status"] if pay else None,
            "expected_due_date": pay["due"] if pay else None,
            "expected_scheduled_date": pay["scheduled"] if pay else None,
            "oracle_rule_ids": tuple(rules), "policy_version": self.policy.version,
            "description": doc.description or spec.description,
        }
        return row, mism


def label(ds: Dataset, policy: Policy) -> tuple[list[dict], list[dict]]:
    """Ground truth (invoices, lines). Raises OracleMismatch when any label differs from the intent."""
    return Oracle(ds, policy).run()
