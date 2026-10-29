# Business rules and policy

All parameters live in the versioned policy file [`config/ap_policy.toml`](../config/ap_policy.toml)
(policy `AP-POLICY`, version `1.0.0`, effective 2026-01-01). The oracle (ground truth) and the
engine implement these rules independently and read their parameters from that one file.
Every decision records the policy version and the rule IDs below, so it can be traced to the
exact rule text. The routing and approval tables in this page are generated from the TOML.

## 1. Conventions

| Topic | Rule | Why |
|---|---|---|
| Money | `Decimal`, quantised to 0.01 with ROUND_HALF_UP; one currency (INR) | Exact and reproducible; no float drift in totals. |
| Line extension | `line net = round_half_up(qty x unit price, 2)` | Standard invoice arithmetic. |
| Tax | Per line: `tax = round_half_up(line net x rate / 100, 2)`, then summed | Line-level tax lets a single wrong line be identified. |
| Header totals | header net = sum(line net), header tax = sum(line tax), gross = net + tax | Invoice totals are derived from lines (assignment rule 3). |
| Quantities | Quantised to the precision of the unit of measure (EA/BOX/PACK/SET/JOB/MONTH 0 dp, HR 1 dp, KG/L/M 2 dp) | "Quantities follow their unit of measure". |
| Percentages | Exact Decimal; tolerance tests never round: `abs(actual - ref) x 100 <= abs(ref) x tol%` | Boundaries behave exactly as documented. |
| Dates | Business days skip Sat/Sun and the four policy holidays; timestamps are IST | SLA, approval and payment arithmetic. |
| Tax codes | GST0 (0%, zero-rated), GST5, GST18, EXEMPT (0%); GST12 retired 2025-09-21 | A simplified synthetic GST-style model. There is no CGST/SGST/IGST split and it is not tax advice (ADR-013). |

## 2. Rule catalogue

The engine evaluates the rules in this order for each invoice, in intake order. A **gate** stops
later checks for that invoice. All other checks are collected, so every issue is recorded.

