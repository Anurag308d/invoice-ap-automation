# Prompt 009 — Orchestrator → DEV: Stage 2 assignment (synthetic data generator and ground truth)

Stage 1 is closed: REV gave **PASS-WITH-NITS** at `66b1f07` (`reviews/stage-1-review-2.md`). The only open item is the
NIT S1-R1-09, which belongs to the candidate. The Stage-1 spec is now the contract. If implementation forces a spec
change, update the docs and data dictionary and add an ADR in the same commit; `docs --check` must stay green.

## Scope (SPRINT_PLAN §4, Stage 2)
Implement the generator exactly as specified:
- Tables are generated in order: master → child → transactional → event.
- IDs are deterministic; the default seed is 20261022; scale is `starter` / `full` (or a numeric factor); both scales
  use one code path.
- Full scale gives exactly 300 / 1,500 / 2,200 / 1,800 / 2,000 records, with the specified mix (including
  CAPTURE_REVIEW = 10 and clean = 1,350).
- The valid baseline is built first. All 8 edge cases and every sub-scenario or archetype in your plan (including A12)
  are injected after it and labelled, without silently corrupting unrelated rows.
- Derived values (totals, tax, balances, scores, statuses, dates) are computed from source records.
- Generator-side history is append-only: vendor status history with effective dates, plus PO and GRN lifecycle
  events.
- Ground truth goes to its own folder as `ground_truth.csv` and `ground_truth.json`. It comes from the rule-based oracle
  applied to the true data, and generation fails loudly if any oracle outcome differs from the injection intent. Never
  put labels in input tables.
- Invoice documents and the inbox are Stage 3. In this stage, generate only the structured source invoices and lines
  the documents will later be rendered from, unless your design needs a stub now.
- Outputs are CSV and JSON. Use no wall-clock time and no unseeded randomness.

## REV has said the Stage-2 review will test these, so build them deliberately and prove them in tests
1. Boundary cases are exact: a price at +2.00% to the cent, a price just inside and just outside tolerance, and a
   quantity at the 5% over-receipt limit and just beyond it. Construct each with exact `Decimal` arithmetic so rounding
   cannot push it across the line.
2. There are no accidental duplicate pairs. Only labelled duplicates may collide on vendor + normalised invoice number,
   or on your fuzzy-duplicate keys. Pay special attention to the two invoices of each A12 PO and to recurring
   same-amount true negatives.
3. No completed event falls after the as-of date, 2026-10-22, and a test enforces it.
4. Vendor closures come after all of that vendor's legitimate activity. The only post-closure activity allowed is the
   labelled closed-vendor invoices.
5. Over-receipt beyond tolerance is a labelled scenario, not a data error. The self-checks must report it as expected.
6. The carry-forward items for Stage 2 are in your `DEV_LOG.md` and in `reviews/stage-1-review-1.md` and
   `reviews/stage-1-review-2.md`. Close every one of them.

## Self-checks, needed now even though the full validation suite is Stage 5
- The generator, or a `validate --quick` command, checks:
  - PK uniqueness;
  - FK integrity;
  - allowed enums;
  - date ordering;
  - arithmetic (line → header);
  - lifecycle-event order;
  - mix and edge-case counts against target at both scales;
  - the oracle-vs-intent assertion.
- A quick determinism check: generate twice with the same seed and confirm identical SHA-256 for every output file.
  Also confirm the result does not depend on `PYTHONHASHSEED` (run it with two different values).
- Unit tests for the generator:
  - counts and ID regexes;
  - the vendor-code embedding;
  - FK validity, arithmetic and edge-case presence;
  - boundary exactness;
  - the no-future-event rule and the no-accidental-duplicate rule;
  - determinism.

## Repository rules for this stage
Per REV's Q3 ruling, do not commit generated datasets yet. Write them to a git-ignored build directory; data is
committed only when Stages 5 and 6 close. Keep the full build fast and report how long it takes.

## Finish
- Write `/home/claude/sprint/dev_reports/stage-2-report.md` covering what was built, the requirement and A-item IDs
  covered, evidence (commands plus short excerpts: counts table, mix table, edge-case table, determinism hashes, test
  summary), distribution stats (evidence for Evaluation Focus (a)), and known gaps.
- Update `DEV_LOG.md`.
- Commit with meaningful message(s) and the required trailers. Intermediate commits are welcome when they mark real
  progress.
- Budget: the account has a rolling 5-hour usage limit, so work efficiently.
- Reply in 15 lines or fewer.
