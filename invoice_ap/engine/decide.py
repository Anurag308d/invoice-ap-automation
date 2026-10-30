"""PRI-01 outcome, RTE-01 exceptions, APR-01 / APR-SIM-01 approvals, PAY-01..06 payments and the
append-only AP event log, for one captured invoice at a time (business_rules sections 4-8).
"""
from __future__ import annotations

from datetime import datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal

from ..common import ids
from ..common.calendar import BusinessCalendar
from ..common.enums import EXCEPTION_TYPES
from .master import Master
from .routing import Router
from .validate import Issue, LineState, match_status

DECISION_LATENCY = timedelta(minutes=1)       # decided one minute after capture (synthetic, no wall clock)
PAYMENT_RUN = time(10, 0)                     # the simulated payment run releases payments at 10:00 IST
RANK = {t: i for i, t in enumerate(EXCEPTION_TYPES)}


class Decider:
    def __init__(self, master: Master, policy, router: Router):
        self.m, self.policy, self.router = master, policy, router
        raw = policy.raw
        self.raw, self.cal, self.as_of = raw, BusinessCalendar.from_policy(raw), policy.as_of_date
        self.as_of_end = datetime.combine(self.as_of, time(23, 59, 59))
        self.routing = raw["routing"]["types"]
        self.system = master.user_with("SYSTEM_USER")
        self.out = {t: [] for t in ("invoice_decision", "match_result", "match_allocation", "duplicate_pair",
                                    "approval", "payment", "ap_exception")}
        self.events: list[tuple] = []
        self.n = {"approval": 0, "payment": 0, "allocation": 0, "pair": 0}

    # ------------------------------------------------------------------ helpers
    def event(self, at, order, etype, entity, invoice_id, frm, to, role="SYSTEM", actor=None, rule=None, reason=None):
        self.events.append((at, order, len(self.events), etype, entity, invoice_id, frm, to, role,
                            actor or self.system, rule, reason))

    def _band(self, path: str, gross: Decimal) -> dict:
        for b in self.raw["approval"]["bands"]:
            if b["path"] == path and gross > Decimal(b["lower_exclusive"]) and (
                    "upper_inclusive" not in b or gross <= Decimal(b["upper_inclusive"])):
                return b
        raise ValueError(f"no approval band for {path} {gross}")

    def _approver(self, level: str, inv: dict, po: dict | None) -> str:
        assignee = self.raw["approval"]["levels"][level]["assignee"]
        if assignee == "INVOICE_ATTENTION_REQUESTER":
            return inv["attention_user_id"] or (po["requester_id"] if po else None) or self.router.owner
        if assignee == "COST_CENTER_MANAGER":
            requester = self.m.users.get(inv["attention_user_id"] or "")
            cc = po["cost_center"] if po else (requester["cost_center"] if requester else None)
            return self.m.user_with("COST_CENTER_MANAGER", cc) or self.router.owner
        return self.m.user_with(assignee) or self.router.owner

    # ------------------------------------------------------------------ one invoice
    def decide(self, inv: dict, lines: list[dict], order: int, received_at: datetime, captured_at: datetime,
               issues: list[Issue], states: dict[str, LineState], evaluated: bool, duplicate) -> dict:
        iid = inv["invoice_id"]
        decided_at = captured_at + DECISION_LATENCY
        self.event(received_at, order, "INVOICE", iid, iid, None, "RECEIVED", reason="intake registers document")
        self.event(captured_at, order, "INVOICE", iid, iid, "RECEIVED", "CAPTURED", rule="CAP-01",
                   reason="extraction finished; ID-01 assigned the invoice ID")
        issues = sorted(issues, key=lambda i: (RANK[i.type], i.line_id or ""))
        po = self.m.pos.get(inv["po_id"] or "")
        requester = (po["requester_id"] if po else None) or inv["attention_user_id"]
        if duplicate is not None:
            self.n["pair"] += 1
            self.out["duplicate_pair"].append({
                "duplicate_pair_id": ids.duplicate_pair_id(self.n["pair"]), "invoice_id": iid,
                "original_invoice_id": duplicate.original, "match_type": duplicate.match_type,
                "matched_keys": tuple(duplicate.keys)})
        blocking = [i for i in issues if self.routing[i.type]["blocking"]]
        band = levels = payment = None
        approvals: list[dict] = []
        late: list[tuple[Issue, datetime]] = []          # issues raised after approval (PAY-03, PAY-06)
        status = "REJECTED" if blocking and blocking[0].type == "DUPLICATE_EXACT" else "ON_HOLD" if blocking else None
        if not blocking:
            band, levels, approvals, status, payment, late = self._approve_and_pay(inv, po, decided_at, order)
        exceptions = self._raise(iid, issues, decided_at, requester, status == "REJECTED", order)
        if late:
            exceptions += self._raise(iid, [i for i, _ in late], late[0][1], requester, False, order,
                                      primary_taken=any(e["is_primary"] for e in exceptions))
        if blocking:
            self.event(decided_at, order, "INVOICE", iid, iid, "CAPTURED", status,
                       rule="DUP-01" if status == "REJECTED" else "PRI-01", reason=f"primary issue {blocking[0].type}")
        all_types = [i.type for i in issues] + [i.type for i, _ in late]
        primary = next((t for t in sorted(all_types, key=RANK.get) if self.routing[t]["blocking"]), "NONE")
        rules = {"CAP-01", "VEN-01", "ID-01", "PRI-01", "RTE-01"} | {self.routing[t]["raised_by"] for t in all_types}
        if inv["po_id"] and evaluated:
            rules.add("MS-01")
        for s in states.values():
            rules.update(s.rules)
        if band:
            rules.update({band["rule_id"], "APR-SIM-01"})
        if payment:
            rules.update({"PAY-01", "PAY-02", "PAY-04"} | ({"PAY-05"} if payment["status_as_of"] == "PAID" else set()))
        self._match_rows(inv, lines, states, evaluated)
        decision = {
            "invoice_id": iid, "status_as_of": status, "match_status": match_status(bool(inv["po_number"]), evaluated,
                                                                                  states.values()),
            "issue_types": tuple(sorted(set(all_types), key=RANK.get)), "primary_issue": primary,
            "blocked": status in ("ON_HOLD", "REJECTED"),
            "duplicate_of_invoice_id": duplicate.original if duplicate else None,
            "approval_band": band["band"] if band else None, "approval_levels": tuple(levels or ()),
            "payment_ready": payment is not None, "payment_id": payment["payment_id"] if payment else None,
            "decided_at": decided_at, "policy_version": self.policy.version, "rule_ids": tuple(sorted(rules))}
        self.out["invoice_decision"].append(decision)
        return decision

    def _raise(self, iid, issues, at, requester, rejected, order, primary_taken=False) -> list[dict]:
        rows = []
        first = None if primary_taken else next((i for i in issues if self.routing[i.type]["blocking"]), None)
        for i in issues:
            row = self.router.raise_exception(i.type, iid, at, primary=i is first, expected=i.expected,
                                              actual=i.actual, tolerance=i.tolerance, line_id=i.line_id,
                                              requester=requester, related=i.related)
            row["variance"] = i.variance
            self.event(at, order, "EXCEPTION", row["exception_id"], iid, None, "OPEN", rule="RTE-01",
                       reason=f"{i.type} -> {row['assigned_role']} / {row['queue']}")
            if rejected:
                row["status_as_of"], row["resolution_code"], row["is_overdue_as_of"] = "CLOSED", "INVOICE_REJECTED", False
                self.event(at, order, "EXCEPTION", row["exception_id"], iid, "OPEN", "CLOSED", rule="DUP-01",
                           reason="auto-closed: invoice rejected as an exact duplicate")
            rows.append(row)
        self.out["ap_exception"] += rows
        return rows

    def _approve_and_pay(self, inv, po, decided_at, order):
        iid = inv["invoice_id"]
        path = "PO" if inv["po_number"] else "NON_PO"
        band = self._band(path, inv["header_gross_amount"])
        levels = list(band["levels"])
        self.event(decided_at, order, "INVOICE", iid, iid, "CAPTURED", "PENDING_APPROVAL", rule="APR-01",
                   reason=f"no blocking issue; band {band['band']} -> {'/'.join(levels)}")
        approvals, t, last = [], decided_at, None
        for seq, level in enumerate(levels, start=1):
            cfg = self.raw["approval"]["levels"][level]
            user = self._approver(level, inv, po)
            self.n["approval"] += 1
            aid = ids.approval_id(self.n["approval"])
            day = self.cal.add_business_days(t.date(), int(cfg["turnaround_business_days"]))
            decided = datetime.combine(day, t.time()) if day != t.date() else t
            done = decided <= self.as_of_end
            approvals.append({"approval_id": aid, "invoice_id": iid, "level": level, "sequence": seq,
                              "approval_band": band["band"], "approver_role": cfg["role"], "approver_user_id": user,
                              "requested_at": t, "decided_at": decided if done else None,
                              "status_as_of": "APPROVED" if done else "PENDING", "rule_id": band["rule_id"],
                              "policy_version": self.policy.version})
            self.event(t, order, "APPROVAL", aid, iid, None, "PENDING", rule=band["rule_id"], reason=f"{level} requested")
            if not done:
                break
            self.event(decided, order, "APPROVAL", aid, iid, "PENDING", "APPROVED", role=cfg["role"], actor=user,
                       rule="APR-SIM-01", reason=f"{level} approved after {cfg['turnaround_business_days']} business days")
            t, last = decided, (cfg["role"], user)
        self.out["approval"] += approvals
        if approvals[-1]["status_as_of"] == "PENDING":
            return band, levels, approvals, "PENDING_APPROVAL", None, []
        self.event(t, order, "INVOICE", iid, iid, "PENDING_APPROVAL", "APPROVED", role=last[0], actor=last[1],
                   rule="APR-SIM-01", reason="last required level approved")
        status = self.m.vendor_status(inv["vendor_id"], t.date(), t)
        if status not in self.raw["vendor"]["payable_statuses"]:
            self.event(t, order, "INVOICE", iid, iid, "APPROVED", "ON_HOLD", rule="PAY-03",
                       reason=f"vendor {status} on the ready date")
            return band, levels, approvals, "ON_HOLD", None, [(Issue("VENDOR_NOT_PAYABLE", expected="ACTIVE",
                                                                     actual=str(status)), t)]
        terms = po["payment_terms_code"] if po else self.m.vendors[inv["vendor_id"]]["payment_terms_code"]
        due = inv["invoice_date"] + timedelta(days=self.m.terms[terms])
        scheduled = self.cal.previous_business_day(due, include_today=True)
        earliest = self.cal.next_business_day(t.date())
        late = []
        if scheduled < earliest:
            scheduled = earliest
            late.append((Issue("PAYMENT_DUE_DATE_PASSED", expected=f"pay by {due}", actual=f"scheduled {scheduled}"), t))
        paid = scheduled <= self.as_of
        self.n["payment"] += 1
        pid = ids.payment_id(self.n["payment"])
        amount = inv["header_gross_amount"]
        payment = {"payment_id": pid, "invoice_id": iid, "vendor_id": inv["vendor_id"], "amount": amount,
                   "currency": inv["currency"],
                   "payment_method": "RTGS" if amount >= Decimal(self.raw["payment"]["rtgs_min_amount"]) else "NEFT",
                   "due_date": due, "scheduled_date": scheduled, "created_at": t,
                   "paid_at": datetime.combine(scheduled, PAYMENT_RUN) if paid else None,
                   "status_as_of": "PAID" if paid else "SCHEDULED", "due_date_passed": bool(late),
                   "policy_version": self.policy.version}
        self.out["payment"].append(payment)
        self.event(t, order, "INVOICE", iid, iid, "APPROVED", "PAYMENT_READY", rule="PAY-01",
                   reason=f"ready; scheduled {scheduled} ({payment['payment_method']})")
        self.event(t, order, "PAYMENT", pid, iid, None, "SCHEDULED", rule="PAY-02", reason=f"due {due}")
        if paid:
            self.event(payment["paid_at"], order, "PAYMENT", pid, iid, "SCHEDULED", "PAID", rule="PAY-05",
                       reason="payment run")
            self.event(payment["paid_at"], order, "INVOICE", iid, iid, "PAYMENT_READY", "PAID", rule="PAY-05",
                       reason="payment run")
        return band, levels, approvals, "PAID" if paid else "PAYMENT_READY", payment, late

    def _match_rows(self, inv, lines, states, evaluated):
        tol = Decimal(self.raw["matching"]["price_tolerance_pct"])
        for ln in lines:
            s = states.get(ln["invoice_line_id"], LineState())
            matched = s.po_line_id is not None
            self.out["match_result"].append({
                "invoice_line_id": ln["invoice_line_id"], "invoice_id": inv["invoice_id"], "po_line_id": s.po_line_id,
                "price_status": s.price, "po_unit_price": s.po_price, "invoice_unit_price": ln["unit_price"] if matched else None,
                "price_variance_pct": s.variance.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP) if s.variance is not None else None,
                "price_tolerance_pct": tol if matched else None, "qty_status": s.qty, "ordered_qty": s.ordered,
                "received_qty": s.received, "prior_invoiced_qty": s.prior,
                "invoiced_qty": ln["quantity"] if matched else None,
                "max_qty_vs_po": s.max_qty.normalize() if s.max_qty is not None else None,
                "tax_status": s.tax, "po_tax_code": s.po_tax_code, "expected_tax_amount": s.expected_tax,
                "line_match_status": match_status(bool(inv["po_number"]), evaluated and matched, [s]),
                "rule_ids": tuple(sorted(set(s.rules)))})
            for seq, (grn_line, qty) in enumerate(s.allocations, start=1):
                self.n["allocation"] += 1
                self.out["match_allocation"].append({
                    "allocation_id": ids.allocation_id(self.n["allocation"]), "invoice_line_id": ln["invoice_line_id"],
                    "grn_line_id": grn_line, "allocated_qty": qty, "allocation_seq": seq})

    # ------------------------------------------------------------------ event log
    def event_rows(self) -> list[dict]:
        rows, seqs = [], {}
        for n, e in enumerate(sorted(self.events, key=lambda e: (e[0], e[1], e[2])), start=1):
            at, _, _, etype, entity, iid, frm, to, role, actor, rule, reason = e
            seqs[entity] = seqs.get(entity, 0) + 1
            rows.append({"event_id": ids.ap_event_id(n), "entity_type": etype, "entity_id": entity, "invoice_id": iid,
                         "seq": seqs[entity], "from_status": frm, "to_status": to, "event_at": at, "actor_role": role,
                         "actor_id": actor, "rule_id": rule, "reason": reason, "policy_version": self.policy.version})
        return rows
