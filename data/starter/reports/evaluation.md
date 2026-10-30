# Decision evaluation (starter)

Invoices evaluated: 200. Definitions are at the end of this page.

## Headline

| KPI | Value |
|---|---|
| STP rate | 46.50% (93 invoices) |
| Exception rate | 32.50% |
| Payment-ready safety (R34e) violations | 0 |
| Per-invoice acceptance (R34a-e) | 200 pass / 0 fail |
| Value at risk held (INR) | 5017847.17 |
| Blocked value released in error (INR) | 0.00 |
| Cycle days capture -> ready (median / p90) | 0 / 4 |

## Agreement with ground truth (invoice level)

| Item | Agreement |
|---|---|
| invoice_id | 200/200 (100.00%) |
| issue_types | 200/200 (100.00%) |
| primary_issue | 200/200 (100.00%) |
| blocked | 200/200 (100.00%) |
| match_status | 200/200 (100.00%) |
| duplicate_of | 200/200 (100.00%) |
| assigned_roles | 200/200 (100.00%) |
| queues | 200/200 (100.00%) |
| approval_band | 200/200 (100.00%) |
| approval_levels | 200/200 (100.00%) |
| final_status | 200/200 (100.00%) |
| payment_ready | 200/200 (100.00%) |
| payment_status | 200/200 (100.00%) |
| due_date | 200/200 (100.00%) |
| scheduled_date | 200/200 (100.00%) |

## Agreement with ground truth (line level)

| Item | Agreement |
|---|---|
| price_status | 286/286 (100.00%) |
| qty_status | 286/286 (100.00%) |
| tax_status | 286/286 (100.00%) |
| received_qty | 286/286 (100.00%) |
| prior_invoiced_qty | 286/286 (100.00%) |

## Per exception type (invoice level)

| Type | TP | FP | FN | Precision | Recall | F1 |
|---|---|---|---|---|---|---|
| EXT_LOW_CONFIDENCE | 1 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |
| DUPLICATE_EXACT | 6 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |
| DUPLICATE_NUMBER_REUSE | 3 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |
| DUPLICATE_SUSPECTED | 1 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |
| VENDOR_NOT_FOUND | 0 | 0 | 0 | not present | not present | not present |
| VENDOR_SENDER_MISMATCH | 0 | 0 | 0 | not present | not present | not present |
| VENDOR_CLOSED | 1 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |
| VENDOR_BLOCKED | 1 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |
| PO_NOT_FOUND | 0 | 0 | 0 | not present | not present | not present |
| VENDOR_PO_MISMATCH | 1 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |
| INVOICE_DATE_IN_FUTURE | 0 | 0 | 0 | not present | not present | not present |
| INVOICE_BEFORE_PO | 2 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |
| HEADER_TOTAL_MISMATCH | 1 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |
| LINE_AMOUNT_MISMATCH | 1 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |
| TAX_CODE_INVALID | 0 | 0 | 0 | not present | not present | not present |
| TAX_CODE_MISMATCH | 1 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |
| TAX_AMOUNT_MISMATCH | 2 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |
| PO_LINE_UNMATCHED | 0 | 0 | 0 | not present | not present | not present |
| MISSING_RECEIPT | 8 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |
| QTY_EXCEEDS_PO | 5 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |
| QTY_EXCEEDS_RECEIVED | 13 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |
| PRICE_VARIANCE | 20 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |
| VENDOR_NOT_PAYABLE | 0 | 0 | 0 | not present | not present | not present |
| PAYMENT_DUE_DATE_PASSED | 0 | 0 | 0 | not present | not present | not present |

## Per exception type (line level)

