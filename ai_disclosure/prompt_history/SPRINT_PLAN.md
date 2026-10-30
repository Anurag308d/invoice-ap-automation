# Sprint plan — Invoice-to-Pay (AP) automation assignment

Requirements live in `/home/claude/sprint/ASSIGNMENT.md` (verbatim). If this plan and the assignment ever
disagree, the assignment wins.

## 1. Roles

| Role | Who | Responsibility |
|---|---|---|
| Orchestrator | main Claude session | Runs the sprint, relays work between agents, keeps the prompt history, delivers the final repo to the candidate's computer. Arbitrates disputes. |
| DEV | developer agent | Expert AP-automation and data engineer. Builds everything in the repo. The only agent that writes to the repo. |
| REV | senior reviewer agent | Independent principal engineer and AP / finance-ops domain lead. Audits every stage against the assignment, runs the code, issues the gate verdict. Never edits the repo. |

Neither agent spawns sub-agents. Every prompt must be logged, and the prompt history is a submission requirement (see ASSIGNMENT.md §B-03 and §C-6).

## 2. Paths

| What | Path |
|---|---|
| Repo (git, branch `main`) | `/home/claude/invoice-ap-automation` |
| Requirements (verbatim) | `/home/claude/sprint/ASSIGNMENT.md` |
| This plan | `/home/claude/sprint/SPRINT_PLAN.md` |
| DEV running log (decisions, status, next steps; lets work resume after a context reset) | `/home/claude/sprint/DEV_LOG.md` |
| DEV stage reports / fix responses | `/home/claude/sprint/dev_reports/stage-<N>-report.md`, `stage-<N>-response-<K>.md` |
| REV acceptance checklist | `/home/claude/sprint/reviews/ACCEPTANCE_CHECKLIST.md` |
| REV reviews | `/home/claude/sprint/reviews/stage-<N>-review-<K>.md` |
| REV findings tracker (all findings across stages, with status) | `/home/claude/sprint/reviews/FINDINGS_TRACKER.md` |
| Orchestrator prompt log (read-only for agents) | `/home/claude/sprint/prompts/` |

At the end, the orchestrator copies the prompt log, reviews and responses into the repo's AI-disclosure directory as evidence of process and validation.

## 3. Gate process (every stage)

1. DEV builds the stage scope, verifies it themselves (runs code and tests), commits, and writes `stage-<N>-report.md`. The report lists what was built, the requirement IDs covered, how it was verified (commands and short output excerpts), known gaps and questions.
2. REV reviews independently. REV reads the docs and code, runs the commands, and inspects the data. REV never takes DEV's report on trust. REV writes `stage-<N>-review-<K>.md` with a verdict.
3. On a REVISE verdict, DEV fixes every BLOCKER and MAJOR finding, and every MINOR one unless there is a written justification. DEV writes `stage-<N>-response-<K>.md` (finding ID → fix → evidence) and commits. REV then re-reviews the fixed items and checks for regressions.
4. The stage closes when REV issues PASS or PASS-WITH-NITS. After 3 review rounds, the orchestrator arbitrates.
5. The next stage starts only after the current one passes. Carry-forward items stay open in FINDINGS_TRACKER.md and must be closed by the final audit.

Verdict scale: PASS / PASS-WITH-NITS (only NIT-level items remain) / REVISE.

| Severity | Meaning |
|---|---|
| BLOCKER | Violates an explicit requirement, gives wrong results, breaks run or tests, or leaks ground truth. |
| MAJOR | Requirement only partly met, weak evidence, or a significant correctness, robustness or clarity gap that a strict evaluator would penalise. |
| MINOR | A quality improvement a strict evaluator could notice. |
| NIT | Optional polish. |

## 4. Stages and Definition of Done

