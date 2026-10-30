"""Layout-aware reader for text invoices (EMAIL bodies and SCAN OCR text).

Layout rules:
1. The line-item section starts at a table header (pipe table, or columns separated by two or more
   spaces, whose cells are all known column labels including description, quantity and amount) or at
   an item block ("Item 1"). Rows end at the first line that does not fit; blank lines, page markers
   and repeated table headers inside a column table are skipped (multi-page scans).
2. Header fields are read only above the item section, totals only below it, so "Tax" in the totals
   never collides with a "Tax" column. A meta line may hold two label pairs separated by three or more
   spaces. A label is separated from its value by ':' or by two or more spaces.
3. A field read twice with different values is a conflict (confidence 0.50). The vendor name may be
   an unlabelled letterhead: the nearest non-empty line above the tax registration line.
4. The currency is a labelled field or, failing that, the currency marker of the totals.
"""
from __future__ import annotations

import re

from .fields import CONFLICT, Extracted, RawCapture, make, missing
from .labels import BLOCK_START, COLUMNS, HEADER, TOTALS, lookup
from .normalize import label_key
from .read import read_value

PAGE = re.compile(r"-+\s*page\s+\d+\s+of\s+\d+\s*-+", re.IGNORECASE)
BLOCK = re.compile(r"(item|line|sr|s\.?\s*no\.?)\s+(\d+)", re.IGNORECASE)
CURRENCY_MARK = re.compile(r"^(INR|Rs\.?|₹)", re.IGNORECASE)


def _pairs(line: str) -> list[tuple[str, str]]:
    s = line.strip()
    if not s:
        return []
    segments = re.split(r"\s{3,}", s) if s.count(":") >= 2 else [s]
    out = []
    for seg in segments:
        if ":" in seg:
            label, value = seg.split(":", 1)
        else:
            m = re.fullmatch(r"(.*?\S)\s{2,}(\S.*)", seg)
            if not m:
                continue
            label, value = m[1], m[2]
        out.append((label.strip(), value.strip()))
    return out


def _cells(line: str, kind: str) -> list[str]:
    s = line.strip()
    if kind == "pipe":
        return [c.strip() for c in s.strip("|").split("|")]
    return re.split(r"\s{2,}", s)


def _header_columns(cells: list[str]) -> list[tuple[str, str]] | None:
    hits = [lookup(COLUMNS, label_key(c)) for c in cells]
    if any(h is None for h in hits):
        return None
    names = [h[0] for h in hits]
    if len(set(names)) != len(names) or not {"description", "quantity", "line_net_amount"} <= set(names):
        return None
    return hits


def _find_items(lines: list[str]):
    for i, line in enumerate(lines):
        s = line.strip()
        if not s:
            continue
        m = BLOCK.fullmatch(s)
        if m and label_key(m[1]) in BLOCK_START:
            return "block", i, None
        kind = "pipe" if s.startswith("|") else "columns"
        cells = _cells(s, kind)
        if len(cells) >= 3:
            cols = _header_columns(cells)
            if cols:
                return kind, i, (cells, cols)
    return None, None, None


def _row(raw: dict[str, tuple[str, str]]) -> dict[str, Extracted]:
    """raw: field -> (text, method). Unit of measure first, because quantity precision depends on it."""
    out: dict[str, Extracted] = {}
    if "uom" in raw:
        out["uom"] = read_value("uom", raw["uom"][0], raw["uom"][1])
    uom = out["uom"].value if "uom" in out else None
    for name, (text, method) in raw.items():
        if name != "uom":
            out[name] = read_value(name, text, method, uom=uom)
    return out


def _table(lines, kind, start, cells, cols):
    header_keys = [label_key(c) for c in cells]
    rows, i = [], start + 1
    while i < len(lines):
        s = lines[i].strip()
        if kind == "pipe":
            if not s.startswith("|"):
                break
            if re.fullmatch(r"[\s\-:|]+", s):
                i += 1
                continue
        elif not s or PAGE.fullmatch(s):
            i += 1
            continue
        row = _cells(s, kind)
        if [label_key(c) for c in row] == header_keys:     # header repeated on a new page
            i += 1
            continue
        if len(row) != len(cols):
            break
        rows.append(_row({name: (text, method) for (name, method), text in zip(cols, row)}))
        i += 1
    return rows, i


def _blocks(lines, start):
    blocks: list[dict] = []
    conflicts: set[int] = set()
    i = start
    while i < len(lines):
        line, s = lines[i], lines[i].strip()
        m = BLOCK.fullmatch(s)
        if m and label_key(m[1]) in BLOCK_START:
            blocks.append({"line_number": (m[2], "PATTERN")})
            i += 1
            continue
        if not s:
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            nxt = BLOCK.fullmatch(lines[j].strip()) if j < len(lines) else None
            if nxt and label_key(nxt[1]) in BLOCK_START:
                i = j
                continue
            break
        if blocks and line[:1] in (" ", "\t") and ":" in s:
            label, value = s.split(":", 1)
            hit = lookup(COLUMNS, label_key(label))
            if hit:
                if hit[0] in blocks[-1]:
                    conflicts.add(len(blocks) - 1)
                blocks[-1][hit[0]] = (value.strip(), hit[1])
            i += 1
            continue
        break
    rows = [_row(b) for b in blocks]
    for k in conflicts:
        for e in rows[k].values():
            e.confidence = min(e.confidence, CONFLICT)
    return rows, i


def _put(target: dict, name: str, ext: Extracted) -> None:
    if name in target:
        prev = target[name]
        if prev.value != ext.value:
            target[name] = Extracted(prev.raw, prev.value, prev.method, min(prev.confidence, CONFLICT))
        return
    target[name] = ext


def parse_text(lines: list[str]) -> RawCapture:
    lines = [ln.rstrip() for ln in lines]
    kind, start, header_info = _find_items(lines)
    rows: list[dict] = []
    end = len(lines)
    if kind == "block":
        rows, end = _blocks(lines, start)
    elif kind:
        rows, end = _table(lines, kind, start, *header_info)
    meta = lines[:start] if kind else lines
    after = lines[end:] if kind else lines
    header: dict[str, Extracted] = {}
    tax_line = None
    for idx, line in enumerate(meta):
        for label, value in _pairs(line):
            hit = lookup(HEADER, label_key(label))
            if hit:
                _put(header, hit[0], read_value(hit[0], value, hit[1]))
                if hit[0] == "vendor_tax_id" and tax_line is None:
                    tax_line = idx
    marks = set()
    for line in after:
        for label, value in _pairs(line):
            hit = lookup(TOTALS, label_key(label))
            if hit:
                _put(header, hit[0], read_value(hit[0], value, hit[1]))
                if m := CURRENCY_MARK.match(value.strip()):
                    marks.add(m[1].upper().rstrip("."))
    if "vendor_name" not in header and tax_line is not None:
        above = [ln.strip() for ln in meta[:tax_line] if ln.strip()]
        if above and not _pairs(above[-1]):
            header["vendor_name"] = make(above[-1], above[-1], "PATTERN")
    if "currency" not in header and len(marks) == 1:
        header["currency"] = make(next(iter(marks)), "INR", "PATTERN")
    if not rows:
        items = missing()
    else:
        numbers = [r["line_number"].value for r in rows if "line_number" in r]
        ok = len(numbers) == len(rows) and None not in numbers and len(set(numbers)) == len(numbers)
        items = make(f"{len(rows)} lines", len(rows), "PATTERN")
        if not ok:
            items = Extracted(items.raw, items.value, items.method, CONFLICT)
    return RawCapture(header, rows, items)
