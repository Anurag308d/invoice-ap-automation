# Invoice-to-Pay (AP) automation

Invoice intake, field extraction, PO/receipt three-way matching, exception routing and payment
readiness, built and evaluated on a reproducible, fully synthetic ERP dataset. Python 3.11+, standard
library only.

## The problem

An accounts-payable team receives invoices through a supplier portal, EDI, e-mail and paper scans.
Each one must be read, tied to the right vendor and purchase order, checked against what was ordered
and received, routed to the right person when something is wrong, approved according to its amount,
and only then released for payment, without paying anything twice, early, or to the wrong vendor.
This repository automates that flow end to end and measures how well it does it.

## Solution overview

```
config/ap_policy.toml (versioned rules)
        |
generator ──> master/   vendors, status history, SKUs, POs, goods receipts, ERP events
        |──> inbox/    intake manifest + one document per invoice (portal JSON, EDI, e-mail, scan)
        |──> source/, ground_truth/   evaluation only: invoices as issued, labels from a rule-based oracle
        |
engine (reads master/ and inbox/ only)
   extract (adapter per channel, per-field confidence) -> resolve vendor from the printed tax ID
   -> duplicates -> vendor, PO, date, arithmetic and tax checks -> three-way match per line
   -> route exceptions to five actors -> approvals by amount band -> payment readiness and schedule
   -> processed/   decisions, exceptions, matches, N:M receipt allocations, approvals, payments,
                   append-only event log, decision trace
        |
evaluation, validation, exports, dashboard -> reports/, exports/
```

- **Generator** (`invoice_ap/generator`): exact volumes and scenario mix, a clean baseline first and
  then labelled anomalies, documents rendered with per-vendor templates. The oracle applies the
  documented rules to the true data, and generation fails loudly if any label differs from the
  intended scenario.
- **Engine** (`invoice_ap/engine`): never sees ground truth, the source invoices or a vendor-revealing
  ID. It reads every value from the documents and decides as of each invoice's processing time.
- **Evaluation and quality** (`invoice_ap/evaluation`, `invoice_ap/quality`): extraction accuracy,
  agreement with ground truth, per-type precision/recall/F1, per-invoice acceptance, and a full
  validation suite over every table.

Details: [architecture](docs/architecture.md), [business rules](docs/business_rules.md),
[schema](docs/schema.md), [data dictionary](docs/data_dictionary.md),
[data generation](docs/data_generation.md).

## Quickstart

The generated data is committed under `data/`, so the reports and the dashboard can be opened
without running anything.

macOS / Linux:

```bash
git clone <repo-url> invoice-ap-automation && cd invoice-ap-automation
python3 -m pip install -r requirements-dev.txt   # pytest only
python3 -m invoice_ap build-all                  # both scales end to end + reproducibility check (~35 s)
python3 -m pytest                                # all tests, including committed data == fresh build
open data/full/reports/dashboard.html            # offline dashboard, any browser
```

Windows PowerShell:

```powershell
git clone <repo-url> invoice-ap-automation; cd invoice-ap-automation
py -m pip install -r requirements-dev.txt
py -m invoice_ap build-all
py -m pytest
start data\full\reports\dashboard.html
```

## Configuration

| What | Where | Default |
|---|---|---|
| Rules, tolerances, routing, approval matrix, payment policy, calendar, as-of date | [`config/ap_policy.toml`](config/ap_policy.toml), versioned; every decision records the version | `AP-POLICY` 1.0.0, as of 2026-10-22 |
| Random seed | `--seed` | `20261022` |
| Scale | `--scale starter\|full\|<factor>` | `starter` = 1/10 of `full` |

Key tolerances: unit price within 2.00% of the PO (inclusive), cumulative quantity within 5% over
the PO, tax and arithmetic within 0.01, extraction confidence at least 0.90. Their reasons are in
[business rules §3](docs/business_rules.md) and ADR-007.

## How to run

Each command takes `--scale starter|full` or `--data <folder>`.

