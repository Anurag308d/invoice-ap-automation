"""Inbox (engine-readable), source and ground-truth (evaluation-only) layers."""
from __future__ import annotations

from ..common import enums as E
from ..common.enums import SCENARIO_CODES
from .model import Table, day, dec, enum, flag, integer, lst, money, ordinal, pct, pk, qty, ref, text, ts

TAX_CODES = ("GST0", "GST5", "GST12", "GST18", "EXEMPT")

INTAKE_MANIFEST = Table(
    "intake_manifest", "inbox", "generator",
    "Register of every received invoice document. Carries no labels, no scenario information and no "
    "invoice_id: the invoice ID embeds the vendor, so the engine assigns it only after resolving the "
    "vendor from the document (ID-01, ADR-037).",
    "one row per received document", ("doc_id",), (
        pk("doc_id", "doc_id", "Document identifier DOC-2026-000001, in intake order",
           rule="unique; DOC-2026-<intake_seq>"),
        ordinal("intake_seq", "Global intake sequence; also the 6-digit counter of the invoice ID",
                unique=True, origin="assigned", max_value="999999",
                rule="1..N without gaps, in received_at order"),
        enum("channel", E.CHANNELS, "Intake channel"),
        enum("file_format", tuple(E.FILE_FORMATS.values()), "Document format of the channel",
             origin="derived", derivation="enums.FILE_FORMATS[channel]"),
        ts("received_at", "Arrival timestamp", rule="strictly increasing in doc_id order"),
        text("sender_address", "Channel sender: portal account, EDI partner ID, e-mail From address "
             "or mailroom batch ID",
             rule="EMAIL: may be a forwarding mailbox rather than the vendor's remit address; SCAN: "
                  "batch ID only; the engine never resolves the vendor from it (ADR-037)"),
        ref("sender_vendor_id", "vendor.vendor_id", "Vendor authenticated by the channel", "vendor_id",
            required=False, required_when="channel in (PORTAL, EDI)",
            rule="empty for EMAIL and SCAN; used only by the VEN-04 cross-check, never as the vendor"),
        text("file_path", "Document path relative to the inbox folder", unique=True),
        text("file_sha256", "SHA-256 of the document bytes", pattern=r"^[0-9a-f]{64}$",
             origin="derived", derivation="sha256(file bytes)"),
        integer("file_bytes", "Document size", unit="bytes", min_value="1", origin="derived",
                derivation="len(file bytes)"),
    ))

INVOICE = Table(
    "invoice", "source", "generator",
    "The true invoice as the vendor issued it (what is printed on the document). Evaluation-only: "
    "the engine never reads it; it is the extraction ground truth.",
    "one row per received invoice document (resubmissions are separate rows)", ("invoice_id",), (
        pk("invoice_id", "invoice_id", "Invoice identifier INV-<vendor_id>-2026-000001",
           rule="INV-<true vendor_id>-2026-<intake_seq of doc_id>; unique, immutable"),
        ref("doc_id", "intake_manifest.doc_id", "Rendered document", "doc_id", unique=True),
        ref("vendor_id", "vendor.vendor_id", "Issuing vendor", "vendor_id",
            rule="equals the vendor code embedded in invoice_id"),
        text("vendor_invoice_number", "Vendor's own invoice number as printed",
             rule="(vendor, normalised number) unique except labelled duplicate documents"),
        day("invoice_date", "Invoice date as printed",
            rule="<= received date; >= po_date except labelled INVOICE_BEFORE_PO"),
        ref("po_id", "purchase_order.po_id", "PO quoted on the invoice (empty = non-PO)", "po_id",
            required=False, required_when="the invoice is PO-backed",
            rule="PO vendor = vendor_id except labelled VENDOR_PO_MISMATCH"),
        ref("attention_user_id", "app_user.user_id", "Requester named on a non-PO invoice",
            "user_id", required=False, required_when="po_id is empty"),
        enum("currency", ("INR",), "Currency"),
        money("header_net_amount", "Printed net total"),
        money("header_tax_amount", "Printed tax total"),
        money("header_gross_amount", "Printed invoice total",
              rule="= lines_gross_amount except labelled HEADER_TOTAL_MISMATCH"),
        money("lines_net_amount", "Sum of printed line net amounts", origin="derived",
              derivation="sum(invoice_line.line_net_amount)"),
        money("lines_tax_amount", "Sum of printed line tax amounts", origin="derived",
              derivation="sum(invoice_line.tax_amount)"),
        money("lines_gross_amount", "Lines net plus lines tax", origin="derived",
              derivation="lines_net_amount + lines_tax_amount"),
        integer("line_count", "Number of invoice lines", min_value="1", origin="derived",
                derivation="count(invoice_line)"),
        flag("is_po_backed", "True when a PO is quoted", origin="derived", derivation="po_id is not empty"),
    ), entity="Invoice")

