"""Processed layer: everything the engine writes (built only from master data and the inbox)."""
from __future__ import annotations

from ..common import enums as E
from .model import Table, day, dec, enum, flag, integer, lst, money, ordinal, pct, pk, qty, ref, text, ts

TAX_CODES = ("GST0", "GST5", "GST12", "GST18", "EXEMPT")
_LOWCONF = "unless capture_status = LOW_CONFIDENCE (then empty when unreadable)"
_ISSUES = E.EXCEPTION_TYPES

CAPTURED_INVOICE = Table(
    "captured_invoice", "processed", "engine",
    "Header fields as extracted from the document, plus engine-resolved references. Printed values are "
    "never corrected: a wrong printed total stays wrong here so validation can catch it.",
    "one row per received document", ("invoice_id",), (
        pk("invoice_id", "invoice_id", "Invoice ID assigned after vendor resolution", origin="decided",
           rule="ID-01: INV-<VEN-01 vendor_id, or VND-00000 if unresolved>-2026-<intake_seq>; equals "
                "the source invoice_id exactly when the vendor was resolved correctly"),
        ref("doc_id", "intake_manifest.doc_id", "Source document", "doc_id", unique=True),
        enum("channel", E.CHANNELS, "Intake channel", origin="derived", derivation="intake_manifest.channel"),
        ts("captured_at", "When extraction finished", origin="decided",
           rule=">= intake_manifest.received_at and <= as_of_date"),
        enum("capture_status", E.CAPTURE_STATUSES, "LOW_CONFIDENCE when any required field < threshold",
             origin="decided", rule="CAP-01"),
        dec("min_field_confidence", "Lowest confidence over required fields", min_value="0",
            max_value="1", origin="derived", derivation="min(extraction_field.confidence)"),
        text("vendor_name", "Vendor name as printed", origin="captured"),
        text("vendor_tax_id", "Tax registration number as printed", origin="captured"),
        ref("vendor_id", "vendor.vendor_id", "Vendor resolved from the printed tax registration number",
            "vendor_id", required=False, origin="decided",
            rule="VEN-01 is its only source (never the sender or an ID); empty = VENDOR_NOT_FOUND"),
        text("vendor_invoice_number", "Invoice number as printed", origin="captured",
             required=False, required_when=_LOWCONF),
        text("normalized_invoice_number", "Number after DUP normalisation", origin="derived", required=False,
             required_when="vendor_invoice_number was read (empty when the printed number is unreadable)",
             derivation="uppercase, split on non-alphanumerics, strip leading zeros per numeric token, join"),
        day("invoice_date", "Invoice date (normalised to ISO)", origin="captured", required=False,
            required_when=_LOWCONF, rule="a valid calendar date; DATE-01 requires <= received date"),
        text("po_number", "PO reference as printed", required=False, origin="captured"),
        ref("po_id", "purchase_order.po_id", "Resolved PO", "po_id", required=False, origin="decided",
            rule="PO-01"),
        ref("attention_user_id", "app_user.user_id", "Requester named on a non-PO invoice", "user_id",
            required=False, origin="decided"),
        enum("currency", ("INR",), "Currency", origin="captured"),
        money("header_net_amount", "Printed net total", origin="captured", required=False,
              required_when=_LOWCONF),
        money("header_tax_amount", "Printed tax total", origin="captured", required=False,
              required_when=_LOWCONF),
        money("header_gross_amount", "Printed invoice total", origin="captured", required=False,
              required_when=_LOWCONF),
        integer("line_count", "Lines extracted", min_value="1", origin="derived",
                derivation="count(captured_invoice_line)"),
    ))

CAPTURED_INVOICE_LINE = Table(
    "captured_invoice_line", "processed", "engine", "Line fields as extracted.",
    "one row per extracted invoice line", ("invoice_line_id",), (
        pk("invoice_line_id", "invoice_line_id", "Line ID INVL-<invoice_id>-<printed line number>",
           rule="unique; built from invoice_id and the printed line number"),
        ref("invoice_id", "captured_invoice.invoice_id", "Parent captured invoice", "invoice_id"),
        ordinal("line_number", "Printed line number", min_value="1", origin="captured"),
        ordinal("po_line_number", "PO line number as printed", required=False, origin="captured",
                rule="must resolve to a line of the quoted PO (PO-03)"),
        ref("po_line_id", "purchase_order_line.po_line_id", "Resolved PO line", "po_line_id",
            required=False, origin="decided", rule="PO-03"),
        ref("sku_id", "sku.sku_id", "SKU as printed", "sku_id", required=False, origin="captured"),
        text("description", "Description as printed", origin="captured"),
        enum("uom", E.UOMS, "Unit of measure", origin="captured"),
        qty("quantity", "Quantity as printed", origin="captured"),
        money("unit_price", "Unit price as printed", origin="captured"),
        money("line_net_amount", "Line amount as printed", origin="captured"),
        ref("tax_code", "tax_code.tax_code", "Tax code as printed", type="enum", allowed=TAX_CODES,
            origin="captured"),
        money("tax_amount", "Tax amount as printed", origin="captured"),
        dec("min_field_confidence", "Lowest confidence over the line's fields", min_value="0",
            max_value="1", origin="derived", derivation="min(extraction_field.confidence)"),
    ), unique_together=(("invoice_id", "line_number"),))

