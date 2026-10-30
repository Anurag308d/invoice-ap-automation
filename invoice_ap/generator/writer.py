"""Byte-stable CSV and JSON output in the exact column order of the spec (ADR-015).

Data JSON (exports and ground_truth.json) is compact: no indent, sorted keys,
separators (",", ":"). Small human-facing reports keep an indent.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ..spec import BY_NAME
from ..spec.io import as_strings, cell, csv_bytes  # noqa: F401  (re-exported for callers)


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


def json_bytes(obj) -> bytes:
    """Readable JSON for small reports."""
    return (json.dumps(obj, indent=1, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def json_compact(obj) -> bytes:
    """Compact JSON for data files."""
    return (json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")


def write_file(root: Path, rel: str, data: bytes, manifest: dict) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    manifest[rel] = {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def write_dataset(root: Path, tables: dict[str, list[dict]], extra_json: dict[str, object]) -> dict:
    """Write every table as CSV in its layer folder (exports are written by invoice_ap.export once
    the engine has run). Returns {relative path: {bytes, sha256, rows?}}."""
    files: dict[str, dict] = {}
    for table in sorted(tables):
        rows = tables[table]
        spec = BY_NAME[table]
        write_file(root, spec.file, csv_bytes(table, rows), files)
        files[spec.file]["rows"] = len(rows)
    for rel, obj in sorted(extra_json.items()):
        write_file(root, rel, json_compact(obj), files)
    return files
