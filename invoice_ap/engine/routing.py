"""RTE-01 / SLA-01: route an exception by the policy's routing matrix and assign a user deterministically.

Assignment within a role (business_rules section 6):
- business requester: the PO's requester, else the invoice's attention user;
- process owner: the policy owner (first user with the owner role);
- operations analyst: round-robin in exception-id order;
- system administrator: the vendor-master owner.
"""
from __future__ import annotations

from datetime import date, datetime

from ..common import ids
from ..common.calendar import BusinessCalendar


class Router:
    def __init__(self, policy, users: list[dict[str, str]]):
        self.policy = policy
        self.types = policy.raw["routing"]["types"]
        self.cal = BusinessCalendar.from_policy(policy.raw)
        self.analysts = sorted(u["user_id"] for u in users if u["role_code"] == "OPERATIONS_ANALYST")
        owner_role = policy.raw["policy"].get("owner_role", "PROCESS_OWNER")
        self.owner = min(u["user_id"] for u in users if u["role_code"] == owner_role)
        self.vendor_master = min(u["user_id"] for u in users if u["responsibility"] == "VENDOR_MASTER_OWNER")
        self.counter = 0
        self.analyst_turn = 0

    def _user(self, role: str, requester: str | None) -> str:
        if role == "OPERATIONS_ANALYST":
            user = self.analysts[self.analyst_turn % len(self.analysts)]
            self.analyst_turn += 1
            return user
        if role == "SYSTEM_ADMINISTRATOR":
            return self.vendor_master
        if role == "PROCESS_OWNER":
            return self.owner
        if role == "BUSINESS_REQUESTER" and requester:
            return requester
        return self.owner                       # no requester known: the policy owner takes it

    def raise_exception(self, exception_type: str, invoice_id: str, created_at: datetime, *, primary: bool,
                        expected: str | None = None, actual: str | None = None, tolerance: str | None = None,
                        line_id: str | None = None, requester: str | None = None, related: str | None = None) -> dict:
        rule = self.types[exception_type]
        self.counter += 1
        due = self.cal.add_business_days(created_at.date(), int(rule["sla_business_days"]))
        as_of: date = self.policy.as_of_date
        return {"exception_id": ids.exception_id(self.counter), "invoice_id": invoice_id, "invoice_line_id": line_id,
                "exception_type": exception_type, "severity": rule["severity"], "blocking": bool(rule["blocking"]),
                "is_primary": primary, "rule_id": rule["raised_by"], "policy_version": self.policy.version,
                "expected_value": expected, "actual_value": actual, "variance": None, "tolerance": tolerance,
                "related_invoice_id": related, "assigned_role": rule["role"],
                "assigned_user_id": self._user(rule["role"], requester), "queue": rule["queue"],
                "created_at": created_at, "sla_due_date": due, "status_as_of": "OPEN", "resolution_code": None,
                "is_overdue_as_of": due < as_of}