### Stage 1 — Specification, design and repo skeleton (docs first; these docs are deliverables, not throwaway)
- `docs/architecture.md`: components, data flow (mermaid), module boundaries (generator / engine / evaluation / validation / export / report / CLI) and the no-leakage design.
- `docs/schema.md`: ERD (mermaid `erDiagram`) for the 9 core entities plus supporting tables. Also: PK and FK list, a cardinality table (1:1, 1:N, N:M with bridge tables), optional relationships, effective dates, and a lifecycle state machine for each stateful entity (Vendor, PO, GRN, Invoice, Approval, Payment, Exception).
- `docs/data_dictionary.md`, plus a machine-readable spec that later code and tests use. For every field of every table: type, required/optional, allowed values, units, uniqueness, validation rule, description, and whether it is source or derived.
- `docs/business_rules.md` plus a versioned policy config file. It covers:
  - tolerances for price, quantity, over-receipt, tax and rounding;
  - match-status derivation and precedence;
  - duplicate rules, vendor rules and date rules;
  - the routing matrix (exception → actor role → queue → SLA → blocking or not);
  - the approval matrix (amount bands → levels → roles);
  - payment-readiness rules and policy versioning.
- `docs/data_generation.md`:
  - generation order and distributions;
  - an exact volume-allocation algorithm, showing how exactly 300 / 1,500 / 2,200 / 1,800 / 2,000 are hit at full scale and how the starter scale is derived;
  - a scenario-mix allocation table with exact counts at both scales;
  - a mapping of all 8 edge cases to labels and categories;
  - the ground-truth schema, seed and scale parameters, and determinism rules.
- `docs/evaluation_plan.md`: every metric to be produced and how it maps to the acceptance criteria and to Evaluation Focus (a)–(g).
- `docs/requirements_traceability.md`: every R-/G- item in §5 → planned implementation location → planned evidence (test, report or file).
- `docs/assumptions_and_decisions.md`: each ambiguity resolved explicitly, as ADR-style entries (decision, alternatives, trade-off).
- Repo skeleton: README stub, `pyproject.toml` and/or `requirements*.txt`, package layout, `.gitignore`, `.gitattributes` (force LF for text and data so checksums survive Windows checkouts), LICENSE (MIT), `tests/`. First meaningful commit.
- DoD (REV confirms):
  - every requirement has a planned home;
  - the volume math is feasible and exact;
  - the mix and edge-case allocation is consistent with ~70/10/8/5/4/3 and covers all 8 edge cases;
  - IDs follow the conventions;
  - ambiguities are resolved and documented;
  - the design has no leakage path.

### Stage 2 — Synthetic data generator and ground truth
- The generator implements the Stage-1 spec:
  - tables are built in order: master → child → transactional → event;
  - IDs are deterministic;
  - `--seed` defaults to 20261022;
  - scale is a parameter (`starter` / `full`, or a numeric factor) and both scales use the same code path.
- Full-scale volumes are exactly 300 vendors / 1,500 POs / 2,200 PO lines / 1,800 GRNs / 2,000 invoices, and the scenario mix is as specified.
- A valid baseline is generated first. All 8 edge cases are then injected and labelled, without silently corrupting unrelated rows.
- Derived values (totals, tax, balances, scores, statuses, dates) are computed from source records.
- Generator-side history is append-only: vendor status history, PO and GRN lifecycle events.
- Ground truth (`ground_truth.csv` + `ground_truth.json`) sits in a separate folder. A rule-based oracle derives it from the true source data and asserts it against the injection intent. It never appears in input tables.
- Outputs are written as CSV and JSON. There is no wall-clock time and no unseeded randomness.
- Unit tests cover the generator.
- DoD: REV runs both scales and verifies counts, mix, ID formats, FKs, derived values, edge cases, ground-truth separation, determinism and the realism of distributions.

### Stage 3 — Invoice intake and field extraction
- Every invoice is rendered as a document in its intake channel. There are at least 3 heterogeneous formats, for example a structured portal JSON, an EDI-like flat file, and semi-structured email/OCR text from several vendor templates with recoverable formatting variation. An intake manifest records document id, invoice id, channel, received timestamp and sender.
- The extraction engine has one adapter per channel, label synonyms, and date / number / currency normalisation. It produces per-field confidence and never "fixes" printed values: a wrong header total must survive extraction so validation can catch it.
- An extraction evaluation compares extracted fields with the source invoice and lines: field-level and document-level, per channel and per field, with a mismatch listing. A low-confidence rule routes uncertain documents to the operations analyst. That rule is defined and tested.
- The engine reads only master data and the inbox. This is enforced by a test.
- DoD: every invoice's extracted fields match the source. Any mismatch is caught by confidence or validation and routed, never silent.

