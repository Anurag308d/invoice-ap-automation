# Validation summary (full)

Status: **PASS** - 0 violations, 187 labelled defects reported as expected (each belongs to a labelled scenario in ground truth).

| Check | Status | Violations | Labelled (expected) | Examples |
|---|---|---|---|---|
| primary and unique keys | pass | 0 | 0 |  |
| foreign keys (every declared FK) | pass | 0 | 0 |  |
| allowed values, formats, ranges, required | pass | 0 | 0 |  |
| embedded IDs and intake numbering | pass | 0 | 0 |  |
| date order and the as-of limit (no completed event after as-of) | pass | 0 | 22 | INV-VND-00193-2026-000125 dated before PO-2026-000115; INV-VND-00174-2026-000139 dated before PO-2026-000114; INV-VND-00270-2026-000246 dated before PO-2026-000 |
| arithmetic (lines -> headers, PO and receipt balances) | pass | 0 | 65 | GRNL-GRN-2026-000006-01 received beyond 5% tolerance; GRNL-GRN-2026-000031-01 received beyond 5% tolerance; GRNL-GRN-2026-000039-01 received beyond 5% tolerance |
| lifecycle events (state machines, order, current = last event) | pass | 0 | 0 |  |
| mix and edge-case counts vs target | pass | 0 | 0 |  |
| oracle labels == injection intent (blocking issues) | pass | 0 | 0 |  |
| no accidental duplicate pairs (number or content collisions) | pass | 0 | 100 | INV-VND-00209-2026-000085 collides with INV-VND-00209-2026-000080; INV-VND-00298-2026-000102 collides with INV-VND-00298-2026-000096; INV-VND-00298-2026-000150  |
| polymorphic event references (ap_event, erp_event) | pass | 0 | 0 |  |
| decision consistency (one decision per invoice, primary, blocked, issues, payment link) | pass | 0 | 0 |  |
| R34e: no payment for a blocked or unapproved invoice | pass | 0 | 0 |  |
| approvals only for invoices without a blocking issue at decision time | pass | 0 | 0 |  |
| N:M bridge and duplicate pairs | pass | 0 | 0 |  |
| capture consistency and policy provenance | pass | 0 | 0 |  |

## Rows per table

| Table | Rows |
|---|---|
| actor_role | 6 |
| ap_event | 16215 |
| ap_exception | 745 |
| app_user | 28 |
| approval | 1497 |
| captured_invoice | 2000 |
| captured_invoice_line | 2960 |
| duplicate_pair | 100 |
| erp_event | 5050 |
| extraction_field | 49435 |
| goods_receipt | 1800 |
| goods_receipt_line | 2669 |
| ground_truth | 2000 |
| ground_truth_line | 2960 |
| intake_manifest | 2000 |
| invoice | 2000 |
| invoice_decision | 2000 |
| invoice_line | 2960 |
| match_allocation | 2591 |
| match_result | 2960 |
| payment | 1348 |
| payment_terms | 4 |
| policy_version | 1 |
| purchase_order | 1500 |
| purchase_order_line | 2200 |
| sku | 400 |
| tax_code | 5 |
| vendor | 300 |
| vendor_status_history | 340 |
