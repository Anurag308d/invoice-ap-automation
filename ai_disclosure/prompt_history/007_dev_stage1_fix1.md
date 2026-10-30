# Prompt 007 — Orchestrator → DEV: Stage 1, fix round 1

REV's verdict on Stage 1 (commit `12f551a`) is **REVISE**: 0 BLOCKER, 1 MAJOR, 7 MINOR, 1 NIT.
- Review: `/home/claude/sprint/reviews/stage-1-review-1.md`. Read it in full.
- Tracker: `/home/claude/sprint/reviews/FINDINGS_TRACKER.md`.

## What to do
1. Fix S1-R1-01 (MAJOR) and S1-R1-02 through S1-R1-08 (MINOR). Each fix must meet the acceptance test REV wrote for
   that finding.
   - S1-R1-01 is the important one. The engine must not be able to get the true vendor for free from the manifest or
     from the invoice_id. Choose REV's option (a) or (b), or both, record the choice as an ADR, and make sure the Stage-3
     plan has the static ban and the ID-blind sandbox test REV describes.
   - S1-R1-09 (NIT, the commit author e-mail) is the candidate's decision at hand-off. Take no action.
2. Apply REV's rulings consistently across the spec, the policy, the allocation tables, the generated docs and the
   tests:
   - Q1: clean at 68% is accepted.
   - Q2: degraded scans become their own labelled category, so clean is 1,350 (67.5%).
   - Q3: committing the full build is fine under REV's conditions: committed data ≲ 25 MB, committed only when Stages 5
     and 6 close, and a check proves it equals a fresh build.
   - Q4: the flat layout is accepted.
   - The as-of date is now a fixed past date (S1-R1-04; REV recommends 2026-10-22). No completed event may fall after
     it, so the data window, lead times and SLA dates need to be re-derived.
3. Read the review's carry-forward section and record those items in your DEV_LOG plan for the stages they belong to.
   Implement later-stage work only where the spec itself needs it.
4. Re-run the full test suite, `docs --check`, and your allocation proof at both scales.
5. Write `/home/claude/sprint/dev_reports/stage-1-response-1.md`, mapping finding ID → change → evidence (a command
   plus a short output excerpt).
6. Commit with a meaningful message such as `stage-1 fix-1: …` and the required trailers.
7. Budget: the account has a rolling 5-hour usage limit. Make targeted edits, keep tool output small, and don't re-read
   large files you already know.
8. Reply to the orchestrator in 10 lines or fewer: commit hash, the status of each finding, and anything you disagree
   with (with your reason).
