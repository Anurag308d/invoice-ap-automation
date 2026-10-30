"""The engine's view of master data, always as of a moment (ADR-038, time-travel safety).

Every lookup takes the moment at which the engine decides: a vendor status counts only if it was
recorded by then (and is effective on the day asked), a receipt only if it was posted by then, a PO
only if it was dated by then. The as-of snapshot columns of master are never read.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from ..spec.io import read_table


def moment(ts: str) -> datetime:
    """Master timestamps are written in IST with an explicit offset; compare them as naive IST."""
    return datetime.fromisoformat(ts[:19])


class Master:
    def __init__(self, master_dir: Path):
        master_dir = Path(master_dir)
        self.vendors = {v["vendor_id"]: v for v in read_table(master_dir, "vendor")}
        self.history = defaultdict(list)
        for h in sorted(read_table(master_dir, "vendor_status_history"), key=lambda h: (h["vendor_id"], int(h["seq"]))):
            self.history[h["vendor_id"]].append((date.fromisoformat(h["effective_date"]), moment(h["recorded_at"]),
                                                 h["to_status"]))
        self.pos = {p["po_id"]: p for p in read_table(master_dir, "purchase_order")}
        self.po_lines = {l["po_line_id"]: l for l in read_table(master_dir, "purchase_order_line")}
        self.po_line_by_sku = defaultdict(list)
        for l in self.po_lines.values():
            self.po_line_by_sku[(l["po_id"], l["sku_id"])].append(l["po_line_id"])
        posted = {g["grn_id"]: moment(g["posted_at"]) for g in read_table(master_dir, "goods_receipt")}
        self.receipts = defaultdict(list)          # po_line_id -> [(posted_at, grn_line_id, qty)] in posting order
        for g in read_table(master_dir, "goods_receipt_line"):
            self.receipts[g["po_line_id"]].append((posted[g["grn_id"]], g["grn_line_id"], Decimal(g["received_qty"])))
        for rows in self.receipts.values():
            rows.sort()
        self.tax_codes = {t["tax_code"]: t for t in read_table(master_dir, "tax_code")}
        self.terms = {t["terms_code"]: int(t["net_days"]) for t in read_table(master_dir, "payment_terms")}
        self.users = {u["user_id"]: u for u in read_table(master_dir, "app_user")}

    def vendor_status(self, vendor_id: str, day: date, known_at: datetime) -> str | None:
        """Status effective on `day`, using only history rows recorded by `known_at`."""
        current = None
        for effective, recorded, status in self.history[vendor_id]:
            if effective <= day and recorded <= known_at:
                current = status
        return current

    def po_known(self, po_id: str | None, day: date) -> dict | None:
        po = self.pos.get(po_id or "")
        return po if po is not None and date.fromisoformat(po["po_date"]) <= day else None

    def receipts_until(self, po_line_id: str, at: datetime) -> list[tuple[datetime, str, Decimal]]:
        return [r for r in self.receipts[po_line_id] if r[0] <= at]

    def tax_valid(self, code: str, day: date) -> bool:
        t = self.tax_codes.get(code)
        return t is not None and date.fromisoformat(t["valid_from"]) <= day and (
            not t["valid_to"] or day <= date.fromisoformat(t["valid_to"]))

    def tax_rate(self, code: str) -> Decimal | None:
        t = self.tax_codes.get(code)
        return Decimal(t["rate_pct"]) if t else None

    def user_with(self, responsibility: str, cost_center: str | None = None) -> str | None:
        for uid in sorted(self.users):
            u = self.users[uid]
            if u["responsibility"] == responsibility and (cost_center is None or u["cost_center"] == cost_center):
                return uid
        return None