| Rule | Check | Exception when it fails | Notes |
|---|---|---|---|
| CAP-01 | Every required field is extracted with confidence >= 0.90 | `EXT_LOW_CONFIDENCE` (**gate**) | Values that cannot be trusted are not checked further. The extractor never corrects printed values. |
| VEN-01 | Printed tax registration number resolves to a vendor | `VENDOR_NOT_FOUND` (**gate**) | The **only** source of `captured_invoice.vendor_id`: never the sender, never an ID (ADR-037). |
| ID-01 | Assign `invoice_id = INV-<VEN-01 vendor>-2026-<intake_seq>` (`VND-00000` when unresolved) | - | The invoice ID is an output of vendor resolution, never an input. It equals the source ID exactly when VEN-01 was right. |
| DUP-01 | No earlier document with the same vendor, normalised number, invoice date and gross | `DUPLICATE_EXACT` -> **REJECTED** (**gate**) | "Same invoice submitted twice". |
| DUP-02 | No earlier document with the same vendor and normalised number (different content) | `DUPLICATE_NUMBER_REUSE` -> HOLD (**gate**) | "Duplicate invoice number". |
| DUP-03 | No earlier document with the same vendor, invoice date, gross and PO under a different number | `DUPLICATE_SUSPECTED` -> HOLD (**gate**) | Catches a resubmission whose number was altered. |
| VEN-04 | On PORTAL and EDI, the authenticated sender vendor equals the VEN-01 vendor | `VENDOR_SENDER_MISMATCH` | Flags a possible impersonation or misdirected upload. EMAIL senders are not authenticated (forwarding is common) and SCAN has no sender, so they are not compared. |
| VEN-02 | Vendor status on the invoice date is not CLOSED | `VENDOR_CLOSED` | Status is read from the effective-dated history, never from the `snapshot_status` column. |
| VEN-03 | Vendor status on the invoice date is not BLOCKED | `VENDOR_BLOCKED` | |
| PO-01 | The printed PO number exists | `PO_NOT_FOUND` | Line matching is skipped. |
| PO-02 | The PO belongs to the invoice's vendor | `VENDOR_PO_MISMATCH` | Line matching is skipped (matching against a foreign PO would produce noise). |
| DATE-01 | invoice date <= received date | `INVOICE_DATE_IN_FUTURE` | |
| DATE-02 | invoice date >= PO date | `INVOICE_BEFORE_PO` | Retrospective PO: a policy exception for the process owner. |
| ARI-01 | abs(printed line amount - round(qty x price)) <= 0.01 on every line | `LINE_AMOUNT_MISMATCH` | |
| ARI-02 | header net, tax and gross each within 0.01 of the line sums | `HEADER_TOTAL_MISMATCH` | "Invoice total differs from line sum". |
| TAX-01 | Each printed tax code is valid on the invoice date | `TAX_CODE_INVALID` | |
| TAX-02 | Each printed tax code equals the PO line's tax code (PO invoices) | `TAX_CODE_MISMATCH` | |
| TAX-03 | abs(printed tax - round(printed net x rate)) <= 0.01 on every line | `TAX_AMOUNT_MISMATCH` | |
| PO-03 | Each invoice line maps to a PO line (printed PO line number, else SKU) | `PO_LINE_UNMATCHED` | |
| MAT-01 | Cumulative received for the PO line is > 0 at processing time | `MISSING_RECEIPT` | Only receipts posted before the invoice is processed count. |
| MAT-04 | prior invoiced + this quantity <= ordered x (1 + 5%) | `QTY_EXCEEDS_PO` | "Invoice exceeds PO quantity". |
| MAT-03 | prior invoiced + this quantity <= cumulative received at processing time | `QTY_EXCEEDS_RECEIVED` | Also catches partial deliveries billed in full. |
| MAT-02 | abs(invoice unit price - PO unit price) <= PO unit price x 2% (inclusive) | `PRICE_VARIANCE` | Symmetric: under-billing usually means a wrong PO price or a missing line. |
| MS-01 | Match status derivation (section 4) | - | |
| PRI-01 | Primary status precedence (section 5) | - | |
| RTE-01 / SLA-01 | Route every exception by the routing matrix; due = created + SLA business days | - | Section 6. |
| APR-01 | Approval chain from the amount band (eligible invoices only) | - | Section 7. |
| APR-SIM-01 | Simulated approvers approve after the level's fixed turnaround | - | Deterministic stand-in for human approvers (ADR-011). |
| PAY-01 | Payment-ready: no open blocking exception, all levels approved, vendor payable | - | Section 8. |
| PAY-02 | Schedule on the due date (previous business day if needed), never before the next business day after ready | - | |
| PAY-03 | Vendor status on the ready date is ACTIVE | `VENDOR_NOT_PAYABLE` | |
| PAY-04 | RTGS when amount >= 2,00,000.00, else NEFT | - | Mirrors the RTGS minimum. |
| PAY-05 | Payment run releases SCHEDULED payments whose scheduled date <= as-of | - | Payment execution is simulated, with no bank integration. |
| PAY-06 | Ready after the due date: pay next business day and warn | `PAYMENT_DUE_DATE_PASSED` (non-blocking) | |

Cumulative quantities are per PO line. "Prior invoiced" is the sum of quantities on earlier
non-duplicate invoices, in intake order, that billed the same PO line. That includes invoices
currently on hold, because they are claims against the receipt. Duplicate documents never consume
quantity (`duplicates_consume_receipts = false`). Over-receipt is allowed only up to the same 5%,
so a receipt beyond 5% that is billed in full raises `QTY_EXCEEDS_PO`.

## 3. Tolerances and why these values

| Parameter | Value | Justification |
|---|---|---|
| `matching.price_tolerance_pct` | 2.00 (inclusive, symmetric) | Typical AP tolerances are 1-5%. 2% absorbs rounding and small list-price drift but catches real overbilling. Inclusive means exactly +2.00% passes and +2.00% plus one cent fails. The data includes all three boundary cases. |
| `matching.over_receipt_tolerance_pct` | 5.00 | Bulk goods (packaging, raw materials) ship approximately; ERP over-delivery tolerances are commonly 0-10%. |
| `tax.amount_abs` | 0.01 | Only a per-line rounding difference is acceptable; 0.02 is already an error. |
| `arithmetic.*_abs` | 0.01 | Same reasoning for line extensions and header totals. |
| `extraction.min_field_confidence` | 0.90 | Clean structured reads and known label synonyms score >= 0.95. Any OCR repair or heuristic fallback scores <= 0.80 and is routed to a human (calibrated in Stage 3). |
| Auto-approval limit (P1) | 2,00,000.00 | The PO already authorised the spend, and a clean three-way match proves receipt and price. Larger amounts keep a human in the loop. The limit equals the RTGS threshold. |

