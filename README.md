# Invoice-to-Pay (AP) automation

Automates invoice intake, field extraction, PO/receipt matching, exception routing and payment
readiness on a reproducible, fully synthetic ERP dataset. A generator builds the ERP world
(vendors, POs, goods receipts) and renders every invoice as a document in one of four intake
channels. An independent engine then works only from master data and those documents. It extracts
fields, validates, detects duplicates, performs the three-way match, routes exceptions to the five
actors (business requester, process owner, approver, operations analyst, system administrator),
requests approvals and schedules payments. Its decisions are scored against a ground truth derived
by a documented rule-based oracle.

> **Status: Stage 5 of 6.** The specification, generator, document rendering, extraction engine,
> decision engine, evaluation, validation suite, exports, reproducibility check, role queues and
> offline dashboard are done, and the generated data is committed. Stage 6 is the hand-off
> (walkthrough, AI-use disclosure, final acceptance).

## Quickstart

Requires Python 3.11 or newer. The runtime uses the standard library only; `pytest` is needed only
for the tests. **The generated data is already committed under `data/`**, so the reports and the
dashboard can be opened without running anything.

macOS / Linux:

```bash
git clone <repo-url> invoice-ap-automation && cd invoice-ap-automation
python3 -m pip install -r requirements-dev.txt   # pytest only
python3 -m invoice_ap build-all                  # everything, both scales, + reproducibility check (~35 s)
python3 -m pytest                                # all tests, including committed data == fresh build
open data/full/reports/dashboard.html            # offline dashboard (any browser; no network needed)
```

Windows PowerShell:

```powershell
git clone <repo-url> invoice-ap-automation; cd invoice-ap-automation
py -m pip install -r requirements-dev.txt
py -m invoice_ap build-all
py -m pytest
start data\full\reports\dashboard.html
```

Step by step (each command takes `--scale starter|full` or `--data <folder>`):

| Command | What it does |
|---|---|
| `python -m invoice_ap plan --scale full` | Exact volume and scenario allocation |
| `python -m invoice_ap generate --scale full` | Master data, documents, source invoices, ground truth |
| `python -m invoice_ap run --scale full` | The AP engine, reading only `master/` and `inbox/` |
| `python -m invoice_ap evaluate --scale full` | Metrics vs ground truth, per-invoice acceptance |
| `python -m invoice_ap validate --scale full` | Full validation suite over every table (`--quick`: generator self-checks) |
| `python -m invoice_ap export --scale full` | JSON for every table, `seed.sql` and `evaluation_seed.sql` |
| `python -m invoice_ap dashboard --scale full` | `reports/dashboard.html` |
| `python -m invoice_ap build --scale full` | All of the above for one scale, plus the source manifest |
| `python -m invoice_ap repro --scale starter` | Rebuild twice (two hash seeds) and once with another seed, and compare checksums |
| `python -m invoice_ap queue --role OPERATIONS_ANALYST --scale full` | One actor's open work queue (all five roles without `--role`) |
| `python -m invoice_ap explain INV-VND-00279-2026-000032 --scale full` | One invoice's decision, exceptions, events and trace |
| `python -m invoice_ap policy` / `docs --check` | Validate the policy file / check generated docs |

## What to open first

| File (in `data/full/` or `data/starter/`) | Contents |
|---|---|
| `reports/dashboard.html` | KPIs, the five actors' queues, invoice explorer with decision traces, evaluation, validation |
| `reports/evaluation.md` | Agreement with ground truth, per-type precision/recall/F1, confusion, duplicates, approvals, payments, KPIs with definitions, backlog, per-invoice acceptance |
| `reports/acceptance_per_invoice.csv` | R34a-e pass/fail for every invoice |
| `reports/extraction_evaluation.md` | Field, channel and document accuracy of extraction; every mismatch |
| `reports/validation_summary.md` | The full validation suite over every table |
| `reports/reproducibility.md` | Two rebuilds compared file by file, plus another seed |
| `reports/source_manifest.json` | Every file with rows, bytes, SHA-256, commit flag, provenance and licences |
| `reports/distribution_summary.md` | Realised distributions (Evaluation Focus a) |
| `exports/sql/seed.sql`, `exports/sql/evaluation_seed.sql` | SQLite-ready DDL (PK/FK/CHECK) and data; load the seed first |

## Committed data and size budget