INVOICE_LINE = Table(
    "invoice_line", "source", "generator",
    "True invoice lines as printed. Evaluation-only.",
    "one row per printed invoice line", ("invoice_line_id",), (
        pk("invoice_line_id", "invoice_line_id", "Line identifier INVL-<invoice_id>-01"),
        ref("invoice_id", "invoice.invoice_id", "Parent invoice", "invoice_id"),
        ordinal("line_number", "1-based line number", min_value="1", origin="assigned"),
        ref("po_line_id", "purchase_order_line.po_line_id", "PO line billed", "po_line_id",
            required=False, required_when="the invoice is PO-backed",
            rule="belongs to the invoice's PO"),
        ref("sku_id", "sku.sku_id", "SKU billed (empty for service lines)", "sku_id", required=False,
            required_when="po_line_id is not empty"),
        text("description", "Line description as printed"),
        enum("uom", E.UOMS, "Unit of measure"),
        qty("quantity", "Billed quantity", min_value="0.01"),
        money("unit_price", "Billed unit price", min_value="0.01"),
        money("line_net_amount", "Printed line amount",
              rule="= expected_line_net_amount except labelled LINE_AMOUNT_MISMATCH"),
        ref("tax_code", "tax_code.tax_code", "Printed tax code", type="enum", allowed=TAX_CODES,
            rule="= PO line tax code except labelled TAX_CODE_MISMATCH"),
        pct("tax_rate_pct", "Rate of the printed tax code", origin="derived", derivation="tax_code.rate_pct"),
        money("tax_amount", "Printed tax amount",
              rule="within 0.01 of expected_tax_amount except labelled TAX_AMOUNT_MISMATCH"),
        money("expected_line_net_amount", "Recomputed extension", origin="derived",
              derivation="round_half_up(quantity x unit_price, 2)"),
        money("expected_tax_amount", "Recomputed tax", origin="derived",
              derivation="round_half_up(line_net_amount x tax_rate_pct / 100, 2)"),
        money("line_gross_amount", "Printed net plus printed tax", origin="derived",
              derivation="line_net_amount + tax_amount"),
    ), entity="InvoiceLine", unique_together=(("invoice_id", "line_number"),))