EXTRACTION_FIELD = Table(
    "extraction_field", "processed", "engine",
    "Per-field extraction evidence: raw text, normalised value, method and confidence.",
    "one row per extracted field", ("extraction_field_id",), (
        pk("extraction_field_id", "extraction_field_id", "EXF-2026-000001"),
        ref("doc_id", "intake_manifest.doc_id", "Document", "doc_id"),
        ref("invoice_id", "captured_invoice.invoice_id", "Invoice", "invoice_id"),
        ref("invoice_line_id", "captured_invoice_line.invoice_line_id", "Line (empty for header fields)",
            "invoice_line_id", required=False),
        text("field_name", "Logical field name, e.g. header_gross_amount, quantity"),
        text("raw_text", "Text exactly as found in the document", required=False, origin="captured"),
        text("normalized_value", "Canonical value after normalisation", required=False, origin="captured"),
        dec("confidence", "Extraction confidence", min_value="0", max_value="1", origin="decided"),
        enum("method", E.EXTRACTION_METHODS, "How the value was found", origin="decided"),
        flag("is_low_confidence", "confidence < extraction.min_field_confidence", origin="derived",
             derivation="confidence < policy threshold"),
    ), unique_together=(("doc_id", "invoice_line_id", "field_name"),))

INVOICE_DECISION = Table(
    "invoice_decision", "processed", "engine",
    "Engine decision summary per invoice (what evaluation compares with ground truth).",
    "one row per invoice", ("invoice_id",), (
        ref("invoice_id", "captured_invoice.invoice_id", "Invoice", "invoice_id", unique=True),
        enum("status_as_of", E.INVOICE_STATUSES, "Status at the as-of date", origin="derived",
             derivation="to_status of the last INVOICE ap_event"),
        enum("match_status", E.MATCH_STATUSES, "Invoice match status", origin="decided", rule="MS-01"),
        lst("issue_types", "All issues raised (blocking and non-blocking)", _ISSUES, origin="decided"),
        enum("primary_issue", _ISSUES + ("NONE",), "Highest-precedence blocking issue",
             origin="decided", rule="PRI-01"),
        flag("blocked", "At least one open blocking exception", origin="derived",
             derivation="exists ap_exception with blocking and status_as_of = OPEN, or REJECTED"),
        ref("duplicate_of_invoice_id", "captured_invoice.invoice_id", "Original of a detected duplicate",
            "invoice_id", required=False, origin="decided"),
        text("approval_band", "Approval band applied", required=False, origin="decided", rule="APR-01"),
        lst("approval_levels", "Approval levels required, in order", E.APPROVAL_LEVELS, origin="decided"),
        flag("payment_ready", "A payment record exists", origin="derived",
             derivation="exists payment for invoice_id", rule="never true when blocked"),
        ref("payment_id", "payment.payment_id", "Payment record", "payment_id", required=False),
        ts("decided_at", "When validation and matching finished", origin="decided",
           rule=">= captured_invoice.captured_at and <= as_of_date"),
        text("policy_version", "Policy version applied", fk="policy_version.policy_version"),
        lst("rule_ids", "Rule IDs that fired", origin="decided", pattern=r"^(?:[A-Z]{2,4}(?:-[A-Z]{2,4})?-\d{2}(?:\|[A-Z]{2,4}(?:-[A-Z]{2,4})?-\d{2})*)?$",
            rule="each ID is documented in docs/business_rules.md"),
    ))