## 4. Match status (MS-01)

Line level: price status (EXACT / WITHIN_TOLERANCE / OUT_OF_TOLERANCE), quantity status
(OK / NO_RECEIPT / EXCEEDS_PO / EXCEEDS_RECEIVED) and tax status (OK / WITHIN_ROUNDING /
CODE_MISMATCH / AMOUNT_MISMATCH). Invoice level:

| Condition | `match_status` |
|---|---|
| Non-PO invoice | `NOT_APPLICABLE` |
| A gate stopped processing, or the PO is missing or foreign | `NOT_EVALUATED` |
| Any line with a tax code or tax amount failure | `TAX_MISMATCH` |
| else any line without receipt | `MISSING_RECEIPT` |
| else any line exceeding received or PO quantity | `QTY_MISMATCH` |
| else any line price out of tolerance | `PRICE_VARIANCE` |
| else every line exact (price equal, tax exact, quantity within received) | `MATCHED` |
| else (some variance inside tolerance) | `MATCHED_WITHIN_TOLERANCE` |

The precedence among mismatch statuses (`matching.match_status_precedence`) follows the issue
precedence below.

## 5. Primary status precedence (PRI-01)

An invoice can carry several issues, for example a quantity above both the receipt and the PO
tolerance. All of them are recorded as exceptions and routed. The **primary issue** is the
highest-ranked blocking issue in the routing table below, and it decides the invoice's headline
status and queue. The order follows the questions an AP team asks:

1. Can we trust the data? (capture)
2. Are we about to pay twice? (duplicates)
3. Is the vendor legitimate and payable? (vendor)
4. Is the PO reference valid? (PO)
5. Does the invoice follow policy? (dates)
6. Is the document internally consistent? (arithmetic, tax)
7. Does it match what was ordered and received? (receipt, quantity, price)

An invoice with no blocking issue has primary issue `NONE` and enters approval.

## 6. Routing matrix (RTE-01)

