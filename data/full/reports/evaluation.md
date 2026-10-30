# Decision evaluation (full)

Invoices evaluated: 2000. Definitions are at the end of this page.

## Headline

| KPI | Value |
|---|---|
| STP rate | 46.05% (921 invoices) |
| Exception rate | 32.50% |
| Payment-ready safety (R34e) violations | 0 |
| Per-invoice acceptance (R34a-e) | 2000 pass / 0 fail |
| Value at risk held (INR) | 75412564.65 |
| Blocked value released in error (INR) | 0.00 |
| Cycle days capture -> ready (median / p90) | 0 / 4 |

## Agreement with ground truth (invoice level)

| Item | Agreement |
|---|---|
| invoice_id | 2000/2000 (100.00%) |
| issue_types | 2000/2000 (100.00%) |
| primary_issue | 2000/2000 (100.00%) |
| blocked | 2000/2000 (100.00%) |
| match_status | 2000/2000 (100.00%) |
| duplicate_of | 2000/2000 (100.00%) |
| assigned_roles | 2000/2000 (100.00%) |
| queues | 2000/2000 (100.00%) |
| approval_band | 2000/2000 (100.00%) |
| approval_levels | 2000/2000 (100.00%) |
| final_status | 2000/2000 (100.00%) |
| payment_ready | 2000/2000 (100.00%) |
| payment_status | 2000/2000 (100.00%) |
| due_date | 2000/2000 (100.00%) |
| scheduled_date | 2000/2000 (100.00%) |

## Agreement with ground truth (line level)

| Item | Agreement |
|---|---|
| price_status | 2960/2960 (100.00%) |
| qty_status | 2960/2960 (100.00%) |
| tax_status | 2960/2960 (100.00%) |
| received_qty | 2960/2960 (100.00%) |
| prior_invoiced_qty | 2960/2960 (100.00%) |

## Per exception type (invoice level)

| Type | TP | FP | FN | Precision | Recall | F1 |
|---|---|---|---|---|---|---|
| EXT_LOW_CONFIDENCE | 10 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |
| DUPLICATE_EXACT | 50 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |
| DUPLICATE_NUMBER_REUSE | 35 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |
| DUPLICATE_SUSPECTED | 15 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |
| VENDOR_NOT_FOUND | 0 | 0 | 0 | not present | not present | not present |
| VENDOR_SENDER_MISMATCH | 0 | 0 | 0 | not present | not present | not present |
| VENDOR_CLOSED | 15 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |
| VENDOR_BLOCKED | 5 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |
| PO_NOT_FOUND | 0 | 0 | 0 | not present | not present | not present |
| VENDOR_PO_MISMATCH | 10 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |
| INVOICE_DATE_IN_FUTURE | 0 | 0 | 0 | not present | not present | not present |
| INVOICE_BEFORE_PO | 20 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |
| HEADER_TOTAL_MISMATCH | 15 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |
| LINE_AMOUNT_MISMATCH | 5 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |
| TAX_CODE_INVALID | 0 | 0 | 0 | not present | not present | not present |
| TAX_CODE_MISMATCH | 15 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |
| TAX_AMOUNT_MISMATCH | 15 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |
| PO_LINE_UNMATCHED | 0 | 0 | 0 | not present | not present | not present |
| MISSING_RECEIPT | 80 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |
| QTY_EXCEEDS_PO | 50 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |
| QTY_EXCEEDS_RECEIVED | 130 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |
| PRICE_VARIANCE | 200 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |
| VENDOR_NOT_PAYABLE | 0 | 0 | 0 | not present | not present | not present |
| PAYMENT_DUE_DATE_PASSED | 0 | 0 | 0 | not present | not present | not present |

## Per exception type (line level)

| Type | TP | FP | FN | Precision | Recall | F1 |
|---|---|---|---|---|---|---|
| LINE_AMOUNT_MISMATCH | 5 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |
| TAX_CODE_INVALID | 0 | 0 | 0 | not present | not present | not present |
| TAX_CODE_MISMATCH | 15 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |
| TAX_AMOUNT_MISMATCH | 15 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |
| PO_LINE_UNMATCHED | 0 | 0 | 0 | not present | not present | not present |
| MISSING_RECEIPT | 129 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |
| QTY_EXCEEDS_PO | 50 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |
| QTY_EXCEEDS_RECEIVED | 156 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |
| PRICE_VARIANCE | 200 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |

