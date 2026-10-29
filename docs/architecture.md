# Architecture

Status: Stage 1 (design). Sections marked *planned* are built in later stages; the module and
file names below are the contract those stages implement.

## 1. What the system does

The build has two halves that never share logic.

1. A **synthetic ERP world** (the generator). It creates vendors, POs, goods receipts and the invoices
   vendors send, renders each invoice as a document in its intake channel, and derives the expected
   outcome of every invoice with a rule-based **oracle**.
2. An **AP automation engine**. It sees only what a real AP department would see: ERP master data
   and an inbox of documents. It extracts fields, validates, detects duplicates, performs the
   three-way match, routes exceptions to the five actors, requests approvals and schedules payments.

The **evaluation** then compares the engine's output with the oracle's ground truth and with the
true source invoices. Because the engine works only from extracted documents, the metrics measure
real behaviour rather than restating what the generator already knew.

```mermaid
flowchart LR
  subgraph GEN["generator (invoice_ap.generator)"]
    W["world: users, vendors + status history,<br/>SKUs, tax codes, POs, GRNs"] --> P["scenario planner<br/>(exact allocation)"]
    P --> S["true invoices + lines<br/>(baseline first, then labelled injections)"]
    S --> R["renderer: PORTAL json, EDI flat file,<br/>EMAIL text, SCAN OCR text"]
    S --> O["oracle: documented rules<br/>-> ground truth, asserted == intent"]
  end
  W --> M[("master/")]
  R --> I[("inbox/ + intake_manifest")]
  S --> SRC[("source/  (evaluation only)")]
  O --> GT[("ground_truth/  (evaluation only)")]
  subgraph ENG["engine (invoice_ap.engine)"]
    X["intake + extraction<br/>(adapter per channel, confidence)"] --> V["validation: vendor, PO, dates,<br/>arithmetic, tax"]
    V --> DUP["duplicate detection"] --> MT["three-way match<br/>(cumulative, tolerances)"]
    MT --> RT["routing to actor queues"] --> AP["approvals"] --> PY["payment readiness"]
  end
  M --> ENG
  I --> ENG
  ENG --> PR[("processed/ + events + decision traces")]
  PR --> EV["evaluation (invoice_ap.evaluation)"]
  GT --> EV
  SRC --> EV
  EV --> REP[("reports/ + dashboard")]
  M & I & SRC & GT & PR --> Q["validation suite<br/>(invoice_ap.quality)"] --> REP
  M & I & SRC & GT & PR --> XP["exports: CSV / JSON / SQL seed"]
```

The diagram shows the order of the engine's concerns. The exact check order and its gates are in
section 4.

## 2. Components and module boundaries

| Package | Responsibility | Reads | Writes | May import |
|---|---|---|---|---|
| `invoice_ap.common` | Vocabulary (`enums`), ID formats, Decimal money, paths, policy loader, doc sync. No business logic. | `config/ap_policy.toml` | - | stdlib only |
| `invoice_ap.spec` | Machine-readable data dictionary; renders `docs/data_dictionary.md` and the JSON spec. | - | docs | `common` |
| `invoice_ap.generator` | Exact allocation, synthetic world, true invoices, injections, document rendering, oracle (*Stage 2-3*). | policy | `master/`, `inbox/`, `source/`, `ground_truth/` | `common`, `spec` |
| `invoice_ap.engine` | Intake, extraction, validation, duplicates, matching, routing, approvals, payments, events, explain (*Stage 3-4*). | policy, `master/`, `inbox/` **only** | `processed/` | `common`, `spec` **only** |
| `invoice_ap.evaluation` | Extraction accuracy, per-type precision/recall/F1, confusion matrix, duplicate pairs, approval and payment safety, KPIs (*Stage 3-4*). | everything | `reports/evaluation.*` | all |
| `invoice_ap.quality` | Defect-aware validation suite: PK, FK, enums, date order, arithmetic, lifecycles, duplicates (*Stage 5*). | everything | `reports/validation_summary.*` | all but `engine` internals |
| `invoice_ap.export` | CSV and JSON for every table; SQL seed with PK/FK/CHECK constraints (*Stage 5*). | everything | `exports/` | `common`, `spec` |
| `invoice_ap.report` | Source manifest, distribution summary, reproducibility report, offline HTML dashboard (*Stage 5*). | everything | `reports/` | all |
| `invoice_ap.cli` | `python -m invoice_ap <command>` | - | - | all |

