"""Controlled vocabularies shared by the spec, the policy validator, the generator and the engine.

Only vocabulary lives here (no business logic and no generator internals), so both sides of the
no-leakage boundary may import it. Every tuple is ordered; code must never rely on set order.
"""
from __future__ import annotations

# --- Actors (assignment: business requester, process owner, approver, operations analyst,
# system administrator). SYSTEM is the automation actor used for engine-made decisions.
HUMAN_ROLES = (
    "BUSINESS_REQUESTER",
    "PROCESS_OWNER",
    "APPROVER",
    "OPERATIONS_ANALYST",
    "SYSTEM_ADMINISTRATOR",
)
ACTOR_ROLES = HUMAN_ROLES + ("SYSTEM",)

COST_CENTERS = ("OPERATIONS", "MANUFACTURING", "IT", "FACILITIES", "LOGISTICS", "CORPORATE")
# Named responsibilities inside a role; config/ap_policy.toml assignment rules refer to these.
RESPONSIBILITIES = (
    "SYSTEM_USER",              # SYSTEM: the automation engine itself
    "VENDOR_MASTER_OWNER",      # SYSTEM_ADMINISTRATOR: vendor master and status changes
    "PLATFORM_ADMIN",           # SYSTEM_ADMINISTRATOR: configuration, runs and audit
    "POLICY_OWNER",             # PROCESS_OWNER
    "AP_ANALYST",               # OPERATIONS_ANALYST
    "REQUESTER",                # BUSINESS_REQUESTER
    "COST_CENTER_MANAGER",      # APPROVER level L1
    "FINANCE_CONTROLLER",       # APPROVER level L2
    "CHIEF_FINANCIAL_OFFICER",  # APPROVER level L3
)
# Work queues. Exceptions are routed to the first ten; APPROVALS holds pending approval requests.
QUEUES = (
    "AP_CAPTURE_REVIEW", "AP_DUPLICATES", "AP_VALIDATION", "AP_TAX", "PAYMENT_WATCH",
    "PO_QUERIES", "RECEIPT_CONFIRMATION", "PRICE_REVIEW", "POLICY_EXCEPTIONS", "VENDOR_MASTER",
    "APPROVALS",
)

# --- Vendor master
VENDOR_STATUSES = ("ACTIVE", "BLOCKED", "CLOSED")
VENDOR_STATUS_REASONS = ("ONBOARDED", "KYC_DOCUMENTS_EXPIRED", "KYC_RENEWED", "RELATIONSHIP_ENDED")
VENDOR_TIERS = ("STRATEGIC", "CORE", "TAIL")
VENDOR_SEGMENTS = ("GOODS", "SERVICES")

# --- Catalogue
GOODS_CATEGORIES = (
    "RAW_MATERIALS",
    "ELECTRICAL",
    "MRO_SPARES",
    "PACKAGING",
    "IT_HARDWARE",
    "OFFICE_SUPPLIES",
    "SAFETY_EQUIPMENT",
    "CANTEEN_SUPPLIES",
)
SERVICE_CATEGORIES = (
    "FACILITY_SERVICES",
    "PROFESSIONAL_SERVICES",
    "IT_SERVICES",
    "LOGISTICS_SERVICES",
)
UOM_DECIMALS = {  # quantity precision per unit of measure
    "EA": 0, "BOX": 0, "PACK": 0, "SET": 0,
    "KG": 2, "L": 2, "M": 2,
    "HR": 1, "MONTH": 0, "JOB": 0,
}
UOMS = tuple(UOM_DECIMALS)

# --- Purchasing and receiving lifecycles (ERP side, written by the generator)
PO_STATUSES = ("ISSUED", "PARTIALLY_RECEIVED", "RECEIVED")
GRN_STATUSES = ("POSTED",)
RECEIPT_TYPES = ("PARTIAL", "FULL", "OVER")
ERP_EVENT_REASONS = ("PO_ISSUED", "GOODS_RECEIVED", "GRN_POSTED")
TAX_CATEGORIES = ("STANDARD", "REDUCED", "ZERO_RATED", "EXEMPT")

# --- Intake and capture
CHANNELS = ("PORTAL", "EDI", "EMAIL", "SCAN")
FILE_FORMATS = {"PORTAL": "PORTAL_JSON", "EDI": "EDI_FLAT", "EMAIL": "EMAIL_TEXT", "SCAN": "OCR_TEXT"}
CAPTURE_STATUSES = ("OK", "LOW_CONFIDENCE")
EXTRACTION_METHODS = ("STRUCTURED", "SEGMENT", "LABEL_EXACT", "LABEL_SYNONYM", "PATTERN",
                      "OCR_REPAIRED", "NOT_FOUND")
DUPLICATE_MATCH_TYPES = ("EXACT", "NUMBER_REUSE", "CONTENT")

# --- AP lifecycles (engine side)
INVOICE_STATUSES = (
    "RECEIVED",
    "CAPTURED",
    "ON_HOLD",
    "REJECTED",
    "PENDING_APPROVAL",
    "APPROVED",
    "PAYMENT_READY",
    "PAID",
)
EXCEPTION_STATUSES = ("OPEN", "CLOSED")
APPROVAL_STATUSES = ("PENDING", "APPROVED", "REJECTED")
APPROVAL_LEVELS = ("AUTO", "REQ", "L1", "L2", "L3")
PAYMENT_STATUSES = ("SCHEDULED", "PAID")
PAYMENT_METHODS = ("NEFT", "RTGS")
SEVERITIES = ("LOW", "MEDIUM", "HIGH", "CRITICAL")