| Command | What it does |
|---|---|
| `python -m invoice_ap build-all` | Everything for both scales, then the reproducibility check |
| `python -m invoice_ap build --scale full` | One scale: generate, run, evaluate, validate, export, dashboard, manifest |
| `python -m invoice_ap generate --scale full` | Master data, documents, source invoices, ground truth |
| `python -m invoice_ap run --scale full` | The AP engine on `master/` and `inbox/` only |
| `python -m invoice_ap evaluate --scale full` | Metrics against ground truth and per-invoice acceptance |
| `python -m invoice_ap validate --scale full` | Full validation suite over every table |
| `python -m invoice_ap export --scale full` | JSON for every table, `seed.sql`, `evaluation_seed.sql` |
| `python -m invoice_ap queue --role OPERATIONS_ANALYST --scale full` | One actor's open work queue (all five without `--role`) |
| `python -m invoice_ap explain INV-VND-00279-2026-000032 --scale full` | One invoice's decision, exceptions, events and trace |
| `python -m invoice_ap repro --scale starter` | Two rebuilds (two hash seeds) and one with another seed, compared file by file |
| `python -m invoice_ap plan --scale full` | The exact volume and scenario allocation |
| `python -m invoice_ap policy` / `docs --check` | Validate the policy file / check that generated docs are in sync |

## How to verify

1. `python -m pytest`: about 540 tests in about 45 s, covering generator exactness, extraction
   (including mutated documents), decisions against ground truth, the no-leakage sandboxes,
   time travel, outputs, and the parity of the committed data with a fresh build. See
   [testing and verification](docs/testing_and_verification.md).
2. Open the reports in `data/full/reports/` (the same files exist for `data/starter/`):

| File | Contents |
|---|---|
| `dashboard.html` | KPIs, the five actors' queues, invoice explorer with decision traces, evaluation, validation |
| `evaluation.md` | Agreement with ground truth, per-type precision/recall/F1, confusion matrices, duplicates, approvals, payments, KPIs with definitions, backlog, acceptance |
| `acceptance_per_invoice.csv` | Pass/fail for every invoice against criteria R34a-e |
| `extraction_evaluation.md` | Field, channel and document accuracy of extraction; every mismatch |
| `validation_summary.md` | The validation suite: keys, FKs, enums, dates, arithmetic, lifecycles, duplicates, engine invariants |
| `reproducibility.md` | Two rebuilds compared file by file, plus another seed |
| `source_manifest.json` | Every file with rows, bytes and SHA-256; command, seed, policy, provenance, licences |
| `distribution_summary.md` | Realised distributions: vendor concentration, prices, lead times, channels, bands |

3. Load `exports/sql/seed.sql` and then `exports/sql/evaluation_seed.sql` into SQLite with
   `PRAGMA foreign_keys = ON`. The full-scale SQL is regenerated by `build-all`.

## Repository layout and outputs

```
config/ap_policy.toml      versioned AP policy (TOML)
invoice_ap/common/         vocabulary, IDs, Decimal money, calendar, lifecycles, policy loader
invoice_ap/spec/           machine-readable data dictionary (renders docs/data_dictionary.md), CSV I/O
invoice_ap/generator/      allocation, world, planner, documents, oracle, writer
invoice_ap/engine/         adapters, extraction, vendor identity, validation, matching, decisions, explain
invoice_ap/evaluation/     extraction and decision metrics, per-invoice acceptance
invoice_ap/quality/        quick self-checks and the full validation suite
invoice_ap/export/         JSON exports and SQL seeds
invoice_ap/report/         manifest, distributions, queues, dashboard
invoice_ap/orchestrate.py  build, build-all, repro
tests/                     pytest suite
docs/                      design, rules, schema, dictionary, evaluation, testing, walkthrough, ADRs
data/<scale>/              master/ inbox/ source/ ground_truth/ processed/ exports/ reports/
ai_disclosure/             AI-usage statement, prompt history, review evidence
```

`data/starter/` is committed complete. `data/full/` is committed except four regenerable groups that
keep the repository near 25 MB: `exports/json/`, `exports/sql/`, `processed/decision_trace.jsonl` and
`processed/extraction_field.csv`. `build-all` regenerates them, and their SHA-256 values are in
`data/full/reports/source_manifest.json`. A test checks every committed file byte for byte against a
fresh build. `.gitattributes` forces LF line endings, so the checksums hold on Windows.

## Results snapshot (committed full build, seed 20261022)

