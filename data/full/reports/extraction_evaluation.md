# Extraction evaluation (full)

- Documents: 2000; exact document match 1992 (99.60%).
- Non-degraded documents with any mismatch: 0 (target 0).
- Degraded scans: 10, flagged for capture review: 10.
- Fields compared: 52640; field match rate 99.98%.
- **Silent errors: 0** (mismatch without a flag; target 0).
- Vendor resolution (VEN-01): 100.00%; invoice ID agreement (ID-01): 100.00%.
- Capture routing: 10 routed; precision 80.00%, recall 100.00%; equals ground truth: True.

## Per channel

| Channel | Documents | Exact | Fields | Accuracy | Silent errors |
|---|---|---|---|---|---|
| EDI | 900 | 900 | 23706 | 100.00% | 0 |
| EMAIL | 340 | 340 | 8947 | 100.00% | 0 |
| PORTAL | 656 | 656 | 17375 | 100.00% | 0 |
| SCAN | 104 | 96 | 2612 | 99.69% | 0 |

## Per field

| Field | Compared | Match | Accuracy | Silent errors |
|---|---|---|---|---|
| vendor_id | 2000 | 2000 | 100.00% | 0 |
| invoice_id | 2000 | 2000 | 100.00% | 0 |
| vendor_name | 2000 | 2000 | 100.00% | 0 |
| vendor_tax_id | 2000 | 2000 | 100.00% | 0 |
| vendor_invoice_number | 2000 | 1998 | 99.90% | 0 |
| invoice_date | 2000 | 1997 | 99.85% | 0 |
| po_id | 2000 | 2000 | 100.00% | 0 |
| attention_user_id | 2000 | 2000 | 100.00% | 0 |
| currency | 2000 | 2000 | 100.00% | 0 |
| header_net_amount | 2000 | 2000 | 100.00% | 0 |
| header_tax_amount | 2000 | 2000 | 100.00% | 0 |
| header_gross_amount | 2000 | 1997 | 99.85% | 0 |
| line_count | 2000 | 2000 | 100.00% | 0 |
| po_line_id | 2960 | 2960 | 100.00% | 0 |
| sku_id | 2960 | 2960 | 100.00% | 0 |
| description | 2960 | 2960 | 100.00% | 0 |
| uom | 2960 | 2960 | 100.00% | 0 |
| quantity | 2960 | 2960 | 100.00% | 0 |
| unit_price | 2960 | 2960 | 100.00% | 0 |
| line_net_amount | 2960 | 2960 | 100.00% | 0 |
| tax_code | 2960 | 2960 | 100.00% | 0 |
| tax_amount | 2960 | 2960 | 100.00% | 0 |

## Confidence calibration

| Confidence | Fields | Accuracy |
|---|---|---|
| 1.00 | 16673 | 100.00% |
| 0.99 | 22806 | 100.00% |
| 0.98 | 3077 | 100.00% |
| 0.97 | 930 | 100.00% |
| 0.95 | 6979 | 100.00% |
| 0.60 | 2 | 100.00% |
| 0.00 | 8 | 0.00% |
| not printed | 2165 | 100.00% |

## Mismatches

| Document | Channel | Line | Field | Source | Captured | Flagged |
|---|---|---|---|---|---|---|
| DOC-2026-000325 | SCAN |  | invoice_date | 2026-03-10 |  | yes |
| DOC-2026-000432 | SCAN |  | vendor_invoice_number | INV-2026-0243 |  | yes |
| DOC-2026-000650 | SCAN |  | header_gross_amount | 578041.41 |  | yes |
| DOC-2026-000738 | SCAN |  | header_gross_amount | 533483.55 |  | yes |
| DOC-2026-001621 | SCAN |  | invoice_date | 2026-08-26 |  | yes |
| DOC-2026-001769 | SCAN |  | invoice_date | 2026-09-15 |  | yes |
| DOC-2026-001820 | SCAN |  | vendor_invoice_number | INV-2026-0263 |  | yes |
| DOC-2026-001949 | SCAN |  | header_gross_amount | 136614.41 |  | yes |
