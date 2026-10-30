# Reproducibility (full, seed 20261022)

Result: **PASS**

| Check | Result |
|---|---|
| Two builds, same seed, PYTHONHASHSEED 1 vs 2 | 2074 of 2074 files byte-identical |
| Row counts identical | True |
| Tree SHA-256 (sorted path:sha256 list) | `53bab54c64d4b02667023784829affa304ed63c3ae8e187bcb4d09deb946a740` |
| Equals the build in this folder | True |
| Seed 20261023: core row counts equal | True |
| Seed 20261023: core tables differ | True |
| Seed 20261023: tree SHA-256 | `8d9cb76a3a66ef1178dc010b45ea41f555c2482d1ff16deddb6f2e6483708b78` |

Core row counts:

| File | Rows |
|---|---|
| master/vendor.csv | 300 |
| master/purchase_order.csv | 1500 |
| master/purchase_order_line.csv | 2200 |
| master/goods_receipt.csv | 1800 |
| source/invoice.csv | 2000 |
| ground_truth/ground_truth.csv | 2000 |
