"""Machine-readable data dictionary: the single source for docs/data_dictionary.md and
invoice_ap/spec/data_dictionary.json. Later stages use it for headers, validation and SQL DDL."""
from __future__ import annotations

from .model import LAYERS, ORIGINS, TYPES, Field, Table
from .tables_documents import DOCUMENT_TABLES
from .tables_master import MASTER_TABLES
from .tables_processed import PROCESSED_TABLES

SPEC_VERSION = "1.0.0"
TABLES: tuple[Table, ...] = MASTER_TABLES + DOCUMENT_TABLES + PROCESSED_TABLES
BY_NAME: dict[str, Table] = {t.name: t for t in TABLES}
CORE_ENTITIES = ("Vendor", "PurchaseOrder", "PurchaseOrderLine", "GoodsReceipt", "GoodsReceiptLine",
                 "Invoice", "InvoiceLine", "Approval", "Payment")


def table(name: str) -> Table:
    return BY_NAME[name]


def core_table(entity: str) -> Table:
    return next(t for t in TABLES if t.entity == entity)


__all__ = ["CORE_ENTITIES", "BY_NAME", "Field", "LAYERS", "ORIGINS", "SPEC_VERSION", "TABLES",
           "TYPES", "Table", "core_table", "table"]