`data/starter/` is committed complete. `data/full/` is committed except four regenerable groups that
would push the repository past about 25 MB (REV ruling Q3 and Stage-4 ruling 1):
`exports/json/`, `exports/sql/`, `processed/decision_trace.jsonl` and `processed/extraction_field.csv`.
`python -m invoice_ap build-all` regenerates them, and their SHA-256 values are in
`data/full/reports/source_manifest.json`. `tests/test_outputs.py::test_committed_data_equals_a_fresh_build`
rebuilds both scales and checks every committed file byte for byte and every excluded file against
its recorded checksum. `.gitattributes` forces LF, so the checksums hold on Windows checkouts too.

## Known limitations

- Every business event (PO, receipt, invoice date, intake) falls on a business day. This is a
  simplification (S2-R1-02); SLA, approval and payment arithmetic use business days either way.
- Eight exception types do not occur in the generated data: the seven of ADR-036 and the
  non-blocking `PAYMENT_DUE_DATE_PASSED`. Each is covered by a test fixture through the engine
  (`tests/test_decisions.py`) and reported as "not present" in the per-type metrics.
- Approver rejection exists in the state machine but is not simulated: simulated approvers approve
  after a fixed turnaround (ADR-011).
- No exception resolutions are simulated, so almost every open exception is "open and past SLA at the
  snapshot". The evaluation and the dashboard show this backlog honestly, aged in business days
  (<= 5, 6-20, > 20), instead of inventing human decisions.
- Engine and oracle were written by the same author; agreement is evidence of a consistent
  implementation of the documented rules, not of independent judgement (ADR-016, ADR-041).

## Configure

| What | Where | Default |
|---|---|---|
| Business rules, tolerances, routing, approval and payment policy | [`config/ap_policy.toml`](config/ap_policy.toml) (versioned; every decision records its version) | `AP-POLICY` 1.0.0 |
| Random seed | `--seed` | `20261022` |
| Scale | `--scale starter\|full\|<factor>` | starter = 1/10 of full |

## Documentation

| Document | Contents |
|---|---|
| [docs/architecture.md](docs/architecture.md) | Components, data flow, module boundaries, no-leakage design, determinism |
| [docs/schema.md](docs/schema.md) | ERD, keys, cardinality, optional relationships, effective dates, state machines |
| [docs/data_dictionary.md](docs/data_dictionary.md) | Every field of every table (generated from `invoice_ap/spec`; JSON copy in `invoice_ap/spec/data_dictionary.json`) |
| [docs/business_rules.md](docs/business_rules.md) | Rule catalogue, tolerances and why, precedence, routing and approval matrices, payment readiness |
| [docs/data_generation.md](docs/data_generation.md) | Generation order, exact allocation at both scales, distributions, injections, ground truth |
| [docs/evaluation_plan.md](docs/evaluation_plan.md) | Metrics, acceptance criteria, Evaluation Focus (a)-(g) mapping |
| [docs/requirements_traceability.md](docs/requirements_traceability.md) | Every requirement -> implementation -> evidence |
| [docs/assumptions_and_decisions.md](docs/assumptions_and_decisions.md) | ADRs: ambiguities resolved, alternatives, trade-offs |

## Repository map

```
config/ap_policy.toml      versioned AP policy (TOML, read with tomllib)
invoice_ap/common/         vocabulary, IDs, Decimal money, lifecycles, policy loader (no business logic)
invoice_ap/spec/           machine-readable data dictionary + renderers
invoice_ap/generator/      allocation, world, planner, documents, oracle, writer
invoice_ap/engine/         AP engine; may read only master data and the inbox
invoice_ap/evaluation/     extraction and decision metrics vs ground truth, per-invoice acceptance
invoice_ap/quality/        quick self-checks and the full validation suite
invoice_ap/export/         JSON exports and the SQL seeds
invoice_ap/report/         manifest, distributions, queues, dashboard
invoice_ap/orchestrate.py  build, build-all and repro
data/starter, data/full    the committed generated datasets (see "Committed data and size budget")
tests/                     pytest suite
docs/                      design documents
```

## Data provenance

All data is synthetic and generated by this code from a fixed seed. No external dataset is used.
Names, tax registration numbers and e-mail addresses are synthetic (reserved `.example` and
`example.com` domains), and users are role labels rather than people.

## AI usage disclosure

This project was built with AI assistance. The full prompt history, the review trail and the
candidate's own statement of what they personally reviewed, changed and validated will be in
`ai_disclosure/` (Stage 6).

> **[CANDIDATE TO COMPLETE]** Personal statement of review and validation. Not written by AI.

## Licence

MIT, see [LICENSE](LICENSE).
