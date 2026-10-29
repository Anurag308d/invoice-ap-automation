"""Master layer: ERP reference and purchasing data written by the generator, readable by the engine."""
from __future__ import annotations

from ..common import enums as E
from .model import Table, day, enum, flag, integer, money, pct, pk, qty, ref, text, ts

AS_OF = "as of policy.as_of_date (2026-12-31)"

ACTOR_ROLE = Table(
    "actor_role", "master", "generator",
    "The five assignment actors plus the SYSTEM automation actor.",
    "one row per actor role", ("role_code",), (
        enum("role_code", E.ACTOR_ROLES, "Role code", unique=True, origin="assigned"),
        text("role_name", "Human-readable role name"),
        flag("is_human", "False only for SYSTEM"),
        text("responsibilities", "What the role does in the AP workflow"),
    ))

APP_USER = Table(
    "app_user", "master", "generator",
    "Named users per role. Display names are role labels, never personal data.",
    "one row per user", ("user_id",), (
        pk("user_id", "user_id", "User identifier USR-0001"),
        text("display_name", "Role-based synthetic label, e.g. 'Requester - IT 02'", unique=True),
        ref("role_code", "actor_role.role_code", "Actor role of the user", type="enum",
            allowed=E.ACTOR_ROLES),
        enum("responsibility", E.RESPONSIBILITIES, "Named responsibility used by assignment rules"),
        enum("cost_center", E.COST_CENTERS, "Department served", required=False,
             required_when="role_code = BUSINESS_REQUESTER or responsibility = COST_CENTER_MANAGER"),
        enum("approval_level", ("L1", "L2", "L3"), "Approval level held", required=False,
             required_when="role_code = APPROVER"),
        text("email", "Synthetic address on the reserved example.com domain",
             pattern=r"^[a-z0-9.\-]+@example\.com$", unique=True),
        day("active_from", "Date the user became active"),
    ))

PAYMENT_TERMS = Table(
    "payment_terms", "master", "generator", "Vendor payment terms reference.",
    "one row per terms code", ("terms_code",), (
        enum("terms_code", ("NET15", "NET30", "NET45", "NET60"), "Terms code", unique=True,
             origin="assigned"),
        integer("net_days", "Days from invoice date to due date", min_value="1", max_value="90",
                unit="calendar days"),
        text("description", "Description"),
    ))

TAX_CODE = Table(
    "tax_code", "master", "generator",
    "Simplified synthetic GST-style tax codes with validity windows (effective-dated).",
    "one row per tax code", ("tax_code",), (
        enum("tax_code", ("GST0", "GST5", "GST12", "GST18", "EXEMPT"), "Tax code", unique=True,
             origin="assigned"),
        pct("rate_pct", "Tax rate", min_value="0.00", max_value="40.00"),
        enum("tax_category", E.TAX_CATEGORIES, "Tax category"),
        text("description", "Description"),
        day("valid_from", "First date the code may be used"),
        day("valid_to", "Last date the code may be used (empty = open-ended)", required=False,
            rule="valid_to >= valid_from; GST12 is retired before 2026 (TAX-01 rejects it)"),
    ))

SKU = Table(
    "sku", "master", "generator", "Catalogue of purchasable goods.",
    "one row per SKU", ("sku_id",), (
        pk("sku_id", "sku_id", "SKU identifier SKU-00001"),
        text("description", "Item description", unique=True),
        enum("category", E.GOODS_CATEGORIES, "Spend category; drives price and lead-time distributions"),
        enum("uom", E.UOMS, "Unit of measure; quantity precision follows enums.UOM_DECIMALS"),
        ref("default_tax_code", "tax_code.tax_code", "Tax code normally applied", type="enum",
            allowed=("GST0", "GST5", "GST18", "EXEMPT")),
        money("reference_price", "Catalogue reference unit price", min_value="0.01"),
        integer("lead_time_min_days", "Minimum supplier lead time", unit="calendar days", min_value="1"),
        integer("lead_time_max_days", "Maximum supplier lead time", unit="calendar days",
                rule="lead_time_max_days >= lead_time_min_days"),
    ))

VENDOR = Table(
    "vendor", "master", "generator", "Vendor master (synthetic companies).",
    "one row per vendor", ("vendor_id",), (
        pk("vendor_id", "vendor_id", "Vendor identifier VND-00001; also the <vendor-code> in invoice IDs"),
        text("vendor_name", "Synthetic company name", unique=True),
        text("tax_registration_id", "Synthetic tax registration number printed on invoices",
             pattern=r"^TRN-\d{9}$", unique=True),
        enum("segment", E.VENDOR_SEGMENTS, "GOODS vendors receive POs; SERVICES vendors bill non-PO"),
        enum("category", E.GOODS_CATEGORIES + E.SERVICE_CATEGORIES, "Primary supply category",
             rule="GOODS category iff segment = GOODS"),
        enum("tier", E.VENDOR_TIERS, "Activity tier (Pareto-like volume skew)"),
        ref("payment_terms_code", "payment_terms.terms_code", "Default payment terms", type="enum",
            allowed=("NET15", "NET30", "NET45", "NET60")),
        enum("preferred_channel", E.CHANNELS, "Usual invoice submission channel"),
        text("remit_email", "Synthetic sender address on a reserved .example domain",
             pattern=r"^ap@vnd-\d{5}\.example$", unique=True),
        day("onboarded_date", "Start of the vendor's active window",
            rule="equals effective_date of the vendor's first status event"),
        enum("status_as_of", E.VENDOR_STATUSES, f"Current status {AS_OF}", origin="derived",
             derivation="to_status of the last vendor_status_history row with effective_date <= as_of"),
        ref("created_by", "app_user.user_id", "System administrator who onboarded the vendor", "user_id"),
    ), entity="Vendor")

