# Evaluation plan

The evaluation compares what the engine decided, working only from master data and the inbox,
with two independent references:
- the true source invoices, which drive the extraction metrics;
- the oracle's ground truth, which drives the decision metrics.

It writes `reports/evaluation.json` (machine-readable) and `reports/evaluation.md` (readable) for
each scale, and the dashboard shows the same numbers. Stage 3 delivers the extraction part, Stage 4
the decision part and Stage 5 the data-quality and reproducibility parts.

## 1. Acceptance criteria -> metrics

The assignment's acceptance criteria apply "for each invoice". Each one is computed per invoice and
aggregated. The per-invoice acceptance check (section 3) must pass for all 2,000 invoices, or every
deviation is listed and explained.

| Criterion | Metric | Target | Computed from |
|---|---|---|---|
| R34a extracted fields match source | Field-level accuracy per field and per channel; document-level exact match; a list of every mismatch; **silent errors** = mismatches not flagged as low confidence and not caught by a validation rule. Vendor accuracy comes from the extracted vendor fields and the VEN-01 result, never from an ID | Silent errors = 0; field match 100% outside the deliberately degraded scans (CAPTURE_REVIEW) | `captured_*` + `extraction_field` vs `source/invoice*` |
| R34b line arithmetic and tax reconcile | Agreement of ARI-01, ARI-02 and TAX-01..03 verdicts with ground truth; an independent recomputation of every line and header from the source data | 100% agreement | `ap_exception`, `match_result` vs `ground_truth*` |
| R34c duplicate detection flags the correct pair | Pair precision, pair recall and pair accuracy (correct original); false positives on the true-negative sets (recurring same-amount, same-day different-PO) | 100% / 100% / 100%; 0 false positives | `duplicate_pair` vs `ground_truth.expected_duplicate_of` |
| R34d three-way match and approval outcome agree with policy | Match-status agreement (invoice and line); per-exception-type precision, recall and F1; primary-issue confusion matrix; approval eligibility, band and level-sequence agreement | 100% agreement; F1 = 1.0 for every type present | `invoice_decision`, `match_result`, `approval` vs ground truth |
| R34e no blocked invoice is marked payment-ready | Count of invoices with a payment record and an open blocking exception, a pending or missing approval, or a non-payable vendor | **0 (hard invariant)** | `payment`, `ap_exception`, `approval` |

## 2. Metric catalogue

| ID | Metric | Definition |
|---|---|---|
| E1 | Extraction accuracy | Exact equality after canonical normalisation (dates ISO, decimals canonical) per field, broken down by channel and template. A document-level match requires every field and line to match. A confidence-calibration table shows accuracy per confidence bucket. Vendor resolution compares `captured_invoice.vendor_id` with `invoice.vendor_id`, and the engine's ID-01 `invoice_id` with the source `invoice_id` (equal only when VEN-01 was right). |
| E2 | Capture routing | Share of documents routed to capture review; precision and recall of routing against the documents that actually contain an extraction error. |
| E3 | Exception classification | Multi-label, invoice level: precision, recall and F1 per exception type, plus micro and macro averages. Line-level labels are compared the same way. |
| E4 | Primary outcome | Confusion matrix of expected vs predicted primary issue (including NONE), plus a confusion matrix of final status at the as-of date. |
| E5 | Match status | Agreement rate of invoice and line `match_status`. |
| E6 | Duplicates | Pair precision, recall and accuracy per duplicate type; true-negative false-positive count. |
| E7 | Routing | Agreement of assigned role and queue with `expected_assigned_roles` / `expected_queues`; SLA due-date correctness; open and overdue counts per actor role. |
| E8 | Approvals | Eligibility agreement; band and level-sequence agreement; approvals created for blocked invoices (must be 0); pending approvals at the as-of date. |
| E9 | Payments | Payment-ready safety (R34e), payment-ready recall (eligible invoices with a payment), due-date, scheduled-date and method agreement, PAID vs SCHEDULED counts. |
| E10 | Operational KPIs | **STP rate** = invoices that reached PAYMENT_READY or PAID with only SYSTEM actions (no exception, AUTO approval) / all invoices. **Exception rate** = invoices with >= 1 blocking exception / all invoices. Exceptions by type, role and queue; cycle time received -> ready (median, p90). |
| E11 | Value at risk prevented | Money held back on invoices with a true blocking issue: the full gross for duplicates, closed or blocked vendors, foreign POs, missing receipts and invoices before the PO; the over-billed amount (excess quantity x price, or price difference x quantity, plus tax) for quantity and price variances; the absolute difference for tax and arithmetic errors. Reported prevented vs missed. |
| E12 | Mix vs target | Actual category and sub-scenario counts vs Table G2/G6 targets, and the edge-case coverage table. |
| E13 | Data quality | Pass/fail counts of the validation suite (PK, FK, enums, date order, arithmetic, lifecycle, duplicates), with labelled defects reported apart from violations (Stage 5, `validation_summary.*`). |
| E14 | Distribution realism | Vendor concentration (top-20% share, Gini), line values by category (quantiles), weekday share, lead times, payment terms, channels, approval bands, monthly volumes (Stage 2-5, `distribution_summary.*`). |
| E15 | Reproducibility | Two builds with the same seed: identical row counts and SHA-256 per file. A different seed: same counts and mix, different checksums (Stage 5, `reproducibility.*`). |

