"""Machine-readable data dictionary model.

Field attributes follow assignment Step 1 (type, required/optional, allowed values, units,
uniqueness, validation rule) plus a description and an origin:
  source   - a value generated or printed as-is (the generator's primary data)
  derived  - computed from other records (formula in `derivation`; never generated independently)
  assigned - a deterministic identifier or sequence number
  captured - a value the engine extracted from a document
  decided  - a value the engine or the oracle decided by rule (rule IDs in `rule`)

`reporting_only` marks convenience snapshots (named snapshot_*) that sit in an engine-readable layer
but are evaluated at the as-of date. They would reveal the future to an invoice processed earlier,
so the engine must never read them (static test plus the Stage-4 time-travel sandbox; ADR-038).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..common.ids import PATTERNS

TYPES = {  # logical type -> (CSV/JSON representation, SQLite affinity)
    "id": ("text matching the ID pattern", "TEXT"),
    "code": ("reference code (FK to a reference table)", "TEXT"),
    "enum": ("one of the allowed values", "TEXT"),
    "text": ("UTF-8 text", "TEXT"),
    "int": ("base-10 integer", "INTEGER"),
    "money": ("decimal string, 2 places, INR", "NUMERIC"),
    "qty": ("decimal string, places per unit of measure", "NUMERIC"),
    "pct": ("decimal string, percent (18.00 = 18%)", "NUMERIC"),
    "decimal": ("decimal string", "NUMERIC"),
    "date": ("ISO date YYYY-MM-DD", "TEXT"),
    "datetime": ("ISO timestamp YYYY-MM-DDTHH:MM:SS+05:30 (IST)", "TEXT"),
    "bool": ("true or false", "INTEGER"),
    "list": ("pipe-separated in canonical order (precedence order for issue types, sequence order for "
             "approval levels, sorted otherwise), no spaces; empty = none", "TEXT"),
}
ORIGINS = ("source", "derived", "assigned", "captured", "decided")
LAYERS = ("master", "inbox", "source", "ground_truth", "processed")
WRITERS = ("generator", "oracle", "engine")


@dataclass(frozen=True)
class Field:
    name: str
    type: str
    description: str
    required: bool = True
    required_when: str = ""
    origin: str = "source"
    unit: str = ""
    allowed: tuple[str, ...] = ()
    pattern: str = ""
    min_value: str = ""
    max_value: str = ""
    unique: bool = False
    fk: str = ""
    rule: str = ""
    derivation: str = ""
    reporting_only: bool = False


@dataclass(frozen=True)
class Table:
    name: str
    layer: str
    writer: str
    description: str
    grain: str
    primary_key: tuple[str, ...]
    fields: tuple[Field, ...]
    entity: str = ""                       # assignment core-entity name, for the nine core tables
    unique_together: tuple[tuple[str, ...], ...] = ()
    notes: tuple[str, ...] = field(default=())

    @property
    def file(self) -> str:
        return f"{self.layer}/{self.name}.csv"

    def column(self, name: str) -> Field:
        return next(f for f in self.fields if f.name == name)


# ---- compact constructors -------------------------------------------------------------------------
def pk(name: str, kind: str, desc: str, **kw) -> Field:
    return Field(name, "id", desc, origin=kw.pop("origin", "assigned"), pattern=PATTERNS[kind],
                 unique=True, rule=kw.pop("rule", "unique, immutable, zero-padded counter"), **kw)


def ref(name: str, target: str, desc: str, kind: str = "", **kw) -> Field:
    ftype = "id" if kind else "code"
    return Field(name, kw.pop("type", ftype), desc, fk=target,
                 pattern=PATTERNS[kind] if kind else kw.pop("pattern", ""),
                 rule=kw.pop("rule", f"must exist in {target}"), **kw)


def enum(name: str, values, desc: str, **kw) -> Field:
    return Field(name, "enum", desc, allowed=tuple(values), **kw)


def lst(name: str, desc: str, values=(), **kw) -> Field:
    """A list column is always present, but an empty value is a legitimate empty list (S2-R1-01), so
    lists are never 'required' in the non-empty sense."""
    kw.setdefault("required", False)
    kw.setdefault("rule", "column always present; empty = empty list (none)")
    return Field(name, "list", desc, allowed=tuple(values), **kw)


def money(name: str, desc: str, **kw) -> Field:
    return Field(name, "money", desc, unit="INR", min_value=kw.pop("min_value", "0.00"), **kw)


def qty(name: str, desc: str, **kw) -> Field:
    return Field(name, "qty", desc, unit="unit of measure of the line",
                 min_value=kw.pop("min_value", "0"), **kw)


def pct(name: str, desc: str, **kw) -> Field:
    return Field(name, "pct", desc, unit="%", **kw)


def text(name: str, desc: str, **kw) -> Field:
    return Field(name, "text", desc, **kw)


def integer(name: str, desc: str, **kw) -> Field:
    return Field(name, "int", desc, unit=kw.pop("unit", "count"), **kw)


def ordinal(name: str, desc: str, **kw) -> Field:
    """1-based sequence or line number."""
    return Field(name, "int", desc, unit="ordinal", min_value=kw.pop("min_value", "1"), **kw)


def day(name: str, desc: str, **kw) -> Field:
    return Field(name, "date", desc, unit="calendar date", **kw)


def ts(name: str, desc: str, **kw) -> Field:
    return Field(name, "datetime", desc, unit="IST timestamp", **kw)


def flag(name: str, desc: str, **kw) -> Field:
    return Field(name, "bool", desc, allowed=("true", "false"), **kw)


def dec(name: str, desc: str, **kw) -> Field:
    return Field(name, "decimal", desc, unit=kw.pop("unit", "score 0-1"), **kw)
