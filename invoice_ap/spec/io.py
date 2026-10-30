"""Canonical text form of values and byte-stable CSV in the exact spec column order (ADR-015).

Shared by the generator (writing master, inbox, source and ground truth) and the engine (reading
master and inbox, writing processed), so neither has to import the other.
"""
from __future__ import annotations

import csv
import io
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from . import BY_NAME

IST = "+05:30"
CENT = Decimal("0.01")


def cell(ftype: str, value) -> str:
    """Canonical text form of one value."""
    if value is None:
        return ""
    if ftype == "bool":
        return "true" if value else "false"
    if ftype == "list":
        return "|".join(value)
    if isinstance(value, datetime):
        return value.isoformat(timespec="seconds") + IST
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        if ftype in ("money", "pct"):     # exactly two decimals; never round silently here
            if value != value.quantize(CENT):
                raise ValueError(f"{ftype} value {value} is not a whole cent")
            return f"{value.quantize(CENT):f}"
        return f"{value:f}"
    return str(value)


def as_strings(table: str, rows: list[dict]) -> list[dict[str, str]]:
    spec = BY_NAME[table]
    names = [f.name for f in spec.fields]
    out = []
    for row in rows:
        if list(row) != names:
            missing, extra = set(names) - set(row), set(row) - set(names)
            if missing or extra:
                raise ValueError(f"{table}: columns differ from spec (missing {missing}, extra {extra})")
        out.append({f.name: cell(f.type, row[f.name]) for f in spec.fields})
    return out


def csv_bytes(table: str, rows: list[dict]) -> bytes:
    buf = io.StringIO(newline="")
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow([f.name for f in BY_NAME[table].fields])
    for r in as_strings(table, rows):
        writer.writerow(r.values())
    return buf.getvalue().encode("utf-8")


def read_table(folder: Path, table: str) -> list[dict[str, str]]:
    """Read one table's CSV from a layer folder (the folder that holds `<table>.csv`)."""
    with open(Path(folder) / f"{table}.csv", newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    expected = [f.name for f in BY_NAME[table].fields]
    if rows and list(rows[0]) != expected:
        raise ValueError(f"{table}: header differs from the spec")
    return rows