VENDOR_STATUS_HISTORY = Table(
    "vendor_status_history", "master", "generator",
    "Append-only, effective-dated vendor status changes (state machine in docs/schema.md).",
    "one row per vendor status change", ("vsh_id",), (
        pk("vsh_id", "vsh_id", "Status event identifier VSH-000001"),
        ref("vendor_id", "vendor.vendor_id", "Vendor", "vendor_id"),
        integer("seq", "1-based sequence per vendor", min_value="1", origin="assigned"),
        enum("from_status", E.VENDOR_STATUSES, "Status before the change (empty for the first row)",
             required=False, required_when="seq > 1"),
        enum("to_status", E.VENDOR_STATUSES, "Status after the change",
             rule="transition allowed by the vendor state machine"),
        day("effective_date", "Date the new status takes effect",
            rule="non-decreasing per vendor; first = onboarded_date"),
        ts("recorded_at", "When the change was recorded"),
        enum("actor_role", ("SYSTEM_ADMINISTRATOR",), "Role that made the change"),
        ref("actor_id", "app_user.user_id", "User that made the change", "user_id"),
        enum("reason_code", E.VENDOR_STATUS_REASONS, "Reason for the change"),
    ), unique_together=(("vendor_id", "seq"),))

PURCHASE_ORDER = Table(
    "purchase_order", "master", "generator", "Purchase orders raised by business requesters.",
    "one row per PO", ("po_id",), (
        pk("po_id", "po_id", "PO identifier PO-2026-000001"),
        ref("vendor_id", "vendor.vendor_id", "Ordering vendor (segment GOODS)", "vendor_id"),
        ref("requester_id", "app_user.user_id", "Business requester who raised the PO", "user_id",
            rule="user role BUSINESS_REQUESTER"),
        enum("cost_center", E.COST_CENTERS, "Cost centre charged", rule="equals the requester's cost_center"),
        day("po_date", "Issue date", rule="within 2026; vendor ACTIVE on po_date; on a business day"),
        enum("currency", ("INR",), "Currency"),
        ref("payment_terms_code", "payment_terms.terms_code", "Terms copied from the vendor at issue",
            type="enum", allowed=("NET15", "NET30", "NET45", "NET60")),
        integer("line_count", "Number of PO lines", min_value="1", max_value="8", origin="derived",
                derivation="count(purchase_order_line)"),
        money("total_net_amount", "Sum of line net amounts", origin="derived",
              derivation="sum(line_net_amount)"),
        money("total_tax_amount", "Sum of line tax amounts", origin="derived",
              derivation="sum(line_tax_amount)"),
        money("total_gross_amount", "Net plus tax", origin="derived",
              derivation="total_net_amount + total_tax_amount"),
        enum("status_as_of", E.PO_STATUSES, f"Receiving status {AS_OF}", origin="derived",
             derivation="to_status of the last erp_event for the PO with event_at <= as_of"),
    ), entity="PurchaseOrder")

PURCHASE_ORDER_LINE = Table(
    "purchase_order_line", "master", "generator", "PO lines (1-8 per PO).",
    "one row per PO line", ("po_line_id",), (
        pk("po_line_id", "po_line_id", "PO line identifier POL-<po_id>-01"),
        ref("po_id", "purchase_order.po_id", "Parent PO", "po_id",
            rule="must exist; equals the po_id embedded in po_line_id"),
        integer("line_number", "1-based line number", min_value="1", max_value="8", origin="assigned"),
        ref("sku_id", "sku.sku_id", "Ordered SKU", "sku_id"),
        text("description", "Item description copied from the SKU", origin="derived",
             derivation="sku.description"),
        enum("uom", E.UOMS, "Unit of measure copied from the SKU", origin="derived", derivation="sku.uom"),
        qty("ordered_qty", "Ordered quantity", min_value="0.01",
            rule="> 0 and a whole number for discrete units of measure"),
        money("unit_price", "Agreed unit price", min_value="0.01"),
        ref("tax_code", "tax_code.tax_code", "Tax code agreed on the PO", type="enum",
            allowed=("GST0", "GST5", "GST18", "EXEMPT"), rule="valid on po_date"),
        pct("tax_rate_pct", "Rate of tax_code", origin="derived", derivation="tax_code.rate_pct"),
        money("line_net_amount", "Net amount", origin="derived",
              derivation="round_half_up(ordered_qty x unit_price, 2)"),
        money("line_tax_amount", "Tax amount", origin="derived",
              derivation="round_half_up(line_net_amount x tax_rate_pct / 100, 2)"),
        money("line_gross_amount", "Gross amount", origin="derived",
              derivation="line_net_amount + line_tax_amount"),
        day("promised_delivery_date", "Delivery date promised on the PO",
            rule="po_date + SKU lead time (min..max days)"),
        qty("received_qty_as_of", f"Total received {AS_OF}", origin="derived",
            derivation="sum(goods_receipt_line.received_qty) for this PO line"),
        qty("open_qty_as_of", f"Quantity still to receive {AS_OF}", origin="derived",
            derivation="max(ordered_qty - received_qty_as_of, 0)"),
    ), entity="PurchaseOrderLine", unique_together=(("po_id", "line_number"),))