| Type | TP | FP | FN | Precision | Recall | F1 |
|---|---|---|---|---|---|---|
| LINE_AMOUNT_MISMATCH | 1 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |
| TAX_CODE_INVALID | 0 | 0 | 0 | not present | not present | not present |
| TAX_CODE_MISMATCH | 1 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |
| TAX_AMOUNT_MISMATCH | 2 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |
| PO_LINE_UNMATCHED | 0 | 0 | 0 | not present | not present | not present |
| MISSING_RECEIPT | 10 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |
| QTY_EXCEEDS_PO | 5 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |
| QTY_EXCEEDS_RECEIVED | 19 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |
| PRICE_VARIANCE | 20 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |

Not present in this dataset (covered by unit fixtures): VENDOR_NOT_FOUND, VENDOR_SENDER_MISMATCH, PO_NOT_FOUND, INVOICE_DATE_IN_FUTURE, TAX_CODE_INVALID, PO_LINE_UNMATCHED, VENDOR_NOT_PAYABLE, PAYMENT_DUE_DATE_PASSED.

## Primary issue confusion (expected -> engine; off-diagonal 0)

| Expected -> engine | Invoices |
|---|---|
| DUPLICATE_EXACT -> DUPLICATE_EXACT | 6 |
| DUPLICATE_NUMBER_REUSE -> DUPLICATE_NUMBER_REUSE | 3 |
| DUPLICATE_SUSPECTED -> DUPLICATE_SUSPECTED | 1 |
| EXT_LOW_CONFIDENCE -> EXT_LOW_CONFIDENCE | 1 |
| HEADER_TOTAL_MISMATCH -> HEADER_TOTAL_MISMATCH | 1 |
| INVOICE_BEFORE_PO -> INVOICE_BEFORE_PO | 2 |
| LINE_AMOUNT_MISMATCH -> LINE_AMOUNT_MISMATCH | 1 |
| MISSING_RECEIPT -> MISSING_RECEIPT | 8 |
| NONE -> NONE | 135 |
| PRICE_VARIANCE -> PRICE_VARIANCE | 20 |
| QTY_EXCEEDS_PO -> QTY_EXCEEDS_PO | 5 |
| QTY_EXCEEDS_RECEIVED -> QTY_EXCEEDS_RECEIVED | 11 |
| TAX_AMOUNT_MISMATCH -> TAX_AMOUNT_MISMATCH | 2 |
| TAX_CODE_MISMATCH -> TAX_CODE_MISMATCH | 1 |
| VENDOR_BLOCKED -> VENDOR_BLOCKED | 1 |
| VENDOR_CLOSED -> VENDOR_CLOSED | 1 |
| VENDOR_PO_MISMATCH -> VENDOR_PO_MISMATCH | 1 |

## Final status confusion

| Expected -> engine | Invoices |
|---|---|
| ON_HOLD -> ON_HOLD | 59 |
| PAID -> PAID | 124 |
| PAYMENT_READY -> PAYMENT_READY | 11 |
| REJECTED -> REJECTED | 6 |

## Duplicates

| Item | Value |
|---|---|
| Expected pairs | 10 |
| Detected pairs | 10 |
| Correct pairs | 10 |
| Pair precision | 100.00% |
| Pair recall | 100.00% |
| False positives on true negatives | 0 |

Correct by scenario:

| Scenario | Correct / expected |
|---|---|
| DUP-CONTENT | 1/1 |
| DUP-EXACT | 3/3 |
| DUP-EXACT-NORMALIZED | 2/2 |
| DUP-EXACT-NPO | 1/1 |
| DUP-NUMBER-REUSE | 3/3 |

## Approvals

| Item | Value |
|---|---|
| Eligible invoices | 135 |
| Approvals for blocked invoices | 0 |
| Levels pending at the as-of date | 0 |

Invoices by approval band:

| Band | Invoices |
|---|---|
| N2 | 9 |
| P1 | 93 |
| P2 | 31 |
| P3 | 2 |
| not eligible | 65 |

## Payments

| Item | Value |
|---|---|
| Payment records | 135 |
| PAID | 124 |
| SCHEDULED | 11 |
| RTGS | 36 |
| Blocked or unapproved with a payment | 0 |

