"""Load and validate the versioned AP policy (config/ap_policy.toml).

The policy is configuration, not logic: the generator's oracle and the engine each implement the
rules independently and both read their parameters from here. validate_policy() checks structure
and internal consistency so a broken edit fails before any data is built.
"""
from __future__ import annotations

import hashlib
import re
import tomllib
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from .enums import (ACTOR_ROLES, APPROVAL_LEVELS, EXCEPTION_TYPES, HUMAN_ROLES, MATCH_STATUSES,
                    NON_BLOCKING_EXCEPTION_TYPES, QUEUES, SEVERITIES)
from .money import D
from .paths import DEFAULT_POLICY

REQUIRED_SECTIONS = ("policy", "calendar", "rounding", "extraction", "duplicates", "vendor",
                     "po_reference", "dates", "arithmetic", "tax", "matching", "precedence",
                     "routing", "assignment", "approval", "payment")
APPROVAL_PATHS = ("PO", "NON_PO")


class PolicyError(ValueError):
    """The policy file is missing, unparseable or internally inconsistent."""


@dataclass(frozen=True)
class Policy:
    raw: dict[str, Any]
    path: Path
    sha256: str

    @property
    def id(self) -> str:
        return self.raw["policy"]["id"]

    @property
    def version(self) -> str:
        return self.raw["policy"]["version"]

    @property
    def as_of_date(self) -> date:
        return date.fromisoformat(self.raw["policy"]["as_of_date"])

    def decimal(self, section: str, key: str) -> Decimal:
        return D(self.raw[section][key])

    def routing(self, exception_type: str) -> dict[str, Any]:
        return self.raw["routing"]["types"][exception_type]

    def bands(self, path: str) -> list[dict[str, Any]]:
        return [b for b in self.raw["approval"]["bands"] if b["path"] == path]


def load_policy(path: Path | str = DEFAULT_POLICY) -> Policy:
    path = Path(path)
    try:
        data = path.read_bytes()
        raw = tomllib.loads(data.decode("utf-8"))
    except (OSError, tomllib.TOMLDecodeError, UnicodeDecodeError) as exc:
        raise PolicyError(f"cannot read policy {path}: {exc}") from exc
    errors = validate_policy(raw)
    if errors:
        raise PolicyError("invalid policy:\n  " + "\n  ".join(errors))
    return Policy(raw=raw, path=path, sha256=hashlib.sha256(data).hexdigest())


def _dec(errors: list[str], where: str, value: Any, low: Decimal | None = None,
         high: Decimal | None = None) -> Decimal | None:
    if not isinstance(value, str):
        errors.append(f"{where}: decimals must be strings, got {type(value).__name__}")
        return None
    try:
        d = D(value)
    except ValueError:
        errors.append(f"{where}: not a decimal: {value!r}")
        return None
    if (low is not None and d < low) or (high is not None and d > high):
        errors.append(f"{where}: {value} outside [{low}, {high}]")
    return d


def _date(errors: list[str], where: str, value: Any) -> date | None:
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        errors.append(f"{where}: not an ISO date: {value!r}")
        return None