MATCH_RESULT = Table(
    "match_result", "processed", "engine",
    "Line-level three-way match (PO line vs receipts vs invoice line) with the tolerance used.",
    "one row per captured invoice line", ("invoice_line_id",), (
        ref("invoice_line_id", "captured_invoice_line.invoice_line_id", "Invoice line",
            "invoice_line_id", unique=True),
        ref("invoice_id", "captured_invoice.invoice_id", "Invoice", "invoice_id"),
        ref("po_line_id", "purchase_order_line.po_line_id", "Matched PO line", "po_line_id",
            required=False, required_when="the line was matched"),
        enum("price_status", E.LINE_PRICE_STATUSES, "Price check", origin="decided", rule="MAT-02"),
        money("po_unit_price", "PO unit price", required=False),
        money("invoice_unit_price", "Invoiced unit price", required=False),
        dec("price_variance_pct", "Signed variance (invoice - PO) / PO x 100", required=False,
            unit="%", origin="derived", derivation="exact, not rounded"),
        pct("price_tolerance_pct", "Tolerance applied", required=False, origin="derived",
            derivation="matching.price_tolerance_pct"),
        enum("qty_status", E.LINE_QTY_STATUSES, "Quantity check", origin="decided",
             rule="MAT-01, MAT-03, MAT-04"),
        qty("ordered_qty", "PO line quantity", required=False),
        qty("received_qty", "Cumulative received at processing time", required=False, origin="derived",
            derivation="sum of GRN lines posted before decided_at"),
        qty("prior_invoiced_qty", "Billed on earlier non-duplicate invoices", required=False,
            origin="derived", derivation="sum of quantities on earlier non-duplicate invoices of the PO line"),
        qty("invoiced_qty", "Billed on this line", required=False),
        qty("max_qty_vs_po", "Upper quantity limit from the PO", required=False, origin="derived",
            derivation="ordered_qty x (1 + over_receipt_tolerance_pct / 100)"),
        enum("tax_status", E.LINE_TAX_STATUSES, "Tax check", origin="decided", rule="TAX-01..03"),
        ref("po_tax_code", "tax_code.tax_code", "PO line tax code", type="enum", allowed=TAX_CODES,
            required=False),
        money("expected_tax_amount", "Recomputed tax for the printed net", required=False,
              origin="derived", derivation="round_half_up(line_net_amount x rate / 100, 2)"),
        enum("line_match_status", E.MATCH_STATUSES, "Line match status", origin="decided", rule="MS-01"),
        lst("rule_ids", "Rule IDs evaluated", origin="decided", pattern=r"^(?:[A-Z]{2,4}(?:-[A-Z]{2,4})?-\d{2}(?:\|[A-Z]{2,4}(?:-[A-Z]{2,4})?-\d{2})*)?$",
            rule="each ID is documented in docs/business_rules.md"),
    ))

MATCH_ALLOCATION = Table(
    "match_allocation", "processed", "engine",
    "Bridge table for the many-to-many invoice line <-> goods receipt line relationship "
    "(FIFO allocation of billed quantity to received quantity).",
    "one row per (invoice line, GRN line) allocation", ("allocation_id",), (
        pk("allocation_id", "allocation_id", "ALC-2026-000001"),
        ref("invoice_line_id", "captured_invoice_line.invoice_line_id", "Invoice line", "invoice_line_id"),
        ref("grn_line_id", "goods_receipt_line.grn_line_id", "Receipt line", "grn_line_id",
            rule="same PO line as the invoice line; posted before the invoice was processed"),
        qty("allocated_qty", "Quantity of the receipt line consumed", min_value="0.01", origin="decided"),
        ordinal("allocation_seq", "FIFO order within the invoice line", min_value="1", origin="assigned"),
    ), unique_together=(("invoice_line_id", "grn_line_id"),))

DUPLICATE_PAIR = Table(
    "duplicate_pair", "processed", "engine", "Detected duplicate -> original pairs.",
    "one row per detected duplicate document", ("duplicate_pair_id",), (
        pk("duplicate_pair_id", "duplicate_pair_id", "DUP-2026-000001"),
        ref("invoice_id", "captured_invoice.invoice_id", "Later document flagged as duplicate",
            "invoice_id", unique=True),
        ref("original_invoice_id", "captured_invoice.invoice_id", "Earlier original", "invoice_id",
            rule="received before invoice_id; same vendor"),
        enum("match_type", E.DUPLICATE_MATCH_TYPES, "Which duplicate rule matched", origin="decided",
             rule="DUP-01..03"),
        lst("matched_keys", "Fields that matched", ("vendor_id", "normalized_number", "invoice_date",
            "header_gross_amount", "po_id"), origin="decided", rule="the key set of the matching DUP rule"),
    ))

