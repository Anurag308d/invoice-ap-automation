# Requirements traceability matrix

Every requirement of the assignment (problem statement, guidelines and FAQ) is listed with where it
is implemented and the file, test or report that proves it. Reports are in `data/full/reports/` and
`data/starter/reports/` (committed); tests are under `tests/`. IDs such as S1-R1-01 or A-26 are
provenance notes from the independent review (see `ai_disclosure/sprint_reviews/`); nothing below
depends on them.

## Problem statement

| ID | Requirement | Implementation | Evidence | Status |
|---|---|---|---|---|
| R1 | End-to-end: intake -> extraction -> PO/receipt matching -> exception routing -> payment readiness | `invoice_ap/generator`, `invoice_ap/engine`, `python -m invoice_ap build-all` | end-to-end test; `reports/evaluation.md` | done: `python -m invoice_ap build-all` builds both scales end to end and checks reproducibility |
| R2 | Expose key decisions and exceptions | `invoice_decision`, `ap_exception`, `decision_trace.jsonl`, `explain`, dashboard | explain output; dashboard | done |
| R3 | Preserve traceability | rule IDs + `policy_version` on every decision, exception, approval, payment and event; `policy_version.sha256` | validation check "every decision has rule and policy version" | done: rule IDs and `policy_version` on every decision, exception, approval, payment and event; `processed/policy_version.csv` carries the policy SHA-256; validator checks state machines |
| R4 | Measurable outputs | `invoice_ap/evaluation` | `reports/evaluation.{json,md}` | done: `invoice_ap/evaluation/{extraction,decisions}.py` -> `reports/extraction_evaluation.*`, `reports/evaluation.*`, `reports/acceptance_per_invoice.csv` |
| R5 | Medium complexity: related entities, conditional rules, >= 1 exception path, metrics | 29 tables, 24 exception types, gates and precedence, E1-E15 | data dictionary; evaluation report | done: 24 exception types (16 in data, 8 by fixtures), gates, precedence, metrics |
| R6 | Five actors explicit in data, routing, approvals, administration | `actor_role`, `app_user`, routing matrix, approval levels, policy owner and maintainer roles | `tests/test_policy.py::test_all_five_actors_have_work`; queue CLI | done: `python -m invoice_ap queue --role <ROLE>` for all five actors; dashboard queue tabs; `test_every_actor_has_a_queue` |
| R7 | Master data generated first | generation order ([data_generation §3](data_generation.md)) | `tests/test_generator.py::test_exact_volumes`; generation order in `generator/build.py` | done |
| R8 | Dependent records use valid parent IDs | FK spec; validation suite | quick check "foreign keys (every declared FK)": 0 orphans; `tests/test_generator.py::test_self_checks_pass_and_the_baseline_is_clean` | done |
| R9a | Vendors first | generation step 2 | `generator/world.py` vendors before `generator/planner.py` POs | done |
| R9b | POs reference vendors | `purchase_order.vendor_id` FK | FK check 0 orphans | done |
| R9c | 1-8 PO lines with SKU, quantity, unit price, tax code | `purchase_order_line`; exact line histogram | `tests/test_generator.py::test_exact_volumes` (1-8 lines); histogram in `reports/distribution_summary.md` | done |
| R9d | Receipts reference PO lines; full, partial and over-receipt | `goods_receipt_line.po_line_id`, `receipt_type`; archetypes A11/A22/A33/A21/A10 | receipt types PARTIAL/FULL/OVER derived; `tests/test_generator.py::test_over_receipt_beyond_tolerance_only_in_labelled_scenarios` | done |
| R9e | Invoices reference vendor and optionally PO | `invoice.vendor_id`, nullable `po_id`; 5% non-PO | 5% non-PO (`C-NPO-*`, `TV-NPO-TAX-AMOUNT`); nullable `invoice.po_id` | done |
| R9f | Line totals, tax and grand total from lines | derived fields in the spec; `invoice_ap/common/money.py` | quick check "arithmetic"; `tests/test_generator.py::test_totals_recompute_from_lines_except_labelled_defects` | done |
| R9g | Match status from price / quantity / tax tolerances | MS-01; `[matching]`, `[tax]` policy | engine tests; E5 | done: `engine/validate.py::match_status`; line and invoice match status agree 100% with ground truth (`tests/test_decisions.py`) |
| R9h | Approval and payment records only for eligible invoices | APR-01, PAY-01 | engine tests; E8, E9 (R34e) | done: approvals only without open blocking issues, payments only when ready; 0 unsafe payments (`test_payments_only_for_unblocked_fully_approved_invoices`) |
| R10 | State changes as explicit events; history never overwritten | `vendor_status_history`, `erp_event`, `ap_event`; `invoice_ap/common/lifecycle.py` | `vendor_status_history`, `erp_event`; quick check "lifecycle events" (state machines, current = last event) | done |
| R11 | Labels from documented rules, not random | catalogue intent + oracle; generation asserts oracle == intent | oracle in `generator/oracle.py`; `tests/test_generator.py::test_oracle_labels_equal_intent_and_clean_means_no_issue`, `::test_generation_fails_loudly_when_an_injection_misses_its_label` | done |
| R12 | Nine core entities | spec tables | `tests/test_spec.py::test_every_core_entity_has_exactly_one_table` | done |
| R13 | PK for every entity, FK for every relationship | spec; SQL DDL constraints | `tests/test_spec.py`; SQLite `foreign_key_check` | done |
| R14 | Cardinality, optional relationships, effective dates, lifecycle states | [schema.md](schema.md) | doc review | done |
| R15 | Bridge tables for N:M | `match_allocation` (invoice line <-> GRN line), exercised both ways: A21 (1 invoice line -> 2 GRN lines) and A12 (1 GRN line -> 2 invoice lines) | `tests/test_allocation.py::test_many_to_many_bridge_is_exercised_in_both_directions`; `tests/test_decisions.py::test_bridge_is_exercised_in_both_directions` | done |
| R16 | Event history retained | append-only event tables | append-only `vendor_status_history` and `erp_event` (sequence-checked) | done |
| R17 | All joins validated | [schema §9](schema.md#9-join-validation) | `validation_summary` | done: every declared FK checked by the validation suite and enforced by SQLite (`foreign_key_check` clean); polymorphic event references checked |
| R18 | Anomalies labelled; unrelated rows not corrupted | injection mechanics ([data_generation §6](data_generation.md)); ground truth | `tests/test_generator.py::test_injections_do_not_touch_unrelated_rows`; quick checks report labelled defects apart from violations | done |
| R19 | ID conventions; zero-padded; immutable; consistent across files | `invoice_ap/common/ids.py` | `tests/test_ids_and_money.py`; pattern and embedded-ID checks | done |
| R20 | Data dictionary for the nine entities (type, required, allowed, unit, unique, rule) | [data_dictionary.md](data_dictionary.md) + `invoice_ap/spec/data_dictionary.json` | `tests/test_spec.py` | done |
| R21 | Parent tables first, then child and event tables | generation order | `generator/build.py`: reference -> vendors -> POs -> GRNs -> invoices -> events | done |
| R22 | Deterministic IDs | counters in intake / creation order | `tests/test_generator.py::test_same_seed_gives_identical_files`, `::test_output_does_not_depend_on_pythonhashseed` | done |
| R23 | 300 / 1,500 / 2,200 / 1,800 / 2,000 | `invoice_ap/generator/allocation.py` | `tests/test_generator.py::test_exact_volumes` (both scales) | done |
| R24 | Mix ~70 / 10 / 8 / 5 / 4 / 3 | catalogue + allocation (Table G2) | `tests/test_generator.py::test_mix_matches_the_allocation` (CLEAN 1,350, CAPTURE_REVIEW 10) | done |
| R25 | FKs valid except labelled defects | all declared FKs valid by design (ADR-035) | FK check 0 orphans at both scales (all declared FKs valid, ADR-035) | done |
| R26 | Fixed seed 20261022 | `--seed` default | `--seed` default 20261022; recorded in `reports/source_manifest.json` | done |
| R27 | Parameterised scale; same generator for starter and full | `parse_scale`, one code path | one code path; `tests/test_generator.py::test_another_seed_changes_the_data_but_not_the_counts` | done |
| R28a | Duplicate invoice number | DUP-NUMBER-REUSE (EC-01) | `tests/test_generator.py::test_edge_cases_are_present` (>= 10 full, >= 1 starter); oracle == intent | done |
| R28b | Invoice total differs from line sum | ARITH-HEADER-TOTAL (EC-02) | `tests/test_generator.py::test_edge_cases_are_present` (>= 10 full, >= 1 starter); oracle == intent | done |
| R28c | Invoice date before PO date | DATE-INVOICE-BEFORE-PO (EC-03) | `tests/test_generator.py::test_edge_cases_are_present` (>= 10 full, >= 1 starter); oracle == intent | done |
| R28d | Partial delivery | C-PARTIAL-OPEN, C-SPLIT-PARTIAL, C-CONSOLIDATED, QM-PARTIAL-BILLED-FULL (EC-04) | `tests/test_generator.py::test_edge_cases_are_present` (>= 10 full, >= 1 starter); oracle == intent | done |
| R28e | Closed vendor | TV-CLOSED (EC-05) | `tests/test_generator.py::test_edge_cases_are_present` (>= 10 full, >= 1 starter); oracle == intent | done |
| R28f | Tax mismatch | TV-TAX-CODE, TV-TAX-AMOUNT, TV-NPO-TAX-AMOUNT (EC-06) | `tests/test_generator.py::test_edge_cases_are_present` (>= 10 full, >= 1 starter); oracle == intent | done |
| R28g | Invoice exceeds PO quantity | QM-EXCEEDS-PO-* , QM-BOUNDARY-OUT (EC-07) | `tests/test_generator.py::test_edge_cases_are_present` (>= 10 full, >= 1 starter); oracle == intent | done |
| R28h | Same invoice submitted twice | DUP-EXACT, DUP-EXACT-NORMALIZED, DUP-EXACT-NPO, DUP-CONTENT (EC-08) | `tests/test_generator.py::test_edge_cases_are_present` (>= 10 full, >= 1 starter); oracle == intent | done |
| R29 | Derived values computed from source records | spec `derivation` for every derived field | derived columns recomputed by the quick arithmetic check | done |
| R30 | Separate ground_truth.csv/.json; no leakage | `ground_truth/` layer; no `invoice_id` in the manifest, sender vendor only for PORTAL/EDI (ADR-037); reporting-only `snapshot_*` columns (ADR-038); evaluation exports in separate files | `tests/test_boundary.py` (imports, sender/ID/snapshot bans), `tests/test_spec.py` (label-free inputs, manifest, snapshot flags); `tests/test_engine_sandbox.py` (blind run byte-identical, ID-blind run identical decisions; done); time-travel sandbox | done: static bans, runtime sandboxes and time-travel tests (`tests/test_boundary.py`, `tests/test_engine_sandbox.py`, `tests/test_decisions.py`) |
| R31 | Validation: PK, FK, enums, date order, arithmetic, lifecycle, duplicates | `invoice_ap/quality` | `validation_summary.{json,md}` | done: `quality/suite.py` -> `reports/validation_summary.{json,md}`; 16 checks pass at both scales; 5 injected faults detected (`test_validation_suite_catches_injected_faults`) |
| R32 | CSV / JSON / SQL seed + README, dictionary, command, seed, manifest, validation summary | `invoice_ap/export`, `invoice_ap/report` | `exports/`, `reports/` | done: layer CSVs, `exports/json/`, `exports/sql/seed.sql` + `evaluation_seed.sql`, manifest, validation summary; `test_sql_seed_loads_with_foreign_keys_and_keeps_labels_separate` |
| R33 | Regenerate twice; compare row counts and checksums | `python -m invoice_ap repro` | `reproducibility.{json,md}` | done: `python -m invoice_ap repro`; `reports/reproducibility.md` (274/274 and 2,074/2,074 files identical; other seed differs) |
| R34a-e | Per-invoice acceptance | [evaluation_plan §1, §3](evaluation_plan.md) | per-invoice acceptance check on all invoices | done: `reports/acceptance_per_invoice.csv`; 2,000/2,000 pass at full scale (10 flagged for capture review as designed); `test_engine_agrees_with_ground_truth_on_every_invoice` |
| R35a-g | Evaluation Focus | [evaluation_plan §4](evaluation_plan.md#4-evaluation-focus-a-g---evidence) | as listed there | done: mapped in evaluation_plan section 4; evidence in `reports/` of the committed data |
| R36 | Lawful provenance | 100% synthetic, no external data (ADR-027) | `source_manifest.json` provenance block | done: manifest provenance and licences; synthetic names, `.example` domains, invented tax numbers |
| R37 | Public GitHub repo, README on how to run, tests | README, `tests/` | README quickstart; `pytest` | done: README quickstart and verification; `python -m pytest` (541+ tests); publishing the repository is the candidate's step |

## Submission guidelines and FAQ

| ID | Requirement | Implementation | Evidence | Status |
|---|---|---|---|---|
| G1 | Install, configure, run and verify steps | README quickstart (PowerShell + macOS/Linux) | fresh-clone audit | done: README "Quickstart" and "How to verify" (macOS/Linux and PowerShell) |
| G2 | Public repo, meaningful commits, visible evolution | one commit per stage and fix round | `git log` | done: one commit per build stage and review fix round (`git log`) |
| G3 | Prompt history and AI-use explanation; the candidate's own statement | `ai_disclosure/AI_USAGE.md`, `prompt_history/`, `sprint_reviews/` | files; candidate placeholders, never invented | done: `ai_disclosure/AI_USAGE.md`; the candidate's own statement is a marked placeholder for them to complete |
| G4 | Reasoning visible: assumptions, decisions, trade-offs, testing, limitations | [assumptions_and_decisions.md](assumptions_and_decisions.md), testing approach doc | docs | done: [assumptions_and_decisions.md](assumptions_and_decisions.md), [testing_and_verification.md](testing_and_verification.md), README limitations |
| G5 | Walkthrough readiness | `docs/walkthrough.md` | doc | done: [walkthrough.md](walkthrough.md) |
| G6 | Prompt history in a clearly identifiable directory | `ai_disclosure/` | directory | done: `ai_disclosure/` (prompt history and review evidence) |
| G7 | Free, local, light dependencies | stdlib runtime, pytest for dev only | `tests/test_repo_hygiene.py` | done |
| G8 | Environment needs, limitations, verification | README sections | doc | done: README "Quickstart", "How to verify", "Limitations and next steps" |
| G9 | No imported complete solutions; licences respected | own code, MIT licence, no runtime dependencies | LICENSE; hygiene test | done |
| G10 | Assumptions and deviations explained; what is incomplete; next steps | ADRs; README limitations | docs | done (ADRs) |
| G11 | No secrets, credentials, personal or sensitive data | synthetic names, role labels, reserved domains (ADR-027) | secret/PII scan test | done: `tests/test_repo_hygiene.py::test_no_secrets_or_personal_data_in_tracked_files` |

## REV-added acceptance items (ACCEPTANCE_CHECKLIST §C.2)

| A-item | What REV added | Implementation | Evidence | Status |
|---|---|---|---|---|
| A-10 | Non-circular evaluation; engine boundary; **blind run** | engine reads only `master/` and `inbox/`; oracle separate | `tests/test_boundary.py`; `tests/test_engine_sandbox.py::test_blind_run_is_byte_identical` (copy without `source/` and `ground_truth/`, outputs byte-identical) and `::test_id_blind_run_gives_identical_decisions` (sender fields blanked) | done (static and both sandboxes, ) |
| A-50 | No vendor shortcut through `invoice_id` or the sender; ground truth out of the SQL seed's input tables; blind run | ADR-037 (ID-01 after VEN-01; VEN-04); evaluation exports in separate files `sql/evaluation_seed.sql`, `json/evaluation/` | `tests/test_spec.py::test_intake_manifest_never_hands_the_engine_a_vendor`; `tests/test_engine_sandbox.py::test_id_blind_run_gives_identical_decisions` and `::test_sender_mismatch_is_raised_and_never_changes_the_vendor`; `test_sql_seed_loads_with_foreign_keys_and_keeps_labels_separate` | done: evaluation tables only in `evaluation_seed.sql` and `exports/json/evaluation/` |
| A-67 | One processing-time semantics shared by oracle and engine | receipt cutoff = processing time; cumulative per PO line in intake order (ADR-012, ADR-024); `snapshot_*` reporting only (ADR-038) | static `snapshot_` ban; `tests/test_decisions.py` time-travel tests | done: engine cutoffs at the intake timestamp, history filtered by recorded_at; `test_time_travel_truncated_master_gives_the_same_processing_decision`, `test_snapshots_and_post_as_of_rows_never_change_a_decision` |
| A-54 | Committed data equals a fresh build; results independent of PYTHONHASHSEED | `python -m invoice_ap repro`; parity check | `reproducibility.{json,md}` with PYTHONHASHSEED=1 and =2; committed-vs-fresh SHA-256 parity test (ADR-028) | done: `test_committed_data_equals_a_fresh_build` (both scales) and the PYTHONHASHSEED rebuilds in `repro` |
| A-60 | Per-invoice acceptance report | `invoice_ap/evaluation` | `reports/acceptance_per_invoice.csv` (invoice_id x R34a-e, pass/fail with reason) + aggregate in `evaluation.md` | done: `reports/acceptance_per_invoice.csv` + aggregate in `reports/evaluation.md` |
| A-36 / A-39 | Numeric mix tolerances; every edge case >= 10 at full and >= 1 at starter; explicit baseline phase | allocation (Table G2/G7); baseline phase in `generator/build.py` (ADR-039) | `test_full_scale_mix_is_exact`; `tests/test_generator.py::test_mix_matches_the_allocation`, `::test_edge_cases_are_present`, `::test_self_checks_pass_and_the_baseline_is_clean` | done |
| A-26 | N:M bridge exercised in both directions | archetypes A21 and A12 | `test_many_to_many_bridge_is_exercised_in_both_directions`; >= 1 GRN line allocated to >= 2 invoice lines | done: `processed/match_allocation.csv`; `test_bridge_is_exercised_in_both_directions` |
| A-61 | Scenarios spread across the timeline and ID range | seeded placement over the whole intake window | `reports/distribution_summary.md` (vendor concentration, line values by category, weekday share, lead times, mixes, monthly intake, scenario deciles) | done |
| A-03 / A-72 | Negative and mutation tests for extraction and rules | `tests/` | corrupted-document tests (silent-error detection), rule mutation tests (flip a tolerance -> labels change) | done |
| A-64 | Contacts and bank details obviously synthetic | `.example` / `example.com` addresses, `TRN-` tax IDs, no bank account numbers (ADR-027) | REV-IC regex scan; manifest provenance block | done: no bank details are generated; contacts use reserved `.example` domains; manifest provenance |
| A-74 | Prompt history includes relay messages and prompts to other tools | `ai_disclosure/prompt_history/` (orchestrator) | directory listing | done: `ai_disclosure/prompt_history/` |
| A-80 | Timeline integrity (genuine, monotonic commit dates inside the 72-hour window) | one commit per stage and fix round, no `--date` overrides or rewrites | `git log --format='%h %ad %cd'` in the hand-off | done: commit history is append-only with no date overrides; `git log --format='%h %ad %cd'` |
| A-81 | Candidate hand-off list | README hand-off section | create/push repo; personal statement; other-tool prompts; deadline; recruitment e-mail; walkthrough rehearsal; author e-mail choice (S1-R1-09); MIT confirmation | done: README "Hand-off" lists what the candidate must do (publish, personal statement, author e-mail, walkthrough rehearsal) |
| A-82 | Traceability covers the A-items | this section | grep of A-ids | done (this table) |
| A-31 / A-32 | Conventions for unspecified IDs; vendor invoice number kept apart from `invoice_id` | `invoice_ap/common/ids.py`; `vendor_invoice_number` field | `tests/test_ids_and_money.py` | done |
| A-35 | Exact allocation proof | `invoice_ap/generator/allocation.py` | `tests/test_allocation.py`; independent table re-derivation script | done |
| A-65 / A-66 / A-68 | Decimal money; determinism hygiene; code quality and portability | `invoice_ap/common/money.py`; banned-call test; stdlib only, pathlib, LF | `tests/test_ids_and_money.py`, `tests/test_repo_hygiene.py`; Python 3.11-3.13 runs | done: tests pass on Python 3.11 and 3.13; determinism and stdlib-only checks in `tests/test_repo_hygiene.py` |
