# Validation summary (starter)

Status: **PASS** - 0 violations, 19 labelled defects reported as expected (each belongs to a labelled scenario in ground truth).

| Check | Status | Violations | Labelled (expected) | Examples |
|---|---|---|---|---|
| primary and unique keys | pass | 0 | 0 |  |
| foreign keys (every declared FK) | pass | 0 | 0 |  |
| allowed values, formats, ranges, required | pass | 0 | 0 |  |
| embedded IDs and intake numbering | pass | 0 | 0 |  |
| date order and the as-of limit (no completed event after as-of) | pass | 0 | 2 | INV-VND-00017-2026-000025 dated before PO-2026-000019; INV-VND-00008-2026-000171 dated before PO-2026-000119 |
| arithmetic (lines -> headers, PO and receipt balances) | pass | 0 | 7 | GRNL-GRN-2026-000028-01 received beyond 5% tolerance; GRNL-GRN-2026-000149-01 received beyond 5% tolerance; GRNL-GRN-2026-000172-01 received beyond 5% tolerance |
| lifecycle events (state machines, order, current = last event) | pass | 0 | 0 |  |
| mix and edge-case counts vs target | pass | 0 | 0 |  |
| oracle labels == injection intent (blocking issues) | pass | 0 | 0 |  |
| no accidental duplicate pairs (number or content collisions) | pass | 0 | 10 | INV-VND-00017-2026-000007 collides with INV-VND-00017-2026-000001; INV-VND-00028-2026-000014 collides with INV-VND-00028-2026-000013; INV-VND-00012-2026-000041  |
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
| ap_event | 1626 |
| ap_exception | 75 |
| app_user | 28 |
| approval | 146 |
| captured_invoice | 200 |
| captured_invoice_line | 286 |
| duplicate_pair | 10 |
| erp_event | 505 |
| extraction_field | 4837 |
| goods_receipt | 180 |
| goods_receipt_line | 262 |
| ground_truth | 200 |
| ground_truth_line | 286 |
| intake_manifest | 200 |
| invoice | 200 |
| invoice_decision | 200 |
| invoice_line | 286 |
| match_allocation | 253 |
| match_result | 286 |
| payment | 135 |
| payment_terms | 4 |
| policy_version | 1 |
| purchase_order | 150 |
| purchase_order_line | 220 |
| sku | 60 |
| tax_code | 5 |
| vendor | 30 |
| vendor_status_history | 36 |
