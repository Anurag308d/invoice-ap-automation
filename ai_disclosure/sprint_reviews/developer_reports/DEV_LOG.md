# DEV log (running; newest entry first)

Purpose: let DEV resume after a context reset. It covers state, decisions, conventions and next steps.
Requirements: `/home/claude/sprint/ASSIGNMENT.md`. Plan and gates: `/home/claude/sprint/SPRINT_PLAN.md`.
Brief: `/home/claude/sprint/prompts/001_dev_brief.md`.

## 2026-10-30 - Stage 6 final hand-off committed (`aec3b84`)

- README is final (218 lines).
- New docs: `docs/testing_and_verification.md`, `docs/walkthrough.md` and `ai_disclosure/AI_USAGE.md`,
  with a placeholder checklist for the candidate.
- Traceability is final: every row has evidence and a final status.
- Stage and sprint wording is removed from code, tests and docs.
- New secret and personal-data scan test.
- Data rebuilt with `build-all`.
- 544 tests pass from a fresh clone.
- The orchestrator adds `ai_disclosure/prompt_history/` and `sprint_reviews/`.
- Still for the candidate: the personal statement, the author e-mail choice (S1-R1-09), publishing.

## 2026-10-30 - Stage 5 committed (`8a6c8b6`, data included), awaiting REV review

**State.**
- Stage 4 passed (PASS-WITH-NITS).
- `build-all` (about 35 s) writes both scales into `data/` and passes reproducibility.
- 541 tests pass on 3.13 and 3.11, including parity between the committed data and a fresh build.
- Data is committed: starter complete; full scale without `exports/json`, `exports/sql`,
  `decision_trace.jsonl` and `extraction_field.csv` (checksums in the manifest).
- Tracked data is 25.9 MB; the git pack is 3.4 MiB. Report: `dev_reports/stage-5-report.md`.

**Where things live (new).**
- `quality/suite.py`, `export/exports.py`.
- `report/{manifest,queue,dashboard}.py`, `evaluation/report.py`, `orchestrate.py`.
- `tests/test_outputs.py`; fixture `complete_builds`.

**Conventions.**
- After any code change that alters output, run `python -m invoice_ap build-all` and commit `data/`
  with the code. The parity test fails otherwise.
- The exclusion list lives in `report/manifest.py::EXCLUDED_FROM_COMMIT`, mirrored in `.gitignore`
  (and tested).
- Reports carry no paths, times or folder names. Titles use the scale from the manifest.

**Next (Stage 6).**
1. The walkthrough guide and the `ai_disclosure/` folder with the prompt history (A-74, A-75), keeping
   the `[CANDIDATE TO COMPLETE]` placeholders.
2. The timeline-integrity check (A-80) and the hand-off list (A-81).
3. Final acceptance evidence: re-check every item.
4. S1-R1-09 and the MIT confirmation are left to the candidate.

## 2026-10-30 - Stage 4 committed (`d105b00`, `ad005fb`), awaiting REV review

**State.**
- Stage 3 passed (PASS-WITH-NITS).
- Full scale: the engine matches ground truth on 2,000/2,000 invoices for every item and on
  2,960/2,960 lines; acceptance 2,000/2,000; 0 unsafe payments.
- 521 tests pass on 3.13 and 3.11. Report: `dev_reports/stage-4-report.md`.
- Workflow: `generate`, `run`, `evaluate` (exits 1 on any failure), `explain <id>`.
- The full engine run takes about 1.7 s.

**Where things live (new).**
- `engine/`: `master.py`, `validate.py` (Validator, `match_status`), `decide.py`, `explain.py`.
- `pipeline.OUTPUT_TABLES`: 12 tables.
- `evaluation/decisions.py`.
- `tests/test_decisions.py`. Its helpers are `_copy`/`_run`/`_edit` on blind copies; read ground
  truth from the original root.

**Conventions.**
- Processing cutoffs are the intake timestamp; vendor history is filtered by `recorded_at`.
- Event stamps: received, capture +1 min, decision +1 min, payments at 10:00 on the scheduled date.
- The engine never imports the oracle. If a rule changes, change both and rerun the agreement tests.

