# Stage 5 report: validation suite, exports, manifest, reproducibility, CLI, dashboard, committed data

Commit: `8a6c8b6` on `main`, with the trailers. It includes the generated data under `data/`.

## 1. What was built

| Module / command | Role |
|---|---|
| `quality/suite.py`, `validate` | Full suite: the quick checks plus engine invariants (details below). Output: `reports/validation_summary.{json,md}` |
| `export/exports.py`, `export` | JSON for every table, generated from the spec, and the SQL seeds (details below) |
| `report/manifest.py` | `reports/source_manifest.json` (details below) |
| `orchestrate.py`, `build`, `build-all`, `repro` | `build` runs generate -> run -> evaluate -> validate -> export -> dashboard -> manifest for one scale. `build-all` builds both scales and checks reproducibility for each. `repro` runs two subprocess rebuilds (PYTHONHASHSEED 1 and 2) and one with seed + 1, and writes `reports/reproducibility.{json,md}`, which contains no paths and no times |
| `report/queue.py`, `queue [--role] [--user]` | Open work per actor at the snapshot: exceptions by role and queue with SLA date and age in business days, plus pending approvals for approvers and requesters |
| `report/dashboard.py`, `dashboard` | `reports/dashboard.html`: one file, no CDN, deterministic (details below) |
| `evaluation/report.py` | Shared report writer; `evaluate` uses it |

The validation suite runs the quick checks (PK, every declared FK, enums and formats, IDs, date
order and the as-of limit, arithmetic, lifecycles replayed from both event logs, mix, oracle
intent, duplicates) and adds:
- polymorphic `ap_event` / `erp_event` references;
- decision consistency;
- R34e;
- approvals only when the invoice is unblocked;
- the N:M bridge and duplicate pairs;
- capture and policy provenance.

The SQL seeds:
- `exports/sql/seed.sql` holds master, inbox and processed tables;
- `exports/sql/evaluation_seed.sql` holds source and ground truth, as a separate file loaded after
  the seed (REV P-4);
- both carry PK, UNIQUE, FK and CHECK constraints (enums, booleans, ISO date and datetime, numeric
  ranges).

The manifest records:
- generator version, exact commands, seed, scale and policy (id, version, SHA-256);
- every file with bytes, SHA-256, rows and a `committed` flag;
- provenance (100% synthetic, no external sources, no personal data) and licences (code MIT, data
  MIT, no runtime third-party code);
- label separation, the commit policy, and the checksums of excluded files.

The dashboard shows KPI tiles, invoice status bars, queue tabs for the five actors, the backlog by
age, an invoice explorer with each invoice's decision trace (fields, exceptions, line match,
approvals, payment, event log), the agreement table, per-type P/R/F1, and the validation checks.

### Prompt 017 carry-ins

| Item | Done |
|---|---|
| NIT S4-R1-01 | `evaluation.md` is all tables: a headline KPI table, then sections for agreement, per type, confusion, duplicates, approvals, payments, exceptions, backlog, value at risk, acceptance, and a **Definitions** table. It contains no `{'`. A test asserts that every headline KPI has a definition |
| Ruling 2 (backlog) | Labelled "open and past SLA at the snapshot (no resolutions simulated)" in `evaluation.md`, the dashboard and the queue CLI. Aged <= 5 / 6-20 / > 20 business days by role (full scale: 6 / 58 / 619 of 683). Listed in the README limitations |
| Ruling 1 (budget) | Measured, checksums of excluded files in the manifest, README section, parity test (details below) |

## 2. Evidence

**Build-all** (development container): `python -m invoice_ap build-all` in 34.7 s.

| Scale | Build time | Reproducibility |
|---|---|---|
| Starter | 0.7 s | 274 / 274 files identical across two builds |
| Full | 7.3 s (generate 2.3, run 1.5, evaluate 0.6, validate 1.1, export 1.1, dashboard 0.2, manifest 0.5) | 2,074 / 2,074 files identical across two builds |

**Validation summary:**
- Starter: PASS, 16 checks, 0 violations, 19 labelled defects.
- Full: PASS, 16 checks, 0 violations, 187 labelled defects.