Not present in this dataset (covered by unit fixtures): VENDOR_NOT_FOUND, VENDOR_SENDER_MISMATCH, PO_NOT_FOUND, INVOICE_DATE_IN_FUTURE, TAX_CODE_INVALID, PO_LINE_UNMATCHED, VENDOR_NOT_PAYABLE, PAYMENT_DUE_DATE_PASSED.

## Primary issue confusion (expected -> engine; off-diagonal 0)

| Expected -> engine | Invoices |
|---|---|
| DUPLICATE_EXACT -> DUPLICATE_EXACT | 50 |
| DUPLICATE_NUMBER_REUSE -> DUPLICATE_NUMBER_REUSE | 35 |
| DUPLICATE_SUSPECTED -> DUPLICATE_SUSPECTED | 15 |
| EXT_LOW_CONFIDENCE -> EXT_LOW_CONFIDENCE | 10 |
| HEADER_TOTAL_MISMATCH -> HEADER_TOTAL_MISMATCH | 15 |
| INVOICE_BEFORE_PO -> INVOICE_BEFORE_PO | 20 |
| LINE_AMOUNT_MISMATCH -> LINE_AMOUNT_MISMATCH | 5 |
| MISSING_RECEIPT -> MISSING_RECEIPT | 80 |
| NONE -> NONE | 1350 |
| PRICE_VARIANCE -> PRICE_VARIANCE | 200 |
| QTY_EXCEEDS_PO -> QTY_EXCEEDS_PO | 50 |
| QTY_EXCEEDS_RECEIVED -> QTY_EXCEEDS_RECEIVED | 110 |
| TAX_AMOUNT_MISMATCH -> TAX_AMOUNT_MISMATCH | 15 |
| TAX_CODE_MISMATCH -> TAX_CODE_MISMATCH | 15 |
| VENDOR_BLOCKED -> VENDOR_BLOCKED | 5 |
| VENDOR_CLOSED -> VENDOR_CLOSED | 15 |
| VENDOR_PO_MISMATCH -> VENDOR_PO_MISMATCH | 10 |

## Final status confusion

| Expected -> engine | Invoices |
|---|---|
| ON_HOLD -> ON_HOLD | 600 |
| PAID -> PAID | 1192 |
| PAYMENT_READY -> PAYMENT_READY | 156 |
| PENDING_APPROVAL -> PENDING_APPROVAL | 2 |
| REJECTED -> REJECTED | 50 |

## Duplicates

| Item | Value |
|---|---|
| Expected pairs | 100 |
| Detected pairs | 100 |
| Correct pairs | 100 |
| Pair precision | 100.00% |
| Pair recall | 100.00% |
| False positives on true negatives | 0 |

Correct by scenario:

| Scenario | Correct / expected |
|---|---|
| DUP-CONTENT | 15/15 |
| DUP-EXACT | 25/25 |
| DUP-EXACT-NORMALIZED | 20/20 |
| DUP-EXACT-NPO | 5/5 |
| DUP-NUMBER-REUSE | 35/35 |

## Approvals

| Item | Value |
|---|---|
| Eligible invoices | 1350 |
| Approvals for blocked invoices | 0 |
| Levels pending at the as-of date | 2 |

Invoices by approval band:

| Band | Invoices |
|---|---|
| N1 | 5 |
| N2 | 86 |
| N3 | 4 |
| P1 | 921 |
| P2 | 283 |
| P3 | 49 |
| P4 | 2 |
| not eligible | 650 |

## Payments

| Item | Value |
|---|---|
| Payment records | 1348 |
| PAID | 1192 |
| SCHEDULED | 156 |
| RTGS | 361 |
| Blocked or unapproved with a payment | 0 |

## Exceptions

Raised, by type:

| Type | Exceptions |
|---|---|
| DUPLICATE_EXACT | 50 |
| DUPLICATE_NUMBER_REUSE | 35 |
| DUPLICATE_SUSPECTED | 15 |
| EXT_LOW_CONFIDENCE | 10 |
| HEADER_TOTAL_MISMATCH | 15 |
| INVOICE_BEFORE_PO | 20 |
| LINE_AMOUNT_MISMATCH | 5 |
| MISSING_RECEIPT | 129 |
| PRICE_VARIANCE | 200 |
| QTY_EXCEEDS_PO | 50 |
| QTY_EXCEEDS_RECEIVED | 156 |
| TAX_AMOUNT_MISMATCH | 15 |
| TAX_CODE_MISMATCH | 15 |
| VENDOR_BLOCKED | 5 |
| VENDOR_CLOSED | 15 |
| VENDOR_PO_MISMATCH | 10 |

Open at the snapshot, by role:

| Role | Open |
|---|---|
| BUSINESS_REQUESTER | 485 |
| OPERATIONS_ANALYST | 120 |
| PROCESS_OWNER | 70 |
| SYSTEM_ADMINISTRATOR | 20 |

Open at the snapshot, by queue:

| Queue | Open |
|---|---|
| AP_CAPTURE_REVIEW | 10 |
| AP_DUPLICATES | 50 |
| AP_TAX | 30 |
| AP_VALIDATION | 30 |
| POLICY_EXCEPTIONS | 70 |
| PRICE_REVIEW | 200 |
| RECEIPT_CONFIRMATION | 285 |
| VENDOR_MASTER | 20 |

## Backlog: open and past SLA at the snapshot (no resolutions simulated)

683 of 695 open exceptions are past their SLA at the snapshot. Age is in business days since the exception was raised.

| Role | <= 5 business days | 6-20 business days | > 20 business days |
|---|---|---|---|
| ALL ROLES | 6 | 58 | 619 |
| BUSINESS_REQUESTER | 5 | 36 | 437 |
| OPERATIONS_ANALYST | 1 | 14 | 103 |
| PROCESS_OWNER | 0 | 7 | 61 |
| SYSTEM_ADMINISTRATOR | 0 | 1 | 18 |

## Value at risk held, by primary issue (INR)

| Primary issue | INR |
|---|---|
| DUPLICATE_EXACT | 9722309.88 |
| DUPLICATE_NUMBER_REUSE | 8107255.62 |
| DUPLICATE_SUSPECTED | 4933267.17 |
| EXT_LOW_CONFIDENCE | 3969023.86 |
| HEADER_TOTAL_MISMATCH | 778384.08 |
| INVOICE_BEFORE_PO | 3418003.90 |
| LINE_AMOUNT_MISMATCH | 20917.97 |
| MISSING_RECEIPT | 22710372.57 |
| PRICE_VARIANCE | 2931472.85 |
| QTY_EXCEEDS_PO | 1300628.81 |
| QTY_EXCEEDS_RECEIVED | 8601218.61 |
| TAX_AMOUNT_MISMATCH | 12837.87 |
| TAX_CODE_MISMATCH | 722692.33 |
| VENDOR_BLOCKED | 1415096.65 |
| VENDOR_CLOSED | 2633514.94 |
| VENDOR_PO_MISMATCH | 4135567.55 |

## Per-invoice acceptance (R34a-e)

2000 of 2000 invoices pass; 10 are flagged for capture review, which is their expected outcome. Full list: `acceptance_per_invoice.csv`.

| Criterion | pass | flagged | fail |
|---|---|---|---|
| r34a_extraction | 1990 | 10 | 0 |
| r34b_arithmetic_tax | 2000 | 0 | 0 |
| r34c_duplicate_pair | 2000 | 0 | 0 |
| r34d_match_and_approval | 2000 | 0 | 0 |
| r34e_no_blocked_payment_ready | 2000 | 0 | 0 |

Deviations:

- none

## Definitions

| Term | Definition |
|---|---|
| STP rate | Invoices that reached PAYMENT_READY or PAID with no exception at all and AUTO approval, divided by all invoices (evaluation_plan E10). |
| Exception rate | Invoices blocked at the snapshot (an open blocking exception, or REJECTED) divided by all invoices. |
| Precision / recall / F1 | Per exception type, over invoices (or lines): TP = expected and raised, FP = raised but not expected, FN = expected but not raised. A type with no expected and no raised instance is 'not present', never 0/0. |
| Agreement | Share of invoices whose engine value equals the ground-truth value exactly (joined on doc_id). |
| Payment-ready safety | Invoices with a payment record and an open blocking exception or an unapproved level (R34e). Must be 0. |
| Value at risk held | Money held back on truly blocked invoices: full gross for duplicate, vendor, PO, date, receipt and capture holds; excess quantity or price difference (with tax) for quantity and price variances; the absolute difference for tax and arithmetic (E11). |
| Per-invoice acceptance | R34a extracted fields equal the source (or the document is flagged for capture review); R34b arithmetic and tax verdicts equal ground truth and an independent recomputation; R34c the duplicate pair is correct; R34d match status, primary issue, approval band, levels and final status agree; R34e no blocked invoice is payable. |
| Blocked value released in error | Gross of invoices that ground truth blocks but the engine did not. Must be 0.00. |
| Cycle days | Calendar days from capture to the payment record (ready), over payment-ready invoices. |
| Open and past SLA | Open exceptions whose SLA due date is before the as-of date. The snapshot simulates no resolutions (ADR-011), so this is the inherited backlog, aged in business days since the exception was raised. |