def validate_policy(raw: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    missing = [s for s in REQUIRED_SECTIONS if s not in raw]
    if missing:
        return [f"missing sections: {missing}"]
    pol = raw["policy"]
    if not re.fullmatch(r"\d+\.\d+\.\d+", str(pol.get("version", ""))):
        errors.append("policy.version must be MAJOR.MINOR.PATCH")
    start = _date(errors, "policy.effective_from", pol.get("effective_from"))
    as_of = _date(errors, "policy.as_of_date", pol.get("as_of_date"))
    if start and as_of and start > as_of:
        errors.append("policy.effective_from is after policy.as_of_date")
    for i, h in enumerate(raw["calendar"].get("holidays", [])):
        _date(errors, f"calendar.holidays[{i}]", h)

    _dec(errors, "extraction.min_field_confidence", raw["extraction"].get("min_field_confidence"),
         Decimal("0"), Decimal("1"))
    for section, key in (("arithmetic", "line_amount_abs"), ("arithmetic", "header_amount_abs"),
                         ("tax", "amount_abs"), ("matching", "price_tolerance_pct"),
                         ("matching", "over_receipt_tolerance_pct"), ("payment", "rtgs_min_amount")):
        _dec(errors, f"{section}.{key}", raw[section].get(key), Decimal("0"))
    unknown_ms = [m for m in raw["matching"].get("match_status_precedence", []) if m not in MATCH_STATUSES]
    if unknown_ms:
        errors.append(f"matching.match_status_precedence has unknown statuses {unknown_ms}")

    if list(raw["precedence"].get("order", [])) != list(EXCEPTION_TYPES):
        errors.append("precedence.order must list every exception type once, in enums.EXCEPTION_TYPES order")

    types = raw["routing"].get("types", {})
    if sorted(types) != sorted(EXCEPTION_TYPES):
        errors.append(f"routing.types must cover exactly {len(EXCEPTION_TYPES)} exception types")
    for name, entry in sorted(types.items()):
        where = f"routing.types.{name}"
        if entry.get("severity") not in SEVERITIES:
            errors.append(f"{where}: bad severity")
        if entry.get("role") not in HUMAN_ROLES:
            errors.append(f"{where}: role must be one of the five human actor roles")
        if not isinstance(entry.get("blocking"), bool):
            errors.append(f"{where}: blocking must be true/false")
        elif entry["blocking"] == (name in NON_BLOCKING_EXCEPTION_TYPES):
            errors.append(f"{where}: blocking flag disagrees with enums.NON_BLOCKING_EXCEPTION_TYPES")
        if entry.get("queue") not in QUEUES or entry.get("queue") == "APPROVALS":
            errors.append(f"{where}: queue must be an exception queue from enums.QUEUES")
        if not entry.get("raised_by"):
            errors.append(f"{where}: raised_by rule id is required")
        if not isinstance(entry.get("sla_business_days"), int) or entry["sla_business_days"] < 0:
            errors.append(f"{where}: sla_business_days must be a non-negative integer")
    routed_roles = {e.get("role") for e in types.values()}
    for role in sorted(r for r in routed_roles if r):
        if role not in raw["assignment"]:
            errors.append(f"assignment has no rule for routed role {role}")

    levels = raw["approval"].get("levels", {})
    if sorted(levels) != sorted(APPROVAL_LEVELS):
        errors.append(f"approval.levels must define exactly {APPROVAL_LEVELS}")
    for name, lvl in sorted(levels.items()):
        if lvl.get("role") not in ACTOR_ROLES:
            errors.append(f"approval.levels.{name}: bad role")
        if not isinstance(lvl.get("turnaround_business_days"), int) or lvl["turnaround_business_days"] < 0:
            errors.append(f"approval.levels.{name}: turnaround must be a non-negative integer")
    bands = raw["approval"].get("bands", [])
    rule_ids = [b.get("rule_id") for b in bands]
    if len(set(rule_ids)) != len(rule_ids):
        errors.append("approval.bands rule_id values must be unique")
    for path in APPROVAL_PATHS:
        expected_lower = Decimal("0.00")
        chain = [b for b in bands if b.get("path") == path]
        if not chain:
            errors.append(f"approval.bands: no bands for path {path}")
        for i, band in enumerate(chain):
            where = f"approval.bands[{path}:{band.get('band')}]"
            lower = _dec(errors, f"{where}.lower_exclusive", band.get("lower_exclusive"))
            if lower is not None and lower != expected_lower:
                errors.append(f"{where}: bands must be contiguous (expected lower {expected_lower})")
            if not band.get("levels") or any(lv not in APPROVAL_LEVELS for lv in band["levels"]):
                errors.append(f"{where}: levels must be a non-empty list of known levels")
            last = i == len(chain) - 1
            if last and "upper_inclusive" in band:
                errors.append(f"{where}: the last band must be open-ended")
            if not last:
                upper = _dec(errors, f"{where}.upper_inclusive", band.get("upper_inclusive"))
                if upper is not None and lower is not None and upper <= lower:
                    errors.append(f"{where}: upper must exceed lower")
                expected_lower = upper if upper is not None else expected_lower
    return errors