**Next (Stage 5).**
1. Exports: CSV, JSON and the SQL seed with PK/FK/CHECK constraints; evaluation exports in separate
   files.
2. The full validation suite.
3. The reproducibility report, `repro`, `build-all`, `queue --role` and the offline dashboard.
4. Distribution report updates (A-61).
5. Commit data under ruling 1: no full-scale JSON; drop the full `decision_trace.jsonl` (about
   23.5 MB total); record checksums in the manifest; note in the README.
6. Parity test: committed data equals a fresh build (A-54).

## 2026-10-30 - Stage 3 committed (`0a2ca58`), awaiting REV review

**State.**
- Stage 2 passed (PASS-WITH-NITS). All prompt-013 carry-ins are done: S2-R1-01, Q1, Q3, Q4.
- Report: `dev_reports/stage-3-report.md`.
- 503 tests pass on 3.13 and 3.11; `docs --check` is clean.
- Workflow is `generate`, then `run`, then `evaluate` (`--scale` or `--data`).
- Full scale: generate about 2.5-3 s, engine about 0.9 s. 1,990 of 1,990 non-degraded documents are
  exact, 10 of 10 degraded scans are flagged, and there are 0 silent errors.

**Where things live (new).**
- `generator/documents.py`: templates and renderers. It uses its own streams (`doc-templates`,
  `doc-render`) and renders both phases.
- `spec/io.py`: `cell`, `csv_bytes`, `read_table`.
- `engine/`:
  - `adapters` (one per format), `textlayout`, `labels` (synonyms), `normalize`, `read`, `fields`
    (confidence per method);
  - `vendor_identity` (the only reader of sender fields);
  - `capture`, `routing` (`Router.raise_exception`), `pipeline` (`run_engine`, `OUTPUT_TABLES`).
- `evaluation/extraction.py`.
- `tests/conftest.py`: session fixtures `builds` and `engine_runs`.

**Conventions.**
- Never share label lists between renderer and engine.
- A value that fails its format is NOT_FOUND, never guessed.
- OCR repair applies only inside tokens that already contain a digit.
- Data JSON is compact (`writer.json_compact`); reports use `json_bytes`.
- Engine-side datetimes are naive IST: `cell()` appends +05:30.

**Next (Stage 4, after REV passes Stage 3).**
1. Add the remaining rules in order, on captured values: DUP-01..03 gates; VEN-04 behind the
   duplicate gates; VEN-02/03 from history; PO-01..03; DATE; ARI; TAX; MAT with cumulative
   quantities at processing time; MS-01, PRI-01, RTE-01.
2. Add approvals, payments, the `ap_event` lifecycle, `invoice_decision`, `match_result`,
   `match_allocation` (A-26: a GRN line split across two invoice lines) and `duplicate_pair`.
3. Add the time-travel sandbox and give the 8 absent types unit fixtures with "not present" metrics
   (ruling 2).
4. Extend `evaluate` with per-type P/R/F1, the confusion matrix, per-invoice acceptance (A-60) and
   rule mutation tests.

## 2026-10-30 - Stage 2 committed (`22c2e6a`), awaiting REV review

**State.**
- Done:
  - generator, rule-based oracle, writer, quick validator, distribution report;
  - CLI `generate --scale --seed --out` and `validate --quick`;
  - report: `dev_reports/stage-2-report.md`.
- 456 tests pass (3.13 in 4.8 s, 3.11 in 5.4 s); `docs --check` is clean.
- Build times: full about 2.1-2.5 s, starter about 0.2 s.
- Data goes to the git-ignored `data/<scale>/` (Q3). Do not commit it before Stages 5 and 6 close.
- Seed 20261022, `reports/source_manifest.json` SHA-256: starter `6160937e5c454a46...`, full
  `c62b4406026617c1...`. They are identical under PYTHONHASHSEED 1 and 2.

