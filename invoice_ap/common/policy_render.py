"""Markdown views of config/ap_policy.toml for docs/business_rules.md (generated blocks)."""
from __future__ import annotations

from .enums import EXCEPTION_TYPES
from .policy import Policy, load_policy


def routing_markdown(policy: Policy | None = None) -> str:
    pol = policy or load_policy()
    types = pol.raw["routing"]["types"]
    out = ["| Precedence | Exception type | Raised by | Severity | Blocking | Actor role | Queue | SLA (business days) |",
           "|---|---|---|---|---|---|---|---|"]
    for rank, name in enumerate(EXCEPTION_TYPES, start=1):
        e = types[name]
        out.append(f"| {rank} | `{name}` | {e['raised_by']} | {e['severity']} | "
                   f"{'yes' if e['blocking'] else 'no'} | {e['role']} | {e['queue']} | {e['sla_business_days']} |")
    return "\n".join(out) + "\n"


def approval_markdown(policy: Policy | None = None) -> str:
    pol = policy or load_policy()
    levels = pol.raw["approval"]["levels"]
    out = ["| Rule | Path | Band | Gross amount (INR) | Levels in order | Approver roles |",
           "|---|---|---|---|---|---|"]
    for b in pol.raw["approval"]["bands"]:
        upper = b.get("upper_inclusive")
        rng = f"> {b['lower_exclusive']} and <= {upper}" if upper else f"> {b['lower_exclusive']}"
        roles = ", ".join(f"{lv}: {levels[lv]['role']} ({levels[lv]['assignee']})" for lv in b["levels"])
        out.append(f"| {b['rule_id']} | {b['path']} | {b['band']} | {rng} | {' -> '.join(b['levels'])} | {roles} |")
    out += ["", "| Level | Role | Assignee rule | Simulated turnaround (business days) |", "|---|---|---|---|"]
    for name, lv in levels.items():
        out.append(f"| {name} | {lv['role']} | {lv['assignee']} | {lv['turnaround_business_days']} |")
    return "\n".join(out) + "\n"
