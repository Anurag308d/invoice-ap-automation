# Prompt 017 — Orchestrator → DEV: Stage 5 assignment (validation suite, exports, manifest, reproducibility, CLI and dashboard)

Stage 4 is closed: REV gave **PASS-WITH-NITS** at `ad005fb` (`reviews/stage-4-review-1.md`). In this stage, include:
- NIT S4-R1-01: `evaluation.md` must be human-readable, with no raw Python dicts, and include the KPI definitions.
- The overdue-backlog ruling: label it "past SLA at the snapshot, no resolutions simulated", add age buckets, and list
  it as a README limitation.
- The budget ruling: measure the real committed size, put checksums of the excluded full-scale files in the manifest,
  and prove the committed data equals a fresh build.

## Scope (SPRINT_PLAN §4, Stage 5)
- **Validation suite** over all tables:
  - PK uniqueness and FK integrity (every join);
  - allowed enums and date ordering;
  - arithmetic reconciliation;
  - lifecycle transitions (replayed from the event logs);
  - duplicate checks, aware of labelled defects.

  Output `validation_summary.json` and `.md`.
- **Exports:**
  - CSV and JSON for every table;
  - a SQL seed: DDL with PK / FK / CHECK constraints plus INSERTs. Load it into SQLite with `foreign_keys=ON` and
    confirm `foreign_key_check` is clean, with a test.

  Ground truth stays out of the seed's input tables (REV P-4): ship it separately or in a clearly separate schema, and
  record that in the manifest.
- **`source_manifest.json`:** generator version, exact command, seed, scale, policy version, every file with its row
  count and SHA-256, and provenance (100% synthetic, no external data, licences).
- **Reproducibility command:** two runs with the same seed into separate directories, comparing row counts and
  checksums, plus a different-seed sanity run. Save the report.
- **One command** builds everything for both scales.
- **Role-based queue CLI** for the five actors.
- **Offline HTML dashboard:** self-contained, deterministic, no CDN. It shows KPIs, a queue per actor, invoice
  decision traces, the evaluation and validation results.
- **Commit the generated data** (starter in full; full scale per the budget ruling) once Stage 5 is complete, together
  with a test or check proving it equals a fresh build. Keep `.gitattributes` LF so the checksums survive Windows.

## Finish
- Write `dev_reports/stage-5-report.md` with evidence (validation summary, SQL load, reproducibility hashes, repo size),
  and update DEV_LOG.
- Commit with the trailers.
- Be efficient: the rolling 5-hour usage limit still applies.
- Reply in 15 lines or fewer.