MATCH_STATUSES = (
    "MATCHED",
    "MATCHED_WITHIN_TOLERANCE",
    "PRICE_VARIANCE",
    "QTY_MISMATCH",
    "MISSING_RECEIPT",
    "TAX_MISMATCH",
    "NOT_APPLICABLE",  # non-PO invoice: no three-way match
    "NOT_EVALUATED",   # matching skipped because an earlier gate stopped processing
)
LINE_PRICE_STATUSES = ("EXACT", "WITHIN_TOLERANCE", "OUT_OF_TOLERANCE", "NOT_EVALUATED")
LINE_QTY_STATUSES = ("OK", "EXCEEDS_RECEIVED", "EXCEEDS_PO", "NO_RECEIPT", "NOT_EVALUATED")
LINE_TAX_STATUSES = ("OK", "WITHIN_ROUNDING", "CODE_MISMATCH", "AMOUNT_MISMATCH", "NOT_EVALUATED")

# --- Exception (issue) types. The order below IS the primary-status precedence (highest first);
# config/ap_policy.toml repeats it and tests assert that the two agree.
EXCEPTION_TYPES = (
    "EXT_LOW_CONFIDENCE",
    "DUPLICATE_EXACT",
    "DUPLICATE_NUMBER_REUSE",
    "DUPLICATE_SUSPECTED",
    "VENDOR_NOT_FOUND",
    "VENDOR_SENDER_MISMATCH",
    "VENDOR_CLOSED",
    "VENDOR_BLOCKED",
    "PO_NOT_FOUND",
    "VENDOR_PO_MISMATCH",
    "INVOICE_DATE_IN_FUTURE",
    "INVOICE_BEFORE_PO",
    "HEADER_TOTAL_MISMATCH",
    "LINE_AMOUNT_MISMATCH",
    "TAX_CODE_INVALID",
    "TAX_CODE_MISMATCH",
    "TAX_AMOUNT_MISMATCH",
    "PO_LINE_UNMATCHED",
    "MISSING_RECEIPT",
    "QTY_EXCEEDS_PO",
    "QTY_EXCEEDS_RECEIVED",
    "PRICE_VARIANCE",
    "VENDOR_NOT_PAYABLE",
    "PAYMENT_DUE_DATE_PASSED",
)
NON_BLOCKING_EXCEPTION_TYPES = ("PAYMENT_DUE_DATE_PASSED",)

# --- Events
EVENT_ENTITY_TYPES = (
    "VENDOR",
    "PURCHASE_ORDER",
    "GOODS_RECEIPT",
    "INVOICE",
    "EXCEPTION",
    "APPROVAL",
    "PAYMENT",
)

# --- Ground truth vocabulary (evaluation side only; never written into master or inbox data)
SCENARIO_CATEGORIES = (
    "CLEAN",
    "PRICE_VARIANCE",
    "QTY_MISMATCH",
    "DUPLICATE",
    "MISSING_RECEIPT",
    "TAX_VENDOR",
    "ARITHMETIC",
    "INVOICE_BEFORE_PO",
    "CAPTURE_REVIEW",
)
EDGE_CASES = {  # the eight required edge cases of the assignment (Step 5)
    "EC-01": "Duplicate invoice number",
    "EC-02": "Invoice total differs from line sum",
    "EC-03": "Invoice date before PO date",
    "EC-04": "Partial delivery",
    "EC-05": "Closed vendor",
    "EC-06": "Tax mismatch",
    "EC-07": "Invoice exceeds PO quantity",
    "EC-08": "Same invoice submitted twice",
}
CAPTURE_OVERLAYS = ("NONE", "DEGRADED_SCAN")
# Sub-scenario vocabulary only (names, no counts and no per-invoice labels). The catalogue with
# counts and injection intent lives in invoice_ap/generator/catalogue.py; a test keeps both equal.
SCENARIO_CODES = (
    "C-STD", "C-PARTIAL-OPEN", "C-OVERRECEIPT-WITHIN", "C-QTY-AT-TOL", "C-PRICE-AT-TOL",
    "C-PRICE-INSIDE", "C-PRICE-SMALL-VAR", "C-TAX-ROUNDING", "C-TN-SAME-DAY",
    "C-SPLIT-PARTIAL", "C-SPLIT-FINAL", "C-CONSOLIDATED", "C-PARTIAL-BILLING", "C-NPO-RECURRING",
    "C-NPO-ONEOFF",
    "PV-OVER", "PV-SPLIT-LATER", "PV-UNDER", "PV-BOUNDARY-OUT",
    "QM-PARTIAL-BILLED-FULL", "QM-OVERBILL-RECEIVED", "QM-CUMULATIVE", "QM-EXCEEDS-PO-OVERRECEIPT",
    "QM-EXCEEDS-PO-AND-RECEIVED", "QM-BOUNDARY-OUT",
    "DUP-EXACT", "DUP-EXACT-NORMALIZED", "DUP-EXACT-NPO", "DUP-NUMBER-REUSE", "DUP-CONTENT",
    "MR-NO-GRN",
    "TV-CLOSED", "TV-BLOCKED", "TV-TAX-CODE", "TV-TAX-AMOUNT", "TV-VENDOR-PO", "TV-NPO-TAX-AMOUNT",
    "ARITH-HEADER-TOTAL", "ARITH-LINE-EXTENSION",
    "DATE-INVOICE-BEFORE-PO",
    "CAP-DEGRADED-SCAN",
)