### Stage 4 — Decision engine and evaluation
- Validation and matching:
  - Header validation: vendor existence and status at invoice date, vendor identity, PO existence and PO-vendor consistency, date rules, header-vs-lines arithmetic, tax.
  - Duplicate detection: exact resubmission vs invoice-number reuse, number normalisation, true negatives, and an output pair (duplicate → original).
  - Three-way match per line, with cumulative quantities and price / quantity / tax tolerances. Covers missing receipt, exceeds-PO quantity, over-receipt and partial delivery.
  - Match status derived with the documented precedence.
- Exception records carry type, severity, blocking flag, expected-vs-actual details, tolerance used, assigned actor role and queue, SLA due date and status.
- Approvals are created only for eligible invoices, per the approval matrix. Payments are created only for fully approved, unblocked invoices (payment-ready).
- An append-only event log, checked by a state machine, records every state change, and current status equals the last event. Each invoice has a decision trace (an "explain" view).
- Evaluation vs ground truth covers:
  - per-exception-type precision, recall and F1, plus a confusion matrix on the primary outcome;
  - duplicate pair accuracy, approval-level agreement, and payment-ready safety (0 blocked invoices marked ready);
  - STP rate, exception rate and value-at-risk prevented.
  - Output in JSON and Markdown.
- DoD: an automatic per-invoice acceptance check runs on all 2,000 invoices and passes, or any deviation is explained.

### Stage 5 — Validation suite, exports, manifest, reproducibility, CLI and dashboard
- A validation suite runs over all tables: PK uniqueness, FK integrity (every join), allowed enums, date ordering, arithmetic reconciliation, lifecycle transitions (from the event logs) and duplicate checks. It is aware of labelled defects. Output: `validation_summary.json` + `.md`.
- Exports:
  - CSV and JSON for all tables.
  - A SQL seed: DDL with PK / FK / CHECK constraints plus INSERTs. It must load into SQLite with `PRAGMA foreign_keys=ON` and return a clean `foreign_key_check`. Postgres-compatible DDL is welcome.
- `source_manifest.json` records the generator version, exact command, seed, scale, policy version, every file with row count and SHA-256, and provenance (100% synthetic, no external data, licences).
- A reproducibility command regenerates the data twice with the same seed into separate directories and compares row counts and checksums. A different seed is run as a sanity check. The report is saved.
- One command builds everything for the starter and full scales. A role-based queue CLI shows each of the five actors their work. A self-contained offline HTML dashboard covers KPIs, exception queues per actor, invoice decision traces, the evaluation and the validation results.
- DoD: REV runs everything from a clean state. Checksums are identical across runs, the SQL loads, and validation is all green.

### Stage 6 — Documentation, tests, AI-disclosure scaffolding and final acceptance
- README:
  - problem and solution overview, and architecture;
  - quickstart for Windows PowerShell and for macOS/Linux;
  - configure (policy, seed, scale), run, and verify (tests and reports);
  - a map of outputs and a results snapshot;
  - assumptions, limitations and next steps, plus a pointer to the AI-usage disclosure.
- Final docs: data dictionary, schema, rules, generation, evaluation (with actual numbers), and assumptions and decisions (ADR, trade-offs). Also: testing approach and how we know it works, limitations and next steps, a walkthrough guide for the live review, and the requirements traceability matrix with evidence links.
- The tests are a fast pytest suite covering every acceptance criterion and validation rule.
- The AI-disclosure directory (clearly identifiable, e.g. `ai_disclosure/`) holds:
  - `AI_USAGE.md`, written honestly, with clearly marked placeholders for the candidate's own statement of what they personally reviewed, changed or validated (never invent that);
  - `prompt_history/` and `sprint_reviews/`, which the orchestrator fills.