**Where things live (new in Stage 2).**
- `common/calendar.py`: `BusinessCalendar`.
- `generator/`:
  - `rng.py`: sha256 sub-streams, integer draws, Decimal log-normal;
  - `params.py`: every distribution and window;
  - `world.py`;
  - `planner.py`: all the draws;
  - `tables.py`: `materialize(plan, "baseline"|"final", policy_version)`;
  - `oracle.py`: `label()`, which raises `OracleMismatch`;
  - `writer.py`;
  - `build.py`: `generate()`.
- `quality/quick.py`: `load(Path)`, `validate(t, policy, alloc)`.
- `report/distribution.py`.
- `tests/test_generator.py`: 35 cases.

**Conventions to keep.**
- All randomness lives in `planner.py`. `materialize` makes no draws, so baseline and final share
  one plan.
- A new draw in an existing sub-stream shifts every later draw in it, which changes the hashes. Put
  new features on a new named stream.
- Money and pct values must be whole cents before the writer, which raises otherwise. Quantities are
  quantized to the unit of measure.
- In the validator, a labelled duplicate inherits its original's code (`allowed`).
- `quick.load` takes a `Path`, not a str.
- `pyproject` addopts already has `-q`. Do not add another `-q`, or the summary line is hidden.

**Decisions (ADR-039, ADR-030).**
- Two-phase build: the baseline must validate with 0 violations and 0 labelled defects.
- Per-PO timeline redraw: up to 11 attempts, then the worst case.
- Dedicated tail vendors for TV-CLOSED and TV-BLOCKED.
- Duplicate originals are received on or before 30 Sep.
- The intake manifest's sha256 and bytes are pending until Stage 3.
- Turnarounds are 2/2/3/3 business days. Policy stays 1.0.0.

**Open points (in the report, §6).**
- Forwarding mailboxes are 10.3% (35 of 340), from a 15% per-document draw. Switch to an exact quota
  if REV asks.
- PAYMENT_DUE_DATE_PASSED is absent from the data. Stage 4 adds fixtures and a "not present" metric.
- The full build is 18.2 MB without documents; Q3 may need compact JSON in Stage 5.
- Every date falls on a business day.

**Next (Stage 3, after REV passes Stage 2).** Stage-3 gate: A-02, 03, 10 (boundary test), 41, 50
(engine boundary), 55.
1. Render the inbox documents at `intake_manifest.file_path`, byte-stable, and fill `file_sha256`
   and `file_bytes`.
2. Extraction with confidence. CAP-DEGRADED-SCAN must give EXT_LOW_CONFIDENCE (CAP-01).
3. Make `engine/vendor_identity.py` the only reader of sender fields (VEN-01..04).
4. Add `tests/test_engine_sandbox.py`: the blind run (no `source/` or `ground_truth/`) must be
   byte-identical, and the ID-blind run must give identical decisions.
5. Add negative and mutation tests for extraction (A-03), and check that A-41 survives extraction.

## 2026-10-30 - Stage 1 fix round 1 committed (`66b1f07`), awaiting REV re-review