_ISSUES = E.EXCEPTION_TYPES
GROUND_TRUTH = Table(
    "ground_truth", "ground_truth", "oracle",
    "Expected labels and decisions per invoice, derived by the rule-based oracle from the true data "
    "and asserted equal to the generator's injection intent. Never an engine input.",
    "one row per invoice", ("invoice_id",), (
        ref("invoice_id", "invoice.invoice_id", "Invoice", "invoice_id", unique=True),
        ref("doc_id", "intake_manifest.doc_id", "Document", "doc_id", unique=True),
        enum("scenario_category", E.SCENARIO_CATEGORIES, "Primary scenario category (mix table)"),
        enum("scenario_code", SCENARIO_CODES, "Sub-scenario code (docs/data_generation.md Table G6)"),
        lst("edge_case_ids", "Assignment edge cases this invoice demonstrates", tuple(E.EDGE_CASES)),
        flag("is_anomaly", "True when any issue is intended", origin="derived",
             derivation="intended_issue_types is not empty (CLEAN never has issues)"),
        flag("is_po_backed", "PO quoted", origin="derived", derivation="invoice.po_id is not empty"),
        enum("capture_overlay", E.CAPTURE_OVERLAYS, "Document-quality overlay applied when rendering"),
        lst("intended_issue_types", "Labels the generator intended to inject", _ISSUES),
        lst("expected_issue_types", "Labels the oracle derives under the policy", _ISSUES,
            origin="decided", rule="must equal intended_issue_types (generation fails otherwise)"),
        enum("expected_primary_issue", _ISSUES + ("NONE",), "Highest-precedence blocking issue",
             origin="decided", rule="PRI-01"),
        flag("expected_blocked", "At least one blocking issue", origin="decided"),
        enum("expected_match_status", E.MATCH_STATUSES, "Expected invoice match status",
             origin="decided", rule="MS-01"),
        ref("expected_duplicate_of", "invoice.invoice_id", "Original of a duplicate document",
            "invoice_id", required=False, required_when="scenario_category = DUPLICATE", origin="decided"),
        lst("expected_assigned_roles", "Roles that must receive the blocking exceptions",
            E.HUMAN_ROLES, origin="decided", rule="RTE-01"),
        lst("expected_queues", "Queues that must receive the exceptions", E.QUEUES, origin="decided"),
        text("expected_approval_band", "Approval band (empty when not eligible)", required=False,
             origin="decided", rule="APR-01"),
        lst("expected_approval_levels", "Approval levels in order (empty when not eligible)",
            E.APPROVAL_LEVELS, origin="decided"),
        enum("expected_final_status", E.INVOICE_STATUSES, "Invoice status at the as-of date",
             origin="decided"),
        flag("expected_payment_ready", "A payment record must exist", origin="decided", rule="PAY-01"),
        enum("expected_payment_status", E.PAYMENT_STATUSES, "Payment status at the as-of date",
             required=False, required_when="expected_payment_ready", origin="decided"),
        day("expected_due_date", "Due date", required=False, required_when="expected_payment_ready",
            origin="decided", rule="invoice_date + payment-term days (PAY-02); may be after as_of"),
        day("expected_scheduled_date", "Scheduled payment date", required=False,
            required_when="expected_payment_ready", origin="decided", rule="PAY-02"),
        lst("oracle_rule_ids", "Rule IDs that fired in the oracle", origin="decided",
            pattern=r"^(?:[A-Z]{2,4}(?:-[A-Z]{2,4})?-\d{2}(?:\|[A-Z]{2,4}(?:-[A-Z]{2,4})?-\d{2})*)?$", rule="each ID is documented in docs/business_rules.md"),
        text("policy_version", "Policy version used", origin="decided"),
        text("description", "Human-readable description of what was injected"),
    ))

GROUND_TRUTH_LINE = Table(
    "ground_truth_line", "ground_truth", "oracle",
    "Expected line-level match results for every invoice line.",
    "one row per invoice line", ("invoice_line_id",), (
        ref("invoice_line_id", "invoice_line.invoice_line_id", "Invoice line", "invoice_line_id",
            unique=True),
        ref("invoice_id", "invoice.invoice_id", "Invoice", "invoice_id"),
        lst("expected_line_issue_types", "Line-level labels", _ISSUES, origin="decided"),
        enum("expected_price_status", E.LINE_PRICE_STATUSES, "Price check result", origin="decided"),
        enum("expected_qty_status", E.LINE_QTY_STATUSES, "Quantity check result", origin="decided"),
        enum("expected_tax_status", E.LINE_TAX_STATUSES, "Tax check result", origin="decided"),
        qty("expected_received_qty", "Cumulative received at processing time", required=False,
            required_when="line matched", origin="decided"),
        qty("expected_prior_invoiced_qty", "Quantity billed on earlier non-duplicate invoices",
            required=False, required_when="line matched", origin="decided"),
        dec("expected_price_variance_pct", "Signed unit-price variance vs PO", required=False,
            required_when="line matched", unit="%", origin="decided",
            rule="(invoice unit price - PO unit price) / PO unit price x 100, exact"),
    ))

DOCUMENT_TABLES = (INTAKE_MANIFEST, INVOICE, INVOICE_LINE, GROUND_TRUTH, GROUND_TRUTH_LINE)
