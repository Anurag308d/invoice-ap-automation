"""Generated parts of docs/schema.md: keys and foreign keys (from the spec) and state machines
(from invoice_ap/common/lifecycle.py)."""
from __future__ import annotations

import re

from ..common.lifecycle import TERMINAL, TRANSITIONS
from . import TABLES


def keys_markdown() -> str:
    out = ["| Table | Layer | Primary key | Other unique keys | Foreign keys (column -> target) |",
           "|---|---|---|---|---|"]
    for t in TABLES:
        uniques = [f"`{f.name}`" for f in t.fields if f.unique and (f.name,) != t.primary_key]
        uniques += [f"`({', '.join(u)})`" for u in t.unique_together]
        fks = [f"`{f.name}` -> `{f.fk}`" + ("" if f.required else " (optional)")
               for f in t.fields if f.fk]
        out.append(f"| `{t.name}` | {t.layer} | `{', '.join(t.primary_key)}` | "
                   f"{', '.join(uniques) or '-'} | {'<br>'.join(fks) or '-'} |")
    fk_count = sum(1 for t in TABLES for f in t.fields if f.fk)
    out.append("")
    out.append(f"{len(TABLES)} tables, {fk_count} foreign keys. Polymorphic event references "
               "(`erp_event.entity_id`, `ap_event.entity_id`) are validated against the table named "
               "by `entity_type` instead of a declared FK.")
    return "\n".join(out) + "\n"


def _label(text: str) -> str:
    return re.split(r"[:(;]", text)[0].strip()[:48]


def state_machines_markdown() -> str:
    out: list[str] = []
    for entity, transitions in TRANSITIONS.items():
        out += [f"#### {entity}", "", "```mermaid", "stateDiagram-v2"]
        for (src, dst), why in transitions.items():
            out.append(f"  {src or '[*]'} --> {dst}: {_label(why)}")
        for state in TERMINAL[entity]:
            out.append(f"  {state} --> [*]")
        out += ["```", "", "| From | To | Trigger | Produced by the simulation |", "|---|---|---|---|"]
        for (src, dst), why in transitions.items():
            simulated = "no" if "not simulated" in why else "yes"
            out.append(f"| {src or '(create)'} | {dst} | {why} | {simulated} |")
        out.append("")
    return "\n".join(out)
