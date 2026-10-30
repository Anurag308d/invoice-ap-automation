# Distribution summary (starter)

## vendor concentration

| key | value |
|---|---|
| goods_vendors | 27 |
| vendors_with_pos | 23 |
| top_20pct_share_of_pos | 55.3% |
| top_20pct_share_of_po_spend | 58.0% |

## po line net by category

| key | n | p10 | median | p90 | max |
|---|---|---|---|---|---|
| CANTEEN_SUPPLIES | 11 | 6264.00 | 17039.60 | 50654.00 | 78530.91 |
| ELECTRICAL | 14 | 12631.14 | 113709.40 | 197156.00 | 394807.77 |
| IT_HARDWARE | 16 | 54360.12 | 369061.38 | 653937.20 | 1520437.54 |
| MRO_SPARES | 98 | 6796.80 | 34948.72 | 119764.93 | 558048.96 |
| OFFICE_SUPPLIES | 11 | 7073.97 | 23933.00 | 53609.96 | 57564.52 |
| PACKAGING | 10 | 61759.60 | 238949.10 | 374450.30 | 374450.30 |
| RAW_MATERIALS | 30 | 34767.51 | 131447.30 | 319344.25 | 552810.80 |
| SAFETY_EQUIPMENT | 30 | 24763.44 | 220770.00 | 458179.12 | 479671.50 |

## po lines per po

| key | value |
|---|---|
| 1 | 112 |
| 2 | 22 |
| 3 | 8 |
| 4 | 4 |
| 5 | 2 |
| 6 | 1 |
| 8 | 1 |

## weekday share

| key | value |
|---|---|
| po_date | 100.0% |
| grn_received | 100.0% |
| invoice_date | 100.0% |
| received_at | 100.0% |

## lead time days by category

| key | median | p90 |
|---|---|---|
| CANTEEN_SUPPLIES | 2.00 | 5.00 |
| ELECTRICAL | 11.00 | 14.00 |
| IT_HARDWARE | 14.00 | 21.00 |
| MRO_SPARES | 20.00 | 28.00 |
| OFFICE_SUPPLIES | 6.00 | 7.00 |
| PACKAGING | 6.00 | 12.00 |
| RAW_MATERIALS | 15.00 | 21.00 |
| SAFETY_EQUIPMENT | 8.00 | 14.00 |

## payment terms mix

| key | value |
|---|---|
| NET15 | 3 |
| NET30 | 14 |
| NET45 | 9 |
| NET60 | 4 |

## channel mix documents

| key | value |
|---|---|
| EDI | 47 |
| EMAIL | 65 |
| PORTAL | 81 |
| SCAN | 7 |

## email from forwarding mailbox

6

## invoices received by month

| key | value |
|---|---|
| 2026-01 | 6 |
| 2026-02 | 16 |
| 2026-03 | 23 |
| 2026-04 | 39 |
| 2026-05 | 22 |
| 2026-06 | 24 |
| 2026-07 | 31 |
| 2026-08 | 10 |
| 2026-09 | 20 |
| 2026-10 | 9 |

## invoice gross

| key | value |
|---|---|
| p10 | 13160.78 |
| median | 78530.91 |
| p90 | 432061.04 |
| max | 1794116.30 |

## approval bands

| key | value |
|---|---|
| N2 | 9 |
| P1 | 93 |
| P2 | 31 |
| P3 | 2 |
| not eligible | 65 |

## final status at as of

| key | value |
|---|---|
| ON_HOLD | 59 |
| PAID | 124 |
| PAYMENT_READY | 11 |
| REJECTED | 6 |

## scenario spread by intake decile

| key | value |
|---|---|
| ARITHMETIC | [0, 0, 0, 0, 0, 1, 1, 0, 0, 0] |
| CAPTURE_REVIEW | [0, 0, 0, 0, 1, 0, 0, 0, 0, 0] |
| DUPLICATE | [2, 0, 2, 0, 1, 1, 1, 2, 1, 0] |
| INVOICE_BEFORE_PO | [0, 1, 0, 0, 0, 0, 0, 0, 1, 0] |
| MISSING_RECEIPT | [0, 2, 0, 1, 0, 3, 0, 1, 0, 1] |
| PRICE_VARIANCE | [3, 3, 1, 3, 0, 0, 2, 4, 3, 1] |
| QTY_MISMATCH | [1, 2, 0, 2, 2, 2, 0, 2, 2, 3] |
| TAX_VENDOR | [2, 0, 1, 0, 0, 0, 0, 0, 1, 2] |
