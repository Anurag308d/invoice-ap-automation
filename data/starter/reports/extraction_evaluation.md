# Extraction evaluation (starter)

- Documents: 200; exact document match 200 (100.00%).
- Non-degraded documents with any mismatch: 0 (target 0).
- Degraded scans: 1, flagged for capture review: 1.
- Fields compared: 5174; field match rate 100.00%.
- **Silent errors: 0** (mismatch without a flag; target 0).
- Vendor resolution (VEN-01): 100.00%; invoice ID agreement (ID-01): 100.00%.
- Capture routing: 1 routed; precision 0.00%, recall -; equals ground truth: True.

## Per channel

| Channel | Documents | Exact | Fields | Accuracy | Silent errors |
|---|---|---|---|---|---|
| EDI | 47 | 47 | 1169 | 100.00% | 0 |
| EMAIL | 65 | 65 | 1772 | 100.00% | 0 |
| PORTAL | 81 | 81 | 2052 | 100.00% | 0 |
| SCAN | 7 | 7 | 181 | 100.00% | 0 |

## Per field

| Field | Compared | Match | Accuracy | Silent errors |
|---|---|---|---|---|
| vendor_id | 200 | 200 | 100.00% | 0 |
| invoice_id | 200 | 200 | 100.00% | 0 |
| vendor_name | 200 | 200 | 100.00% | 0 |
| vendor_tax_id | 200 | 200 | 100.00% | 0 |
| vendor_invoice_number | 200 | 200 | 100.00% | 0 |
| invoice_date | 200 | 200 | 100.00% | 0 |
| po_id | 200 | 200 | 100.00% | 0 |
| attention_user_id | 200 | 200 | 100.00% | 0 |
| currency | 200 | 200 | 100.00% | 0 |
| header_net_amount | 200 | 200 | 100.00% | 0 |
| header_tax_amount | 200 | 200 | 100.00% | 0 |
| header_gross_amount | 200 | 200 | 100.00% | 0 |
| line_count | 200 | 200 | 100.00% | 0 |
| po_line_id | 286 | 286 | 100.00% | 0 |
| sku_id | 286 | 286 | 100.00% | 0 |
| description | 286 | 286 | 100.00% | 0 |
| uom | 286 | 286 | 100.00% | 0 |
| quantity | 286 | 286 | 100.00% | 0 |
| unit_price | 286 | 286 | 100.00% | 0 |
| line_net_amount | 286 | 286 | 100.00% | 0 |
| tax_code | 286 | 286 | 100.00% | 0 |
| tax_amount | 286 | 286 | 100.00% | 0 |

## Confidence calibration

| Confidence | Fields | Accuracy |
|---|---|---|
| 1.00 | 1959 | 100.00% |
| 0.99 | 1122 | 100.00% |
| 0.98 | 389 | 100.00% |
| 0.97 | 142 | 100.00% |
| 0.95 | 1338 | 100.00% |
| 0.60 | 1 | 100.00% |
| not printed | 223 | 100.00% |

## Mismatches

| Document | Channel | Line | Field | Source | Captured | Flagged |
|---|---|---|---|---|---|---|
