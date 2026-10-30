# Invoice-to-Pay (AP) automation

Automates invoice intake, field extraction, PO/receipt matching, exception routing and payment
readiness on a reproducible, fully synthetic ERP dataset. A generator builds the ERP world
(vendors, POs, goods receipts) and renders every invoice as a document in one of four intake
channels. An independent engine then works only from master data and those documents. It extracts
fields, validates, detects duplicates, performs the three-way match, routes exceptions to the five
actors (business requester, process owner, approver, operations analyst, system administrator),
requests approvals and schedules payments. Its decisions are scored against a ground truth derived
by a documented rule-based oracle.

> **Status: Stage 3 of 6.** Stage 1 (the specification, the policy, the data dictionary and the
> exact allocation), Stage 2 (the synthetic data generator, the rule-based ground truth and the
> self-checks) and Stage 3 (document rendering in four channel formats, extraction with per-field
> confidence, vendor resolution and the extraction evaluation) are done. The decision engine and its
> evaluation (Stage 4), and the validation suite, exports and dashboard (Stage 5) follow. This README
> grows each stage.

## Quickstart (works today)

Requires Python 3.11 or newer. The runtime uses the standard library only; `pytest` is needed only
for the tests.

macOS / Linux:

```bash
git clone <repo-url> invoice-ap-automation && cd invoice-ap-automation
python3 -m pip install -r requirements-dev.txt   # pytest only
python3 -m pytest                                # all tests
python3 -m invoice_ap plan --scale starter       # exact volume and mix allocation (both scales)
python3 -m invoice_ap generate --scale full       # synthetic dataset + documents -> data/full (about 3 s)
python3 -m invoice_ap validate --quick --scale full   # defect-aware self-checks
python3 -m invoice_ap run --scale full            # engine: master + inbox only -> data/full/processed
python3 -m invoice_ap evaluate --scale full       # extraction accuracy -> data/full/reports
python3 -m invoice_ap policy                     # validate config/ap_policy.toml
python3 -m invoice_ap docs --check               # generated docs are in sync with code
```

Windows PowerShell:

```powershell
git clone <repo-url> invoice-ap-automation; cd invoice-ap-automation
py -m pip install -r requirements-dev.txt
py -m pytest
py -m invoice_ap plan --scale starter
py -m invoice_ap generate --scale full
py -m invoice_ap validate --quick --scale full
py -m invoice_ap run --scale full
py -m invoice_ap evaluate --scale full
py -m invoice_ap policy
py -m invoice_ap docs --check
```

The remaining commands (`export`, `repro`, `queue`,
`explain`, `dashboard`, `build-all`) are registered. Until their stage lands they exit with status 2
and a "planned" message. See [architecture §8](docs/architecture.md#8-cli-surface).

## Known limitations (so far)

- Every business event (PO, receipt, invoice date, intake) falls on a business day. This is a
  simplification (S2-R1-02); SLA, approval and payment arithmetic use business days either way.
- Eight exception types do not occur in the generated data: the seven of ADR-036 and the
  non-blocking `PAYMENT_DUE_DATE_PASSED`. Stage 4 covers them with unit fixtures and reports them as
  "not present" in the per-type metrics.
- Stage 3 runs only the capture-stage rules (CAP-01, VEN-01, ID-01, VEN-04); the remaining rules
  arrive in Stage 4.

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
invoice_ap/generator/      exact allocation + scenario catalogue (world, documents, oracle: Stage 2-3)
invoice_ap/engine/         AP engine (Stage 3-4); may read only master data and the inbox
invoice_ap/evaluation/     metrics vs ground truth (Stage 3-4)
invoice_ap/quality/        validation suite (Stage 5)
invoice_ap/export/         CSV / JSON / SQL seed (Stage 5)
invoice_ap/report/         manifest, distributions, reproducibility, dashboard (Stage 5)
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