## 3. Per-invoice acceptance check

Each invoice passes when all of the following hold:
1. every captured field equals the source, or the document was routed to capture review (R34a);
2. the arithmetic and tax verdicts equal the oracle's (R34b);
3. its duplicate status and original equal the expected ones (R34c);
4. its issue set, primary issue, match status, roles and queues, approval band and levels, and
   final status equal the ground truth (R34d);
5. it has a payment record if and only if the ground truth expects one, and never while blocked (R34e).

The report lists every failing invoice with the differing fields.

## 4. Evaluation Focus (a)-(g) -> evidence

| Focus | Evidence |
|---|---|
| (a) realistic distributions and variation | E14 distribution summary; channel and template variety (E1 breakdowns); approval-band and terms mixes |
| (b) consistent IDs and valid joins | ID-pattern checks, FK and embedded-ID checks in the validation suite (E13); `tests/test_ids_and_money.py`, `tests/test_spec.py` |
| (c) dependency and lifecycle consistency | Parent-before-child generation order; date-order checks; event sequences checked against `invoice_ap/common/lifecycle.py`; current status = last event (E13) |
| (d) correct derived values and reconciliation | Independent recomputation of every derived column (E13); R34b metrics (E3) |
| (e) normal, boundary, failure and exception coverage | Mix vs target and edge-case table (E12); boundary sub-scenarios (price at, inside and outside tolerance; quantity at and outside; tax rounding); true negatives (E6) |
| (f) separate ground truth | `ground_truth/` folder; label-free input check; no-leakage tests: static import, sender, ID and snapshot bans (active now), runtime and ID-blind sandboxes (Stage 3), time-travel sandbox (Stage 4); evaluation exports in separate files (Stage 5) |
| (g) fixed-seed reproducibility, documentation and lawful provenance | E15 report; `source_manifest.json` (command, seed, scale, policy version, per-file SHA-256, provenance: 100% synthetic, no external data); these docs |

## 5. How we know it works

There are five independent layers of evidence. No single one is trusted alone.

1. Unit tests with hand-computed fixtures for every rule, boundary and gate.
2. The generator's oracle-vs-intent assertion. Every injected scenario must produce exactly its
   intended labels under the documented policy, or generation stops.
3. The engine-vs-oracle comparison above. The engine reaches its decisions from rendered documents
   through a separate code path.
4. The defect-aware validation suite over every table.
5. Reproducibility: same seed gives identical checksums; a different seed gives the same mix.