## 3. Dataset layout of one build

```
data/<scale>/                 scale = starter | full
  master/        ERP data, engine-readable: actor_role, app_user, payment_terms, tax_code, sku, vendor,
                 vendor_status_history, purchase_order, purchase_order_line, goods_receipt,
                 goods_receipt_line, erp_event  (*.csv)
  inbox/         engine-readable: intake_manifest.csv + documents/<channel>/<doc_id>.<ext>
  source/        EVALUATION ONLY: invoice.csv, invoice_line.csv (the invoices as issued)
  ground_truth/  EVALUATION ONLY: ground_truth.csv + ground_truth.json, ground_truth_line.csv
  processed/     engine output: captured_invoice, captured_invoice_line, extraction_field,
                 invoice_decision, match_result, match_allocation (bridge), duplicate_pair,
                 ap_exception, approval, payment, ap_event, policy_version (*.csv) + decision_trace.jsonl
  exports/       JSON for every table (json/<table>.json) + SQL seed (sql/seed.sql); the layer CSVs
                 above are the CSV export, so they are not copied again
  reports/       source_manifest.json, validation_summary.{json,md}, evaluation.{json,md},
                 distribution_summary.{json,md}, reproducibility.{json,md}, dashboard.html
```

The field-level definition of every table is in [data_dictionary.md](data_dictionary.md). Keys,
cardinalities and state machines are in [schema.md](schema.md).

## 4. Engine pipeline (*Stage 3-4*)

Invoices are processed one at a time in intake order (`received_at`, then `doc_id`). Each one uses
only the receipts posted before its processing time and only earlier invoices, so the engine
can never use information from the future.

```mermaid
flowchart TD
  A["RECEIVED: intake manifest row"] --> B["CAP-01 extract all fields with confidence"]
  B -->|"any required field < 0.90"| H1["EXT_LOW_CONFIDENCE -> ON_HOLD (capture review)"]
  B --> C["VEN-01 resolve vendor by tax registration number"]
  C -->|"not found"| H2["VENDOR_NOT_FOUND -> ON_HOLD"]
  C --> D["DUP-01..03 duplicate check vs all earlier documents"]
  D -->|"exact resubmission"| RJ["DUPLICATE_EXACT -> REJECTED"]
  D -->|"number reuse / same content"| H3["DUPLICATE_* -> ON_HOLD"]
  D --> E["collect every remaining issue:<br/>VEN-02/03 vendor status at invoice date<br/>PO-01/02 PO exists and belongs to vendor<br/>DATE-01/02, ARI-01/02, TAX-01..03<br/>PO-03 + MAT-01..04 line match (skipped if PO invalid)"]
  E --> F["MS-01 match status, PRI-01 primary issue,<br/>RTE-01 route every exception"]
  F -->|"any blocking issue"| H4["ON_HOLD in the owning role's queue"]
  F -->|"none"| G["APR-01 approval chain from the amount band"]
  G --> K["PAY-01 ready: no open blocking exception, all levels approved, vendor payable"]
  K --> L["PAY-02 schedule on the due date,<br/>PAY-05 release on or before the as-of date"]
```

Gates: a low-confidence capture stops further checks because the values cannot be trusted; a
detected duplicate stops matching so that it never consumes receipt quantity. After the gates the
engine collects every issue, not just the first one, so multi-issue invoices are labelled
completely and the primary status is chosen by the documented precedence.

Every state change is appended to `processed/ap_event.csv` with from/to status, timestamp, actor
role and id, rule id and policy version. `processed/decision_trace.jsonl` records each rule
evaluation (inputs, threshold, outcome), and `python -m invoice_ap explain <invoice_id>` renders it.

## 5. No-leakage design (non-negotiable)