<!-- BEGIN GENERATED: routing-matrix (python -m invoice_ap docs) -->
| Precedence | Exception type | Raised by | Severity | Blocking | Actor role | Queue | SLA (business days) |
|---|---|---|---|---|---|---|---|
| 1 | `EXT_LOW_CONFIDENCE` | CAP-01 | MEDIUM | yes | OPERATIONS_ANALYST | AP_CAPTURE_REVIEW | 1 |
| 2 | `DUPLICATE_EXACT` | DUP-01 | HIGH | yes | OPERATIONS_ANALYST | AP_DUPLICATES | 2 |
| 3 | `DUPLICATE_NUMBER_REUSE` | DUP-02 | HIGH | yes | OPERATIONS_ANALYST | AP_DUPLICATES | 2 |
| 4 | `DUPLICATE_SUSPECTED` | DUP-03 | HIGH | yes | OPERATIONS_ANALYST | AP_DUPLICATES | 2 |
| 5 | `VENDOR_NOT_FOUND` | VEN-01 | HIGH | yes | SYSTEM_ADMINISTRATOR | VENDOR_MASTER | 3 |
| 6 | `VENDOR_SENDER_MISMATCH` | VEN-04 | HIGH | yes | OPERATIONS_ANALYST | AP_VALIDATION | 2 |
| 7 | `VENDOR_CLOSED` | VEN-02 | HIGH | yes | SYSTEM_ADMINISTRATOR | VENDOR_MASTER | 3 |
| 8 | `VENDOR_BLOCKED` | VEN-03 | HIGH | yes | SYSTEM_ADMINISTRATOR | VENDOR_MASTER | 3 |
| 9 | `PO_NOT_FOUND` | PO-01 | HIGH | yes | OPERATIONS_ANALYST | AP_VALIDATION | 2 |
| 10 | `VENDOR_PO_MISMATCH` | PO-02 | HIGH | yes | OPERATIONS_ANALYST | AP_VALIDATION | 2 |
| 11 | `INVOICE_DATE_IN_FUTURE` | DATE-01 | MEDIUM | yes | OPERATIONS_ANALYST | AP_VALIDATION | 2 |
| 12 | `INVOICE_BEFORE_PO` | DATE-02 | MEDIUM | yes | PROCESS_OWNER | POLICY_EXCEPTIONS | 3 |
| 13 | `HEADER_TOTAL_MISMATCH` | ARI-02 | HIGH | yes | OPERATIONS_ANALYST | AP_VALIDATION | 2 |
| 14 | `LINE_AMOUNT_MISMATCH` | ARI-01 | HIGH | yes | OPERATIONS_ANALYST | AP_VALIDATION | 2 |
| 15 | `TAX_CODE_INVALID` | TAX-01 | HIGH | yes | OPERATIONS_ANALYST | AP_TAX | 2 |
| 16 | `TAX_CODE_MISMATCH` | TAX-02 | HIGH | yes | OPERATIONS_ANALYST | AP_TAX | 2 |
| 17 | `TAX_AMOUNT_MISMATCH` | TAX-03 | MEDIUM | yes | OPERATIONS_ANALYST | AP_TAX | 2 |
| 18 | `PO_LINE_UNMATCHED` | PO-03 | MEDIUM | yes | BUSINESS_REQUESTER | PO_QUERIES | 3 |
| 19 | `MISSING_RECEIPT` | MAT-01 | MEDIUM | yes | BUSINESS_REQUESTER | RECEIPT_CONFIRMATION | 3 |
| 20 | `QTY_EXCEEDS_PO` | MAT-04 | HIGH | yes | PROCESS_OWNER | POLICY_EXCEPTIONS | 3 |
| 21 | `QTY_EXCEEDS_RECEIVED` | MAT-03 | MEDIUM | yes | BUSINESS_REQUESTER | RECEIPT_CONFIRMATION | 3 |
| 22 | `PRICE_VARIANCE` | MAT-02 | MEDIUM | yes | BUSINESS_REQUESTER | PRICE_REVIEW | 3 |
| 23 | `VENDOR_NOT_PAYABLE` | PAY-03 | HIGH | yes | SYSTEM_ADMINISTRATOR | VENDOR_MASTER | 2 |
| 24 | `PAYMENT_DUE_DATE_PASSED` | PAY-06 | LOW | no | OPERATIONS_ANALYST | PAYMENT_WATCH | 1 |
<!-- END GENERATED: routing-matrix -->

Assignment within a role is deterministic:
- business requester: the PO's requester, else the invoice's attention user;
- process owner: the policy owner;
- operations analyst: round-robin in exception-id order;
- system administrator: the vendor-master owner.

SLA rationale: capture review takes one business day (quick, AP-internal); other AP-internal checks
take two; items that need someone outside AP (requester, process owner, vendor master) take three.
An open exception past its SLA date at the as-of date is reported as overdue.

## 7. Approval matrix (APR-01)

<!-- BEGIN GENERATED: approval-matrix (python -m invoice_ap docs) -->
| Rule | Path | Band | Gross amount (INR) | Levels in order | Approver roles |
|---|---|---|---|---|---|
| APR-PO-01 | PO | P1 | > 0.00 and <= 200000.00 | AUTO | AUTO: SYSTEM (SYSTEM_USER) |
| APR-PO-02 | PO | P2 | > 200000.00 and <= 1000000.00 | L1 | L1: APPROVER (COST_CENTER_MANAGER) |
| APR-PO-03 | PO | P3 | > 1000000.00 and <= 5000000.00 | L1 -> L2 | L1: APPROVER (COST_CENTER_MANAGER), L2: APPROVER (FINANCE_CONTROLLER) |
| APR-PO-04 | PO | P4 | > 5000000.00 | L1 -> L2 -> L3 | L1: APPROVER (COST_CENTER_MANAGER), L2: APPROVER (FINANCE_CONTROLLER), L3: APPROVER (CHIEF_FINANCIAL_OFFICER) |
| APR-NPO-01 | NON_PO | N1 | > 0.00 and <= 50000.00 | REQ | REQ: BUSINESS_REQUESTER (INVOICE_ATTENTION_REQUESTER) |
| APR-NPO-02 | NON_PO | N2 | > 50000.00 and <= 500000.00 | REQ -> L1 | REQ: BUSINESS_REQUESTER (INVOICE_ATTENTION_REQUESTER), L1: APPROVER (COST_CENTER_MANAGER) |
| APR-NPO-03 | NON_PO | N3 | > 500000.00 | REQ -> L1 -> L2 | REQ: BUSINESS_REQUESTER (INVOICE_ATTENTION_REQUESTER), L1: APPROVER (COST_CENTER_MANAGER), L2: APPROVER (FINANCE_CONTROLLER) |