| | |
|---|---|
| Volumes | 300 vendors, 1,500 POs, 2,200 PO lines, 1,800 goods receipts, 2,000 invoices (2,960 lines) |
| Scenario mix | CLEAN 1,350; price variance 200; quantity mismatch 160; duplicates 100; missing receipt 80; tax/vendor 60; arithmetic 20; invoice before PO 20; capture review 10 |
| Channels | EDI 900, portal 656, e-mail 340 (35 forwarded), scan 104 |
| Extraction | 52,640 fields compared; 1,990 / 1,990 non-degraded documents exact; 10 / 10 degraded scans flagged; **0 silent errors**; vendor resolution 100% |
| Agreement with ground truth | 2,000 / 2,000 invoices on issue types, primary issue, match status, duplicate pair, routing, approval band and levels, final status, payment and dates; 2,960 / 2,960 lines on price, quantity and tax status |
| Per exception type | All 16 types present: precision = recall = F1 = 1.0; 8 types not in the data are covered by test fixtures and reported as "not present" |
| Duplicates | 100 / 100 pairs correct; 0 false positives on recurring, same-day and partial-billing true negatives |
| Outcome at the snapshot | PAID 1,192; PAYMENT_READY 156; PENDING_APPROVAL 2; ON_HOLD 600; REJECTED 50 |
| KPIs | STP 46.05%; exception rate 32.50%; value held on truly blocked invoices INR 7,54,12,564.65; 0.00 released in error |
| Payment-ready safety | **0** invoices with a payment and an open blocking exception or a missing approval |
| Exceptions raised | price variance 200, quantity over received 156, missing receipt 129, quantity over PO 50, exact duplicate 50, number reuse 35, invoice before PO 20, header total 15, tax amount 15, tax code 15, vendor closed 15, suspected duplicate 15, capture review 10, foreign PO 10, line amount 5, vendor blocked 5 |
| Per-invoice acceptance | 2,000 / 2,000 pass (10 degraded scans correctly routed to capture review) |
| Validation suite | 16 checks pass, 0 violations; 187 labelled defects reported as expected |
| Reproducibility | 2,074 / 2,074 files byte-identical across two rebuilds (PYTHONHASHSEED 1 vs 2); another seed changes the data, not the volumes |

## Key assumptions and design decisions

All of them, with alternatives and trade-offs, are in [assumptions and decisions](docs/assumptions_and_decisions.md).

- **The vendor comes from the document only** (ADR-037). The engine resolves it from the printed tax
  registration number, then assigns the invoice ID; the channel's sender is only a cross-check.
- **No future information** (ADR-038, ADR-041). Receipts, vendor status and POs count only if they
  were known at processing time; as-of snapshot columns are reporting only.
- **Labels from rules, not randomness** (ADR-016). An oracle derives ground truth from the true data
  and the policy; the engine re-derives decisions independently from documents.
- **Gates and precedence** (ADR-020). Capture, vendor and duplicate checks stop processing; all other
  issues are collected, and a documented precedence picks the primary issue and queue.
- **Exact, reproducible data** (ADR-005, ADR-014, ADR-015, ADR-022). Exact volumes and mix at both scales, Decimal
  money with half-up rounding, seeded sub-streams, no clock and no hash-order dependence.
- **Synthetic GST-style tax and an Indian calendar** (ADR-013). This is not a tax engine.
- **Simulated approvals** (ADR-011). Approvers approve after a fixed turnaround, and the payment
  run is simulated with no bank integration.

## Limitations and next steps

- No exception resolutions and no approver rejections are simulated. Almost every open exception is
  therefore "open and past SLA at the snapshot"; the reports age this backlog (<= 5, 6-20 and
  > 20 business days) rather than inventing human decisions.
- Every business event falls on a business day, a simplification.
- Eight exception types do not occur in the generated data (vendor not found, sender mismatch, PO
  not found, future-dated invoice, invalid tax code, unmatched PO line, vendor not payable, due
  date passed). Each is covered by an engine test fixture.
- Documents are text-based formats; there is no image OCR. Degraded scans simulate OCR damage.
- Engine and oracle share one author. Agreement shows a consistent implementation of the
  documented rules, and a tolerance-mutation test shows the evaluation detects divergence.
- Next steps: simulated resolutions with their own audit trail, image documents with real OCR, a
  multi-currency and multi-entity policy, and a live queue UI on top of the event log.

## AI usage

AI tools were used, as the submission guidelines allow. The AI-usage note and the prompt history
required by the guidelines are in [`ai_disclosure/`](ai_disclosure/).


## Licence

MIT, see [LICENSE](LICENSE). All data is synthetic and generated by this code. Names, tax numbers
and e-mail addresses are invented (reserved `.example` domains), and users are role labels.
