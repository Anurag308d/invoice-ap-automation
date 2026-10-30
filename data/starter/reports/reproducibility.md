# Reproducibility (starter, seed 20261022)

Result: **PASS**

| Check | Result |
|---|---|
| Two builds, same seed, PYTHONHASHSEED 1 vs 2 | 274 of 274 files byte-identical |
| Row counts identical | True |
| Tree SHA-256 (sorted path:sha256 list) | `6207a33439c921829ac2328e6234e11185414d979c173d2312de1d915a43710d` |
| Equals the build in this folder | True |
| Seed 20261023: core row counts equal | True |
| Seed 20261023: core tables differ | True |
| Seed 20261023: tree SHA-256 | `959266cda5ff0e6352b9f9d2fb6e4baa00ce3e1408c5043a9f418156d50daed0` |

Core row counts:

| File | Rows |
|---|---|
| master/vendor.csv | 30 |
| master/purchase_order.csv | 150 |
| master/purchase_order_line.csv | 220 |
| master/goods_receipt.csv | 180 |
| source/invoice.csv | 200 |
| ground_truth/ground_truth.csv | 200 |