| Level | Role | Assignee rule | Simulated turnaround (business days) |
|---|---|---|---|
| AUTO | SYSTEM | SYSTEM_USER | 0 |
| REQ | BUSINESS_REQUESTER | INVOICE_ATTENTION_REQUESTER | 1 |
| L1 | APPROVER | COST_CENTER_MANAGER | 1 |
| L2 | APPROVER | FINANCE_CONTROLLER | 2 |
| L3 | APPROVER | CHIEF_FINANCIAL_OFFICER | 2 |
<!-- END GENERATED: approval-matrix -->

Eligibility: approvals are created only when an invoice has no open blocking exception after
validation and matching. Levels are sequential: level n+1 is requested when level n approves.
The basis is the captured header gross amount. Non-PO invoices always start with the requester
named on the invoice, because no PO pre-authorised the spend ("then requester approval"). The
simulated approvers approve after the turnaround shown. A level that is still undecided at the
as-of date stays PENDING, and so the invoice is not payment-ready. Rejection exists in the state
machine, but no policy rule triggers it, so the simulation never produces it (ADR-011).

## 8. Payment readiness and scheduling (PAY-01 to PAY-06)

An invoice is **payment-ready** only when all three conditions hold:
1. no open blocking exception;
2. every required approval level is APPROVED;
3. the vendor is ACTIVE on the ready date.

Then exactly one payment record is created:
- `due_date = invoice_date + term days`;
- `scheduled_date` = the due date, moved to the previous business day if needed, and never earlier
  than the next business day after ready (if the due date has already passed, the payment goes on
  the next business day and `PAYMENT_DUE_DATE_PASSED` is raised as a non-blocking warning);
- method RTGS at or above 2,00,000.00, else NEFT;
- the payment run marks a payment PAID on its scheduled date when that date is on or before the
  as-of date.

**Safety invariant (acceptance criterion R34e):** no invoice with an open blocking exception, a
pending approval or a non-payable vendor ever has a payment record. The evaluation checks this for
every invoice.

## 9. Duplicate normalisation (DUP-01 to DUP-03)

The invoice number is uppercased and split on every non-alphanumeric character. Leading zeros are
stripped from each numeric token and the tokens are joined. Examples:

| Printed | Normalised |
|---|---|
| `INV/2026/0042`, `inv-2026-42`, `INV 2026 042` | `INV202642` |
| `SI/26-27/0107` | `SI2627107` |

Rules DUP-01 to DUP-03 compare each document with **every earlier document** (lookback = all prior,
in intake order). The pair (duplicate -> original) points to the earliest matching original. Two
recurring monthly invoices with the same amount but different numbers and dates are **not**
duplicates. Two invoices with the same vendor, date and amount on different POs are not duplicates
either. Both true negatives are in the data.

## 10. The five actors

| Actor | Responsibilities in this build | Queues and records |
|---|---|---|
| Business requester | Raises POs, confirms goods receipts, answers price, receipt and quantity questions, approves non-PO invoices (REQ) | PRICE_REVIEW, RECEIPT_CONFIRMATION, PO_QUERIES; `purchase_order.requester_id`, `goods_receipt.received_by` |
| Process owner | Owns this policy; decides policy exceptions (invoice before PO, PO quantity overrun) | POLICY_EXCEPTIONS; `[policy] owner_role` |
| Approver | Approves by level and amount band (L1 cost-centre manager, L2 finance controller, L3 CFO) | APPROVALS; `approval` rows |
| Operations analyst | Runs the AP queue: capture review, duplicates, header and tax validation, payment watch | AP_CAPTURE_REVIEW, AP_DUPLICATES, AP_VALIDATION, AP_TAX, PAYMENT_WATCH |
| System administrator | Maintains the vendor master and status history, the policy file and the runs; keeps the audit trail | VENDOR_MASTER; `vendor.created_by`, `vendor_status_history.actor_id`, `[policy] maintainer_role` |

The SYSTEM actor (`USR-0001`, the engine) records automated steps such as capture, matching,
auto-approval and scheduling, so a human action is never confused with an automated one.
