"""Byte-stable CSV and JSON output in the exact column order of the spec (ADR-015)."""
from __future__ import annotations

import csv
import hashlib
import io
import json
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from ..spec import BY_NAME

IST = "+05:30"
CENT = Decimal("0.01")


def cell(ftype: str, value) -> str:
    """Canonical text form of one value (also what the quick validator reads back)."""
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


def _json_value(ftype: str, value):
    if value is None:
        return None
    if ftype == "bool":
        return bool(value)
    if ftype == "int":
        return int(value)
    if ftype == "list":
        return list(value)
    return cell(ftype, value)


def json_rows(table: str, rows: list[dict]) -> list[dict]:
    spec = BY_NAME[table]
    return [{f.name: _json_value(f.type, row[f.name]) for f in spec.fields} for row in rows]


def csv_bytes(table: str, rows: list[dict]) -> bytes:
    buf = io.StringIO(newline="")
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow([f.name for f in BY_NAME[table].fields])
    for r in as_strings(table, rows):
        writer.writerow(r.values())
    return buf.getvalue().encode("utf-8")


def json_bytes(obj) -> bytes:
    return (json.dumps(obj, indent=1, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def write_file(root: Path, rel: str, data: bytes, manifest: dict) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    manifest[rel] = {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def write_dataset(root: Path, tables: dict[str, list[dict]], extra_json: dict[str, object]) -> dict:
    """Write every table as CSV in its layer folder and as JSON under exports/json (evaluation
    layers in exports/json/evaluation/). Returns {relative path: {bytes, sha256, rows?}}."""
    files: dict[str, dict] = {}
    for table in sorted(tables):
        rows = tables[table]
        spec = BY_NAME[table]
        write_file(root, spec.file, csv_bytes(table, rows), files)
        files[spec.file]["rows"] = len(rows)
        sub = "evaluation/" if spec.layer in ("source", "ground_truth") else ""
        write_file(root, f"exports/json/{sub}{table}.json", json_bytes(json_rows(table, rows)), files)
    for rel, obj in sorted(extra_json.items()):
        write_file(root, rel, json_bytes(obj), files)
    return files