AP_EXCEPTION = Table(
    "ap_exception", "processed", "engine",
    "Exceptions with expected vs actual, tolerance, routing and SLA (named ap_exception because "
    "EXCEPTION is a keyword in some SQL dialects).",
    "one row per raised exception", ("exception_id",), (
        pk("exception_id", "exception_id", "EXC-2026-000001"),
        ref("invoice_id", "captured_invoice.invoice_id", "Invoice", "invoice_id"),
        ref("invoice_line_id", "captured_invoice_line.invoice_line_id", "Line (empty = header level)",
            "invoice_line_id", required=False),
        enum("exception_type", _ISSUES, "Exception type", origin="decided"),
        enum("severity", E.SEVERITIES, "Severity from the routing matrix", origin="derived",
             derivation="routing.types.<exception_type>.severity"),
        flag("blocking", "Blocks approval and payment", origin="derived", derivation="routing matrix"),
        flag("is_primary", "Chosen as the invoice's primary issue", origin="decided", rule="PRI-01"),
        text("rule_id", "Rule that raised it", origin="decided"),
        text("policy_version", "Policy version", fk="policy_version.policy_version"),
        text("expected_value", "What the rule expected", required=False, origin="decided"),
        text("actual_value", "What the document showed", required=False, origin="decided"),
        text("variance", "Difference (amount, quantity or percent)", required=False, origin="derived",
             derivation="actual - expected, in the unit of the check"),
        text("tolerance", "Tolerance applied", required=False, origin="derived",
             derivation="policy value used by rule_id"),
        ref("related_invoice_id", "captured_invoice.invoice_id", "Original invoice for duplicates",
            "invoice_id", required=False),
        enum("assigned_role", E.HUMAN_ROLES, "Actor role the exception is routed to", origin="derived",
             derivation="routing matrix RTE-01"),
        ref("assigned_user_id", "app_user.user_id", "Assignee inside the role", "user_id",
            origin="decided", rule="[assignment] rules"),
        enum("queue", E.QUEUES[:-1], "Work queue", origin="derived", derivation="routing matrix"),
        ts("created_at", "Raised at", origin="decided",
           rule=">= captured_invoice.captured_at and <= as_of_date"),
        day("sla_due_date", "Created date + SLA business days", origin="derived", rule="SLA-01"),
        enum("status_as_of", E.EXCEPTION_STATUSES, "Status at the as-of date", origin="derived",
             derivation="last EXCEPTION ap_event"),
        text("resolution_code", "Why it was closed", required=False, required_when="status_as_of = CLOSED"),
        flag("is_overdue_as_of", "Open past its SLA at the as-of date", origin="derived",
             derivation="status_as_of = OPEN and sla_due_date < as_of_date"),
    ))

APPROVAL = Table(
    "approval", "processed", "engine",
    "Approval requests and decisions per level, created only for eligible invoices.",
    "one row per (invoice, approval level)", ("approval_id",), (
        pk("approval_id", "approval_id", "APR-2026-000001"),
        ref("invoice_id", "captured_invoice.invoice_id", "Invoice", "invoice_id",
            rule="invoice had no open blocking exception when approvals were requested"),
        enum("level", E.APPROVAL_LEVELS, "Approval level"),
        ordinal("sequence", "Order within the invoice's chain", min_value="1", origin="assigned"),
        text("approval_band", "Band from the approval matrix", origin="derived", rule="APR-01"),
        enum("approver_role", ("SYSTEM", "BUSINESS_REQUESTER", "APPROVER"), "Role of the approver",
             origin="derived", derivation="approval.levels.<level>.role"),
        ref("approver_user_id", "app_user.user_id", "Approver", "user_id", origin="decided"),
        ts("requested_at", "Request time", origin="decided",
           rule="previous level's decided_at when sequential"),
        ts("decided_at", "Decision time", required=False, required_when="status_as_of != PENDING",
           origin="decided", rule="APR-SIM-01: requested_at + turnaround business days"),
        enum("status_as_of", E.APPROVAL_STATUSES, "Status at the as-of date", origin="derived",
             derivation="last APPROVAL ap_event"),
        text("rule_id", "Band rule ID", origin="decided"),
        text("policy_version", "Policy version", fk="policy_version.policy_version"),
    ), entity="Approval", unique_together=(("invoice_id", "level"), ("invoice_id", "sequence")))