GOODS_RECEIPT = Table(
    "goods_receipt", "master", "generator", "Goods receipts (GRNs) confirmed by business requesters.",
    "one row per GRN", ("grn_id",), (
        pk("grn_id", "grn_id", "Receipt identifier GRN-2026-000001"),
        ref("po_id", "purchase_order.po_id", "PO being received", "po_id"),
        ref("vendor_id", "vendor.vendor_id", "Delivering vendor", "vendor_id", origin="derived",
            derivation="purchase_order.vendor_id", rule="equals the PO's vendor"),
        day("received_date", "Date the goods arrived", rule=">= po_date; business day"),
        ts("posted_at", "When the GRN was posted", rule="on received_date or later"),
        ref("received_by", "app_user.user_id", "Requester who confirmed the receipt", "user_id",
            rule="user role BUSINESS_REQUESTER"),
        text("delivery_note_number", "Vendor delivery-note reference"),
        integer("line_count", "Number of receipt lines", min_value="1", origin="derived",
                derivation="count(goods_receipt_line)"),
        enum("status_as_of", E.GRN_STATUSES, f"Status {AS_OF}", origin="derived",
             derivation="to_status of the last erp_event for the GRN"),
    ), entity="GoodsReceipt")

GOODS_RECEIPT_LINE = Table(
    "goods_receipt_line", "master", "generator", "Received quantities per PO line.",
    "one row per received PO line per GRN", ("grn_line_id",), (
        pk("grn_line_id", "grn_line_id", "Receipt line identifier GRNL-<grn_id>-01"),
        ref("grn_id", "goods_receipt.grn_id", "Parent GRN", "grn_id"),
        ref("po_line_id", "purchase_order_line.po_line_id", "PO line received", "po_line_id",
            rule="must belong to the GRN's PO"),
        integer("line_number", "1-based line number within the GRN", min_value="1", origin="assigned"),
        qty("received_qty", "Quantity received", min_value="0.01"),
        enum("uom", E.UOMS, "Unit of measure", origin="derived", derivation="purchase_order_line.uom"),
        qty("cumulative_received_qty", "Running received total for the PO line, in posting order",
            origin="derived", derivation="sum(received_qty) of this and earlier GRN lines of the PO line"),
        enum("receipt_type", E.RECEIPT_TYPES, "Partial, full or over-receipt", origin="derived",
             derivation="PARTIAL if cumulative < ordered; FULL if =; OVER if >"),
    ), entity="GoodsReceiptLine", unique_together=(("grn_id", "line_number"), ("grn_id", "po_line_id")))

ERP_EVENT = Table(
    "erp_event", "master", "generator",
    "Append-only PO and GRN lifecycle events (state machines in docs/schema.md).",
    "one row per PO or GRN state change", ("event_id",), (
        pk("event_id", "erp_event_id", "Event identifier ERP-2026-000001"),
        enum("entity_type", ("PURCHASE_ORDER", "GOODS_RECEIPT"), "Entity whose state changed"),
        text("entity_id", "po_id or grn_id", rule="exists in the table named by entity_type"),
        integer("seq", "1-based sequence per entity", min_value="1", origin="assigned"),
        enum("from_status", E.PO_STATUSES + E.GRN_STATUSES, "Status before (empty on creation)",
             required=False, required_when="seq > 1"),
        enum("to_status", E.PO_STATUSES + E.GRN_STATUSES, "Status after",
             rule="transition allowed by the entity's state machine"),
        ts("event_at", "When the change happened", rule="non-decreasing per entity"),
        enum("actor_role", ("BUSINESS_REQUESTER", "SYSTEM"), "Role that caused the change"),
        ref("actor_id", "app_user.user_id", "User that caused the change", "user_id"),
        enum("reason_code", E.ERP_EVENT_REASONS, "Why the state changed"),
        text("ref_id", "GRN that moved a PO's receiving status", required=False,
             required_when="entity_type = PURCHASE_ORDER and reason_code = GOODS_RECEIVED"),
    ), unique_together=(("entity_type", "entity_id", "seq"),))

MASTER_TABLES = (ACTOR_ROLE, APP_USER, PAYMENT_TERMS, TAX_CODE, SKU, VENDOR, VENDOR_STATUS_HISTORY,
                 PURCHASE_ORDER, PURCHASE_ORDER_LINE, GOODS_RECEIPT, GOODS_RECEIPT_LINE, ERP_EVENT)
