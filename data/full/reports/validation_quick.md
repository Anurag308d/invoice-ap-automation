# Quick validation (full)

Status: **pass** - violations 0, labelled defects reported as expected 187

| Check | Status | Violations | Labelled (expected) | Note |
|---|---|---|---|---|
| primary and unique keys | pass | 0 | 0 |  |
| foreign keys (every declared FK) | pass | 0 | 0 |  |
| allowed values, formats, ranges, required | pass | 0 | 0 |  |
| embedded IDs and intake numbering | pass | 0 | 0 |  |
| date order and the as-of limit (no completed event after as-of) | pass | 0 | 22 |  |
| arithmetic (lines -> headers, PO and receipt balances) | pass | 0 | 65 |  |
| lifecycle events (state machines, order, current = last event) | pass | 0 | 0 |  |
| mix and edge-case counts vs target | pass | 0 | 0 |  |
| oracle labels == injection intent (blocking issues) | pass | 0 | 0 |  |
| no accidental duplicate pairs (number or content collisions) | pass | 0 | 100 |  |