PAYMENT = Table(
    "payment", "processed", "engine",
    "Payment records, created only for payment-ready invoices (no open blocking exception, every "
    "approval level approved, vendor payable).",
    "one row per payment-ready invoice", ("payment_id",), (
        pk("payment_id", "payment_id", "PAY-2026-000001"),
        ref("invoice_id", "captured_invoice.invoice_id", "Invoice", "invoice_id", unique=True),
        ref("vendor_id", "vendor.vendor_id", "Payee", "vendor_id", rule="equals the invoice vendor"),
        money("amount", "Amount to pay", min_value="0.01", origin="derived",
              derivation="captured_invoice.header_gross_amount"),
        enum("currency", ("INR",), "Currency"),
        enum("payment_method", E.PAYMENT_METHODS, "RTGS at or above 2 lakh, else NEFT",
             origin="derived", rule="PAY-04"),
        day("due_date", "invoice_date + payment-term days", origin="derived", rule="PAY-02"),
        day("scheduled_date", "Due date on a business day, not before the next business day after ready",
            origin="derived", rule="PAY-02"),
        ts("created_at", "Payment-ready time", origin="decided", rule="PAY-01"),
        ts("paid_at", "Release time in the payment run", required=False,
           required_when="status_as_of = PAID", origin="decided", rule="PAY-05"),
        enum("status_as_of", E.PAYMENT_STATUSES, "Status at the as-of date", origin="derived",
             derivation="last PAYMENT ap_event"),
        flag("due_date_passed", "Ready after the due date (PAY-06 warning)", origin="derived",
             derivation="created_at date > due_date"),
        text("policy_version", "Policy version", fk="policy_version.policy_version"),
    ), entity="Payment")

AP_EVENT = Table(
    "ap_event", "processed", "engine",
    "Append-only lifecycle events for invoices, exceptions, approvals and payments. Current status of "
    "every entity equals its last event; every transition is checked against docs/schema.md.",
    "one row per state change", ("event_id",), (
        pk("event_id", "ap_event_id", "EVT-2026-000001"),
        enum("entity_type", ("INVOICE", "EXCEPTION", "APPROVAL", "PAYMENT"), "Entity type"),
        text("entity_id", "invoice_id, exception_id, approval_id or payment_id",
             rule="exists in the table named by entity_type"),
        ref("invoice_id", "captured_invoice.invoice_id", "Invoice the event belongs to", "invoice_id"),
        ordinal("seq", "1-based sequence per entity", min_value="1", origin="assigned"),
        enum("from_status", E.INVOICE_STATUSES + E.EXCEPTION_STATUSES + E.APPROVAL_STATUSES
             + E.PAYMENT_STATUSES, "Status before (empty on creation)", required=False,
             required_when="seq > 1"),
        enum("to_status", E.INVOICE_STATUSES + E.EXCEPTION_STATUSES + E.APPROVAL_STATUSES
             + E.PAYMENT_STATUSES, "Status after", rule="allowed by the entity's state machine"),
        ts("event_at", "When it happened", rule="non-decreasing per entity"),
        enum("actor_role", E.ACTOR_ROLES, "Role that caused the change"),
        ref("actor_id", "app_user.user_id", "User that caused the change", "user_id"),
        text("rule_id", "Rule behind the change", required=False),
        text("reason", "Short reason", required=False),
        text("policy_version", "Policy version", fk="policy_version.policy_version"),
    ), unique_together=(("entity_type", "entity_id", "seq"),))

POLICY_VERSION = Table(
    "policy_version", "processed", "engine", "The policy file every decision references.",
    "one row per policy version used", ("policy_version",), (
        text("policy_version", "Semantic version from [policy].version", unique=True,
             pattern=r"^\d+\.\d+\.\d+$"),
        text("policy_id", "Policy identifier"),
        day("effective_from", "Effective date", rule="<= as_of_date"),
        day("as_of_date", "Fixed as-of date", rule=">= effective_from; no completed event after it"),
        text("sha256", "SHA-256 of config/ap_policy.toml", pattern=r"^[0-9a-f]{64}$", origin="derived",
             derivation="sha256(policy file bytes)"),
    ))

PROCESSED_TABLES = (CAPTURED_INVOICE, CAPTURED_INVOICE_LINE, EXTRACTION_FIELD, INVOICE_DECISION,
                    MATCH_RESULT, MATCH_ALLOCATION, DUPLICATE_PAIR, AP_EXCEPTION, APPROVAL, PAYMENT,
                    AP_EVENT, POLICY_VERSION)