- Repo hygiene: no secrets, personal data or credentials. Dependencies are small, licences are respected, and the commit history is meaningful.
- Final acceptance audit by REV: a fresh `git clone` into a temp dir, following the README only, then a run of everything and the tests. Every item in §5 and in the acceptance checklist gets ticked with evidence in `FINAL_ACCEPTANCE.md`.
- DoD: REV PASS on all items.

## 5. Master requirement checklist (orchestrator's extraction — REV must independently extend it)

### Problem statement
- R1 End-to-end working solution: invoice intake → field extraction → PO/receipt matching → exception routing → payment readiness.
- R2 Exposes key decisions and exceptions. R3 Preserves traceability. R4 Produces measurable outputs.
- R5 Medium complexity: multiple related entities, conditional rules, ≥1 exception path, meaningful evaluation metrics.
- R6 The five actors (business requester, process owner, approver, operations analyst, system administrator) are explicitly represented in data, routing, approvals and administration.
- R7 Master data is generated first: Vendor, PurchaseOrder, PurchaseOrderLine, GoodsReceipt, GoodsReceiptLine.
- R8 Dependent transaction and event records use valid parent IDs.
- R9 Business logic:
  - R9a Vendors are created first.
  - R9b POs reference vendors.
  - R9c Each PO has 1–8 lines with SKU, quantity, unit price and tax code.
  - R9d Receipts reference PO lines, with full, partial and over-receipt quantities.
  - R9e Invoices reference a vendor and, optionally, a PO.
  - R9f Line totals, tax and grand total are calculated from lines.
  - R9g Match status is derived from price, quantity and tax tolerances.
  - R9h Approval and payment records exist only for eligible invoices.
- R10 State changes are persisted as explicit records or events, and history is never overwritten.
- R11 Outcomes and ground-truth labels come from documented rules, not independent random assignment.
- R12 All 9 core entities exist: Vendor, PurchaseOrder, PurchaseOrderLine, GoodsReceipt, GoodsReceiptLine, Invoice, InvoiceLine, Approval, Payment.
- R13 Every entity has a PK, and every relationship has an FK.
- R14 The documentation covers cardinality (1:1, 1:N, N:M), optional relationships, effective dates and lifecycle states.
- R15 Bridge tables are used for many-to-many relationships.
- R16 Event history is retained for state changes.
- R17 All joins are validated.
- R18 Deliberate anomalies carry an issue_type / ground_truth label instead of silently corrupting unrelated rows.
- R19 ID conventions: VND-00001; PO-2026-000001; GRN-2026-000001; INV-<vendor-code>-2026-000001; INVL-<invoice-id>-01. Counters are zero-padded, IDs are immutable, and referenced IDs are exactly consistent across files.
- R20 (Step 1) A data dictionary for all 9 entities gives each field's type, required/optional, allowed values, units, uniqueness and validation rule.
- R21 (Step 2) Parent/master tables are created first, then child and event tables.
- R22 (Step 3) IDs are deterministic.
- R23 (Step 4) Volumes: 300 vendors, 1,500 POs, 2,200 PO lines, 1,800 receipts, 2,000 invoices.
- R24 Mix: ~70% clean, 10% price variance, 8% quantity mismatch, 5% duplicates, 4% missing receipt, 3% tax/vendor errors.
- R25 Every FK is valid, except deliberately labelled defect cases.
- R26 Fixed seed (20261022).
- R27 Scale is parameterised, and starter and full datasets come from the same generator.
- R28 (Step 5) A valid baseline comes first, then labelled edge cases are injected:
  - R28a duplicate invoice number;
  - R28b invoice total differs from the line sum;
  - R28c invoice date before PO date;
  - R28d partial delivery;
  - R28e closed vendor;
  - R28f tax mismatch;
  - R28g invoice exceeds PO quantity;
  - R28h same invoice submitted twice.
