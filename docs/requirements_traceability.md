# Requirements traceability matrix

Requirement IDs come from the sprint checklist, which was extracted from the assignment text
(problem statement, YottaFlex guidelines and FAQ).

Status values:
- **done**: implemented, with the evidence linked;
- **designed**: specified in the docs, with implementation planned for the listed stage;
- **planned**: not started.

Each later stage updates this file with concrete evidence.

## Problem statement

| ID | Requirement | Implementation (planned location) | Evidence (planned) | Stage | Status |
|---|---|---|---|---|---|
| R1 | End-to-end: intake -> extraction -> PO/receipt matching -> exception routing -> payment readiness | `invoice_ap/generator`, `invoice_ap/engine`, `python -m invoice_ap build-all` | end-to-end test; `reports/evaluation.md` | 2-5 | designed ([architecture](architecture.md)) |
| R2 | Expose key decisions and exceptions | `invoice_decision`, `ap_exception`, `decision_trace.jsonl`, `explain`, dashboard | explain output; dashboard | 4-5 | designed |
| R3 | Preserve traceability | rule IDs + `policy_version` on every decision, exception, approval, payment and event; `policy_version.sha256` | validation check "every decision has rule and policy version" | 4-5 | designed ([business_rules](business_rules.md)) |
| R4 | Measurable outputs | `invoice_ap/evaluation` | `reports/evaluation.{json,md}` | 3-4 | designed ([evaluation_plan](evaluation_plan.md)) |
| R5 | Medium complexity: related entities, conditional rules, >= 1 exception path, metrics | 29 tables, 23 exception types, gates and precedence, E1-E15 | data dictionary; evaluation report | 1-4 | designed |
| R6 | Five actors explicit in data, routing, approvals, administration | `actor_role`, `app_user`, routing matrix, approval levels, policy owner and maintainer roles | `tests/test_policy.py::test_all_five_actors_have_work`; queue CLI | 1, 5 | done (spec and policy); queue CLI planned |
| R7 | Master data generated first | generation order ([data_generation §3](data_generation.md)) | generator order test | 2 | designed |
| R8 | Dependent records use valid parent IDs | FK spec; validation suite | `tests/test_spec.py` FK tests; FK checks | 1, 5 | done (spec); data check planned |
| R9a | Vendors first | generation step 2 | generator test | 2 | designed |
| R9b | POs reference vendors | `purchase_order.vendor_id` FK | FK check | 1, 5 | done (spec) |
| R9c | 1-8 PO lines with SKU, quantity, unit price, tax code | `purchase_order_line`; exact line histogram | `tests/test_allocation.py`; data check | 1-2 | done (allocation) |
| R9d | Receipts reference PO lines; full, partial and over-receipt | `goods_receipt_line.po_line_id`, `receipt_type`; archetypes A11/A22/A33/A21/A10 | distribution summary; receipt-type counts | 1-2 | designed |
| R9e | Invoices reference vendor and optionally PO | `invoice.vendor_id`, nullable `po_id`; 5% non-PO | data check | 1-2 | designed |
| R9f | Line totals, tax and grand total from lines | derived fields in the spec; `invoice_ap/common/money.py` | `tests/test_ids_and_money.py`; recomputation check | 1, 5 | done (helpers + spec) |
| R9g | Match status from price / quantity / tax tolerances | MS-01; `[matching]`, `[tax]` policy | engine tests; E5 | 4 | designed |
| R9h | Approval and payment records only for eligible invoices | APR-01, PAY-01 | engine tests; E8, E9 (R34e) | 4 | designed |
| R10 | State changes as explicit events; history never overwritten | `vendor_status_history`, `erp_event`, `ap_event`; `invoice_ap/common/lifecycle.py` | lifecycle validation | 1, 2, 4, 5 | done (state machines); events planned |
| R11 | Labels from documented rules, not random | catalogue intent + oracle; generation asserts oracle == intent | `test_oracle_matches_intent` | 2 | designed |
| R12 | Nine core entities | spec tables | `tests/test_spec.py::test_every_core_entity_has_exactly_one_table` | 1 | done |
| R13 | PK for every entity, FK for every relationship | spec; SQL DDL constraints | `tests/test_spec.py`; SQLite `foreign_key_check` | 1, 5 | done (spec) |
| R14 | Cardinality, optional relationships, effective dates, lifecycle states | [schema.md](schema.md) | doc review | 1 | done |
| R15 | Bridge tables for N:M | `match_allocation` (invoice line <-> GRN line) | spec test; allocation data | 1, 4 | done (spec) |
| R16 | Event history retained | append-only event tables | lifecycle validation | 2-5 | designed |
| R17 | All joins validated | [schema §9](schema.md#9-join-validation-implemented-in-stage-5) | `validation_summary` | 5 | designed |
| R18 | Anomalies labelled; unrelated rows not corrupted | injection mechanics ([data_generation §6](data_generation.md)); ground truth | baseline-vs-injected diff test | 2 | designed |
| R19 | ID conventions; zero-padded; immutable; consistent across files | `invoice_ap/common/ids.py` | `tests/test_ids_and_money.py`; pattern and embedded-ID checks | 1, 5 | done (formats) |
| R20 | Data dictionary for the nine entities (type, required, allowed, unit, unique, rule) | [data_dictionary.md](data_dictionary.md) + `invoice_ap/spec/data_dictionary.json` | `tests/test_spec.py` | 1 | done |
| R21 | Parent tables first, then child and event tables | generation order | generator test | 2 | designed |
| R22 | Deterministic IDs | counters in intake / creation order | reproducibility report | 2, 5 | designed |
| R23 | 300 / 1,500 / 2,200 / 1,800 / 2,000 | `invoice_ap/generator/allocation.py` | `tests/test_allocation.py`; generated counts | 1-2 | done (allocation) |
| R24 | Mix ~70 / 10 / 8 / 5 / 4 / 3 | catalogue + allocation (Table G2) | `test_full_scale_mix_is_exact`; E12 | 1, 4 | done (allocation) |
| R25 | FKs valid except labelled defects | all declared FKs valid by design (ADR-035) | validation suite | 5 | designed |
| R26 | Fixed seed 20261022 | `--seed` default | source manifest | 2 | designed |
| R27 | Parameterised scale; same generator for starter and full | `parse_scale`, one code path | `tests/test_allocation.py` (5 scales) | 1-2 | done (allocation) |
| R28a | Duplicate invoice number | DUP-NUMBER-REUSE (EC-01) | Table G7; E6 | 1-2, 4 | done (allocation) |
| R28b | Invoice total differs from line sum | ARITH-HEADER-TOTAL (EC-02) | Table G7; E3 | 1-2, 4 | done (allocation) |
| R28c | Invoice date before PO date | DATE-INVOICE-BEFORE-PO (EC-03) | Table G7; E3 | 1-2, 4 | done (allocation) |
| R28d | Partial delivery | C-PARTIAL-OPEN, C-SPLIT-PARTIAL, C-CONSOLIDATED, QM-PARTIAL-BILLED-FULL (EC-04) | Table G7 | 1-2, 4 | done (allocation) |
| R28e | Closed vendor | TV-CLOSED (EC-05) | Table G7 | 1-2, 4 | done (allocation) |
| R28f | Tax mismatch | TV-TAX-CODE, TV-TAX-AMOUNT, TV-NPO-TAX-AMOUNT (EC-06) | Table G7 | 1-2, 4 | done (allocation) |
| R28g | Invoice exceeds PO quantity | QM-EXCEEDS-PO-* , QM-BOUNDARY-OUT (EC-07) | Table G7 | 1-2, 4 | done (allocation) |
| R28h | Same invoice submitted twice | DUP-EXACT, DUP-EXACT-NORMALIZED, DUP-EXACT-NPO, DUP-CONTENT (EC-08) | Table G7; E6 | 1-2, 4 | done (allocation) |
| R29 | Derived values computed from source records | spec `derivation` for every derived field | `tests/test_spec.py`; recomputation check | 1, 5 | done (spec) |
| R30 | Separate ground_truth.csv/.json; no leakage | `ground_truth/` layer; boundary tests | `tests/test_boundary.py` (static, now); runtime sandbox test | 1-3 | done (static); runtime planned |
| R31 | Validation: PK, FK, enums, date order, arithmetic, lifecycle, duplicates | `invoice_ap/quality` | `validation_summary.{json,md}` | 5 | designed |
| R32 | CSV / JSON / SQL seed + README, dictionary, command, seed, manifest, validation summary | `invoice_ap/export`, `invoice_ap/report` | `exports/`, `reports/` | 5 | designed |
| R33 | Regenerate twice; compare row counts and checksums | `python -m invoice_ap repro` | `reproducibility.{json,md}` | 5 | designed |
| R34a-e | Per-invoice acceptance | [evaluation_plan §1, §3](evaluation_plan.md) | per-invoice acceptance check on all invoices | 3-4 | designed |
| R35a-g | Evaluation Focus | [evaluation_plan §4](evaluation_plan.md#4-evaluation-focus-a-g---evidence) | as listed there | 2-5 | designed |
| R36 | Lawful provenance | 100% synthetic, no external data (ADR-027) | `source_manifest.json` provenance block | 5 | designed |
| R37 | Public GitHub repo, README on how to run, tests | README, `tests/` | README quickstart; `pytest` | 1, 6 | partial (README stub, tests); publishing by the candidate |

## Submission guidelines and FAQ

| ID | Requirement | Implementation (planned location) | Evidence (planned) | Stage | Status |
|---|---|---|---|---|---|
| G1 | Install, configure, run and verify steps | README quickstart (PowerShell + macOS/Linux) | fresh-clone audit | 6 | partial (stub) |
| G2 | Public repo, meaningful commits, visible evolution | one commit per stage and fix round | `git log` | 1-6 | in progress |
| G3 | Prompt history and AI-use explanation; the candidate's own statement | `ai_disclosure/AI_USAGE.md`, `prompt_history/`, `sprint_reviews/` | files; candidate placeholders, never invented | 6 | planned |
| G4 | Reasoning visible: assumptions, decisions, trade-offs, testing, limitations | [assumptions_and_decisions.md](assumptions_and_decisions.md), testing approach doc | docs | 1, 6 | done (ADRs); testing doc planned |
| G5 | Walkthrough readiness | `docs/walkthrough.md` | doc | 6 | planned |
| G6 | Prompt history in a clearly identifiable directory | `ai_disclosure/` | directory | 6 | planned |
| G7 | Free, local, light dependencies | stdlib runtime, pytest for dev only | `tests/test_repo_hygiene.py` | 1 | done |
| G8 | Environment needs, limitations, verification | README sections | doc | 6 | planned |
| G9 | No imported complete solutions; licences respected | own code, MIT licence, no runtime dependencies | LICENSE; hygiene test | 1 | done |
| G10 | Assumptions and deviations explained; what is incomplete; next steps | ADRs; README limitations | docs | 1, 6 | done (ADRs) |
| G11 | No secrets, credentials, personal or sensitive data | synthetic names, role labels, reserved domains (ADR-027) | secret/PII scan test | 6 | designed |