| Mechanism | What it guarantees | Where |
|---|---|---|
| Layer separation | Evaluation-only data lives in `source/` and `ground_truth/`, never in `master/` or `inbox/`. | dataset layout |
| Narrow engine entry point | `run_engine(master_dir, inbox_dir, out_dir, policy)`: the engine is never given the dataset root. | `invoice_ap/engine` (*Stage 3*) |
| Static import rule | The engine imports only `common`, `spec` and itself, and `common` and `spec` import nothing from the generator. Evaluation-only names never appear in engine source. | `tests/test_boundary.py` (active now) |
| Runtime sandbox | The engine runs on a temp copy that contains only `master/` and `inbox/`; its output must be byte-identical to the normal run. | `tests/test_engine_sandbox.py` (*Stage 3*) |
| Label-free inputs | No master or inbox column has a label-like name; rendered documents contain no scenario codes or label words. | `tests/test_spec.py` (active now) + document scan (*Stage 3*) |
| Independent oracle | The oracle applies the documented rules to the true source data; generation asserts that its labels equal the injection intent and fails loudly otherwise. | `invoice_ap/generator/oracle.py` (*Stage 2*) |

Ground truth is produced by rules applied to true data (assignment rule 5), and the engine reproduces
it independently from extracted documents. Agreement between the two is therefore evidence, not a
tautology. The remaining limitation, that one author wrote both, is discussed in ADR-016.

## 6. Determinism and reproducibility

- One master seed (`--seed`, default `20261022`). Each concern gets its own `random.Random`
  sub-stream, seeded by `sha256(f"{seed}:{stream}")`, so adding draws to one stream never shifts another.
- Counts come from the exact allocation (`invoice_ap/generator/allocation.py`). The RNG only decides
  which PO, vendor, SKU or date gets each slot. Labels are never drawn at random.
- No wall clock. "Today" is `policy.as_of_date` (2026-12-31) and every timestamp is synthetic.
- Floats never touch money. Distributions use integer draws plus `Decimal` arithmetic (including
  `Decimal.exp` for log-normal values), never `math.exp` or `random.gauss`, whose results can differ
  across platforms. `tests/test_repo_hygiene.py` bans these calls.
- Iteration is always sorted. CSV output is UTF-8 with `\n` line endings and a fixed header order;
  JSON uses `sort_keys` and fixed separators; SQL statements are emitted in a fixed order.
- `.gitattributes` forces LF so the SHA-256 values recorded in `source_manifest.json` match on Windows checkouts too.
- `python -m invoice_ap repro` (*Stage 5*) builds twice with the same seed into separate folders,
  compares row counts and checksums, and runs a second seed as a sanity check.

## 7. Time model

All business dates fall in 2026, the year embedded in transactional IDs. POs are issued from
January to October, receipts follow category lead times, and invoices arrive until 24 December.
Timestamps are IST (`+05:30`). Business days skip weekends and the holidays listed in the policy.
SLA due dates, approval turnaround and payment scheduling all use business-day arithmetic.
Statuses called `*_as_of` are evaluated at 2026-12-31.

## 8. CLI surface

| Command | Purpose | Stage |
|---|---|---|
| `plan [--scale]` | Print the exact allocation tables | 1 (done) |
| `docs [--check]` | Regenerate the data dictionary, JSON spec and generated doc tables | 1 (done) |
| `policy [--path]` | Validate the policy and print a summary | 1 (done) |
| `generate --scale --seed` | Build master, inbox, source and ground truth | 2-3 |
| `run --scale` | Run the engine (master + inbox only) | 3-4 |
| `evaluate`, `explain <invoice_id>` | Metrics and per-invoice decision trace | 4 |
| `validate`, `export`, `repro`, `queue --role`, `dashboard` | Validation suite, exports, reproducibility, actor queues, HTML dashboard | 5 |
| `build-all` | One command that builds everything for both scales | 5 |

## 9. Performance and size budget

The full build must take well under a minute on a laptop. The approach is single-pass and in
memory, with indexed dictionaries and standard-library CSV, and no dataframe dependency. Preliminary
size estimate for the committed data: about 4 MB for the starter build and 30-45 MB for the full
build, dominated by per-field extraction evidence and JSON/SQL exports. Stage 5 measures the real
figures and, if needed, slims exports (for example compact JSON) rather than duplicating files.