## Exceptions

Raised, by type:

| Type | Exceptions |
|---|---|
| DUPLICATE_EXACT | 6 |
| DUPLICATE_NUMBER_REUSE | 3 |
| DUPLICATE_SUSPECTED | 1 |
| EXT_LOW_CONFIDENCE | 1 |
| HEADER_TOTAL_MISMATCH | 1 |
| INVOICE_BEFORE_PO | 2 |
| LINE_AMOUNT_MISMATCH | 1 |
| MISSING_RECEIPT | 10 |
| PRICE_VARIANCE | 20 |
| QTY_EXCEEDS_PO | 5 |
| QTY_EXCEEDS_RECEIVED | 19 |
| TAX_AMOUNT_MISMATCH | 2 |
| TAX_CODE_MISMATCH | 1 |
| VENDOR_BLOCKED | 1 |
| VENDOR_CLOSED | 1 |
| VENDOR_PO_MISMATCH | 1 |

Open at the snapshot, by role:

| Role | Open |
|---|---|
| BUSINESS_REQUESTER | 49 |
| OPERATIONS_ANALYST | 11 |
| PROCESS_OWNER | 7 |
| SYSTEM_ADMINISTRATOR | 2 |

Open at the snapshot, by queue:

| Queue | Open |
|---|---|
| AP_CAPTURE_REVIEW | 1 |
| AP_DUPLICATES | 4 |
| AP_TAX | 3 |
| AP_VALIDATION | 3 |
| POLICY_EXCEPTIONS | 7 |
| PRICE_REVIEW | 20 |
| RECEIPT_CONFIRMATION | 29 |
| VENDOR_MASTER | 2 |

## Backlog: open and past SLA at the snapshot (no resolutions simulated)

69 of 69 open exceptions are past their SLA at the snapshot. Age is in business days since the exception was raised.

| Role | <= 5 business days | 6-20 business days | > 20 business days |
|---|---|---|---|
| ALL ROLES | 0 | 4 | 65 |
| BUSINESS_REQUESTER | 0 | 1 | 48 |
| OPERATIONS_ANALYST | 0 | 2 | 9 |
| PROCESS_OWNER | 0 | 1 | 6 |
| SYSTEM_ADMINISTRATOR | 0 | 0 | 2 |

## Value at risk held, by primary issue (INR)

| Primary issue | INR |
|---|---|
| DUPLICATE_EXACT | 1255924.70 |
| DUPLICATE_NUMBER_REUSE | 204091.36 |
| DUPLICATE_SUSPECTED | 417482.05 |
| EXT_LOW_CONFIDENCE | 239029.11 |
| HEADER_TOTAL_MISMATCH | 0.09 |
| INVOICE_BEFORE_PO | 460361.94 |
| LINE_AMOUNT_MISMATCH | 328.50 |
| MISSING_RECEIPT | 1208557.19 |
| PRICE_VARIANCE | 243224.51 |
| QTY_EXCEEDS_PO | 90998.87 |
| QTY_EXCEEDS_RECEIVED | 315972.86 |
| TAX_AMOUNT_MISMATCH | 1063.78 |
| TAX_CODE_MISMATCH | 25933.63 |
| VENDOR_BLOCKED | 129564.85 |
| VENDOR_CLOSED | 389504.55 |
| VENDOR_PO_MISMATCH | 35809.18 |

## Per-invoice acceptance (R34a-e)

200 of 200 invoices pass; 1 are flagged for capture review, which is their expected outcome. Full list: `acceptance_per_invoice.csv`.

| Criterion | pass | flagged | fail |
|---|---|---|---|
| r34a_extraction | 199 | 1 | 0 |
| r34b_arithmetic_tax | 200 | 0 | 0 |
| r34c_duplicate_pair | 200 | 0 | 0 |
| r34d_match_and_approval | 200 | 0 | 0 |
| r34e_no_blocked_payment_ready | 200 | 0 | 0 |

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