Fault-injection tests show the suite fails on each of these: a payment for a blocked invoice (R34e),
a dangling event entity, an over-allocated GRN line, an orphan FK, and an illegal state
transition.

**SQL load** (`test_sql_seed_loads_with_foreign_keys_and_keeps_labels_separate`, both scales):
- `PRAGMA foreign_keys=ON`; `seed.sql`, then `evaluation_seed.sql`;
- `foreign_key_check` is empty after each, and `integrity_check` returns ok;
- row counts equal the CSVs for all 29 tables;
- an invalid enum UPDATE is rejected by CHECK, and an orphan vendor UPDATE by the FK;
- ground-truth and source tables appear only in `evaluation_seed.sql`.

**Reproducibility** (`reports/reproducibility.md`, committed for both scales):

| Scale | Tree SHA-256 (same seed) | Tree SHA-256 (seed 20261023) |
|---|---|---|
| Starter | `6207a33439c92182` | `959266cda5ff0e63` |
| Full | `53bab54c64d4b026` | `8d9cb76a3a66ef11` |

With seed 20261023, the core row counts are equal and every core table differs. The build in
`data/` equals the rebuilds.

**Committed data and parity:**
- Starter is complete: 274 files, 10.24 MB.
- Full: 15.23 MB committed. 33 files are excluded and regenerable (JSON exports, SQL seeds,
  `decision_trace.jsonl`, `extraction_field.csv`), with SHA-256 values in the manifest.
  `extraction_field.csv` was the ruling's next item, needed because starter's complete SQL and JSON
  add about 7.7 MB.
- Tracked data on disk is 25.9 MB (24.7 MiB), and the whole tracked tree is 26.9 MB. After
  `git gc`, the git pack is **3.42 MiB**.
- `test_committed_data_equals_a_fresh_build[starter|full]` rebuilds both scales and checks:
  - every committed file byte for byte against the fresh build;
  - every excluded file against the manifest checksum;
  - that no excluded file is tracked.
- `.gitignore` lists exactly the excluded groups, and a test ties them to the manifest rule.
  `.gitattributes` forces LF, now including `*.eml`.

**Queues** (full scale), open items per actor:

| Actor | Open items |
|---|---|
| Business requester | 485 |
| Operations analyst | 120 |
| Process owner | 70 |
| Approver | 2 pending approvals |
| System administrator | 20 |

**Dashboard:**
- Starter 0.2 MB, full 1.5 MB.
- No `http(s)://`, `<link>` or `src=`.
- Rebuilding gives identical bytes.
- The JavaScript was executed under node with a DOM stub: the explorer, the queue and the 5 tabs
  render.

**Tests: 541 pass** (3.13 in 39.7 s, 3.11 in 41.0 s), and `docs --check` is clean. The 20 new tests
are in `tests/test_outputs.py`. The shared fixture `complete_builds` runs the real `build` for
both scales.

## 3. Requirements and A-items

**Done in Stage 5** (`docs/requirements_traceability.md` updated):
- R1 (`build-all`), R2 (dashboard), R6 (queues);
- R17, R31, R32, R33, R35a-g, R36;
- A-50 (exports), A-54, A-61 (committed report), A-64.

**Stage-5 gate:**
- A-01 (one command), A-23 (exports), A-27, A-33 (matches the exports);
- A-51..A-54, A-61 (report), A-64 (manifest), A-69.

ADR-042 records the mechanics. The README now has a quickstart (`build-all`), a command table,
"What to open first", "Committed data and size budget" and the limitations.

## 4. Known gaps and notes

- The repository is about 25 MB of tracked data uncompressed, because both scales carry the
  readable CSVs and the documents. It is 3.4 MiB as a git pack.
- The dashboard is a static snapshot: its queues reflect the as-of date, not live updates.
- Stage 6 remains: S1-R1-09 (the candidate decides the author e-mail), the walkthrough, the
  AI-disclosure folder, the timeline-integrity check, the hand-off list and the final acceptance
  re-check.