**State.**
- All of S1-R1-01..08 are fixed (S1-R1-09 is the candidate's decision). Response:
  `dev_reports/stage-1-response-1.md`.
- 421 tests pass; `docs --check` is clean; REV's checker and DEV's parser are OK at both scales.

**What changed.**
- Intake has no `invoice_id`. It has `intake_seq`. `sender_vendor_id` is set only for PORTAL and EDI.
- ID-01: the engine assigns `INV-<VEN-01 vendor or VND-00000>-2026-<intake_seq>`.
- New rule VEN-04 `VENDOR_SENDER_MISMATCH`, giving 24 exception types.
- Master `snapshot_*` columns are flagged reporting only.
- New category CAPTURE_REVIEW (`CAP-DEGRADED-SCAN`). CLEAN is now 1,350 / 135.
- New archetype A12 (`C-PARTIAL-BILLING`, 1 GRN line -> 2 invoice lines). Full scale: A11 915,
  A22 295, A33 50, A21 45, A12 10, A01 80, A10 45, A00 60; C-STD 310.
- `as_of_date = 2026-10-22`: the data window ends then, and intake closes 2026-10-21.
- Lifecycle now uses explicit short labels: `Transition(label, detail, simulated)`.
- New ADRs: ADR-037 (vendor identity), ADR-038 (snapshot columns).
- Exports split: `sql/evaluation_seed.sql` and `json/evaluation/` for source and ground truth.

**Carry-forward plan (from stage-1-review-1; add to the stage DoD when that stage starts).**
- **Stage 2.**
  - Exact boundaries. Choose PO prices so that +2.00% is an exact cent. AT = +2.00% exactly;
    INSIDE / OUT = 2% minus / plus 0.01. Over-receipt at 1.05 must be an exact unit of measure.
  - The oracle asserts that no unintended DUP-03 pair exists (ADR-009).
  - Closures and blocks come after all of the vendor's other activity (ADR-025).
  - No completed event lies after as-of (test). Late POs go to A00 or A10.
  - Baseline self-checks before injection (P-9): PK, FK, enums, arithmetic, plus the oracle
    assertions.
  - Scenario spread across the timeline and ID range (A-61): report decile positions.
  - Channel-realistic sender metadata: about 15% of EMAIL documents come from a forwarding mailbox;
    SCAN gets a batch ID; PORTAL and EDI get the authenticated vendor.
  - Source `invoice_id` = `INV-<true vendor>-2026-<intake_seq>`.
  - A12 POs: one GRN, then two invoices that bill parts.
- **Stage 2/5.** GRN over-receipts beyond tolerance (`QM-EXCEEDS-PO-*`) are reported as labelled,
  not as violations.
- **Stage 3.**
  - `tests/test_engine_sandbox.py::test_blind_run`: copy without `source/` and `ground_truth/`,
    outputs byte-identical.
  - `::test_id_blind_run`: blank `sender_vendor_id` and `sender_address`, identical decisions.
  - Only `engine/vendor_identity.py` may read sender fields (static ban already active).
  - Negative and mutation tests for extraction (A-03).
- **Stage 4.**
  - `tests/test_time_travel.py`: truncate master and events to processing time and blank
    `snapshot_*`; the decision must not change.
  - Per-type metrics for the "not present" types (ADR-036), with no division by zero.
  - The README states that approver rejection is not simulated (A-78).
  - Per-invoice acceptance report `reports/acceptance_per_invoice.csv` (A-60).
  - Data check: at least one GRN line is allocated to at least two invoice lines (A-26).
- **Stage 5.**
  - Evaluation exports go to separate files.
  - Run the PYTHONHASHSEED 1-vs-2 probe.
  - Parity check: committed data equals a fresh build.
  - Measure committed size against Q3 (about 25 MB; otherwise checksums only for the full-scale
    JSON/SQL).
  - Commit generated data only when Stages 5 and 6 close.
- **Stage 6.**
  - S1-R1-09: the candidate decides the author e-mail.
  - The candidate confirms the MIT licence.
  - Keep the `[CANDIDATE TO COMPLETE]` placeholder.
  - A-80 timeline integrity (`git log %ad %cd`).
  - A-81 hand-off list.

## 2026-10-29 - Stage 1 committed (`12f551a`), awaiting REV review

**State.**
- Stage-1 deliverables are complete; the report is at `dev_reports/stage-1-report.md`.
- 408 tests pass on Python 3.11, 3.12 and 3.13.
- `python -m invoice_ap docs --check` is clean.

**Where things live** (repo `/home/claude/invoice-ap-automation`):
- `invoice_ap/common/`: logic-free shared code:
  - `enums.py`: all vocabularies; `EXCEPTION_TYPES` order = precedence;
  - `ids.py`: patterns and formatters;
  - `money.py`: Decimal HALF_UP;
  - `lifecycle.py`: state machines and `sequence_errors`;
  - `policy.py`: `load_policy` / `validate_policy`;
  - `policy_render.py`, `docsync.py`, `paths.py`.
- `invoice_ap/spec/`: data-dictionary DSL (`model.py`) and tables:
  - `tables_master.py`: 12 tables;
  - `tables_documents.py`: intake_manifest, invoice, invoice_line, ground_truth, ground_truth_line;
  - `tables_processed.py`: 12 tables;
  - renderers: `render.py` (dictionary MD + JSON) and `schema_render.py` (keys, state machines).
- `invoice_ap/generator/`:
  - `catalogue.py`: 40 sub-scenarios with placement, edge cases, intended issues and decision;
  - `allocation.py`: exact counts at any scale;
  - `allocation_report.py`: Tables G1-G8.
- `invoice_ap/cli.py`: `plan`, `docs [--check]`, `policy`; the other commands are planned stubs
  (exit 2). `doc_blocks()` lists every generated doc block.
- `config/ap_policy.toml`: policy 1.0.0. Decimals are strings. 23 routing entries; approval bands
  P1-P4 / N1-N3.

**Conventions to keep.**
- After any spec, policy, lifecycle or allocation change, run `python -m invoice_ap docs`, then
  `python -m pytest`.
- Never hand-edit `docs/data_dictionary.md` or the generated blocks.
- Engine may import only `common`, `spec` and `engine` (test-enforced). Never name `ground_truth`,
  `SCENARIO_`, `catalogue` or the `"source"` literal in engine code.
- Banned in package code (test-enforced): `datetime.now`, `date.today`, `time.time`, `random.<fn>(`
  module-level calls, gauss/lognormvariate, `math.exp/log/pow/sin/cos`, `uuid`.
- Commit trailers: exactly the two lines from SPRINT_PLAN §6.
- Python environment quirk: `pip wheel` or install needs `SETUPTOOLS_USE_DISTUTILS=stdlib` (Debian
  setuptools 68). To run pytest under 3.11: `PYTHONPATH=/usr/local/lib/python3.13/site-packages
  /usr/bin/python3.11 -m pytest -q -p no:cacheprovider`. Clean `__pycache__` before committing
  (they are gitignored anyway).

**Key decisions** (ADRs in `docs/assumptions_and_decisions.md`):
- vendor-code = vendor_id;
- global invoice counter;
- CLEAN 68% with EC-02 and EC-03 carved out at 1% each;
- archetype identities for PO, GRN and invoice counts;
- engine creates approvals and payments;
- as-of snapshot 2026-12-31, no resolution simulation;
- gates (capture, duplicate, invalid PO);
- duplicates never consume receipts;
- flat package layout.

**Open questions raised to REV:** CLEAN 68%; capture overlay inside CLEAN; full-build size; flat
layout.

**Next (Stage 2, after REV passes Stage 1):**
1. `generator/rng.py`: sha256 sub-streams; integer-weighted choice; Irwin-Hall Z in Decimal;
   `Decimal.exp`.
2. `generator/world.py`: users (SYSTEM = USR-0001), vendors (Zipf weights `1_000_000 // rank`,
   tiers, segments, terms, channels), status history, SKUs (`max(60, round(lines x 2/11))`).
3. `generator/purchasing.py`: POs, lines (histogram from allocation), receipts per archetype,
   `erp_event`.
4. `generator/invoices.py`: slot assignment -> baseline -> injections -> duplicates -> intake order
   -> manifest.
5. `generator/oracle.py`: independent rules -> ground truth (+ lines). Assert == `intended_issues`
   per invoice and fail loudly.
6. Writers: CSV/JSON from the spec column order. Run `generate --scale starter|full --seed 20261022`.
7. Tests:
   - counts;
   - FKs;
   - IDs;
   - derived values;
   - unrelated rows untouched by an injection;
   - oracle == intent;
   - determinism (two runs give identical bytes);
   - distribution sanity;
   - timeline rules (GRN posted before invoice processing for clean slots; closures after the
     vendor's other activity).
8. Report realised distributions; update traceability and the README.