- R29 (Step 6) Derived values (totals, balances, scores, statuses, dates) are computed from source records.
- R30 (Step 7) A separate `ground_truth.csv`/`.json` exists and never leaks into input features.
- R31 (Step 8) Validation covers PK uniqueness, FK integrity, allowed enums, date ordering, arithmetic reconciliation, lifecycle transitions and duplicate checks.
- R32 (Step 9) Exports: CSV, JSON and SQL seed data, plus README, schema/data dictionary, generator command, fixed seed, source manifest and validation summary.
- R33 (Step 10) Regenerating twice with the same seed gives matching row counts and checksums, and the comparison is reported.
- R34 Per-invoice acceptance:
  - R34a extracted fields match the source;
  - R34b line arithmetic and tax reconcile;
  - R34c duplicate detection flags the correct pair;
  - R34d the three-way match and approval outcome agree with policy;
  - R34e no blocked invoice is marked payment-ready.
- R35 Evaluation focus:
  - (a) realistic distributions and meaningful variation;
  - (b) consistent IDs and valid joins;
  - (c) dependency and lifecycle consistency;
  - (d) correct derived values and reconciliation;
  - (e) normal, boundary, failure and exception coverage;
  - (f) separate ground truth;
  - (g) fixed-seed reproducibility, documentation and lawful provenance.
- R36 Lawful provenance: synthetic data, with any external reference recorded with full provenance (or an explicit statement that none was used).
- R37 Submission: a public GitHub repo, a README explaining how to run it, and the tests the problem asks for.

### Submission guidelines and FAQ
- G1 Make it run: clear steps to install dependencies, configure, run and verify key behaviour.
- G2 Show the work: a dedicated public repo, meaningful commits, the evolution visible, and supporting context.
- G3 Transparent AI use: prompt history for all prompts to every AI tool, plus where AI accelerated the work, where it was relied on heavily, and what the candidate personally reviewed, changed or validated. That last part is the candidate's own statement; leave placeholders and never fabricate it.
- G4 Reasoning visible: problem, assumptions, key decisions, trade-offs, testing approach, limitations, and how we know it works.
- G5 Readiness for a walkthrough: a walkthrough guide.
- G6 Prompt history and supporting artifacts sit in a clearly identifiable directory.
- G7 Only free or locally runnable services, and no unusually large or slow dependencies.
- G8 Environment needs and limitations are documented, along with how core functionality was verified.
- G9 No imported complete solutions; licences and attribution are respected.
- G10 Assumptions and deviations are explained, along with what works, what is incomplete, and next steps.
- G11 No secrets, credentials, personal or sensitive information, or proprietary code in the repo. Sample data is safe and synthetic.

## 6. Engineering conventions (all agents)
- Python ≥ 3.11. The runtime uses the standard library only (`csv`, `json`, `sqlite3`, `decimal`, `hashlib`, `tomllib`, `random.Random(seed)`, `datetime`, `pathlib`, `argparse`, `string`, `html`). `pytest` is the only dev dependency. No network, no paid or hosted services.
- Money uses `Decimal`, quantised to 0.01 with ROUND_HALF_UP and documented. Quantities follow their unit of measure.
- Determinism:
  - every random stream is seeded from the master seed;
  - there is never any wall-clock time, and a fixed as-of date is used for "current" status;
  - iteration order is always sorted (never depend on set or dict hash order);
  - CSV output is stable: `\n` line endings, UTF-8, fixed header order;
  - JSON uses `sort_keys` and stable separators;
  - the SQL is stable.
- Cross-platform: use `pathlib`, write UTF-8 explicitly, open CSV files with `newline=''`, and avoid OS-specific shell in the main flow. Give a Python entry point for everything; a Makefile is optional sugar.
- Keep tool output small: use `head`, `wc` and summaries, never dump thousands of rows into context.
- Git:
  - Only DEV commits. The repo-local identity is pre-configured.
  - Commit at the end of every stage and every fix round, with meaningful messages such as `stage-2: synthetic generator with exact volume allocation`.
  - Every commit message ends with exactly these two trailer lines:
    ```
    Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
    Claude-Session: https://claude.ai/code/session_01EdpfFwFbQxh9FYYUUjKBUP
    ```
- Never edit `/home/claude/sprint/prompts/`. DEV never edits `/home/claude/sprint/reviews/`, and REV never edits the repo or `dev_reports/`.
