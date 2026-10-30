# Prompt 010 — Orchestrator → REV: Stage 2 review, round 1 (synthetic generator and ground truth)

DEV reports that Stage 2 is complete at commit `22c2e6a` on `main`.
- Report: `/home/claude/sprint/dev_reports/stage-2-report.md`.
- Log: `/home/claude/sprint/DEV_LOG.md`.
- Commands: CLI `generate` and `validate --quick`.
- Builds go to a git-ignored directory, per your Q3 ruling.

## Review against
- SPRINT_PLAN §4, Stage 2 DoD.
- The Stage 2 row of your gate map (ACCEPTANCE_CHECKLIST §E).
- The five Stage-2 checks you announced in `stage-1-review-2.md`:
  1. exact boundary construction;
  2. no accidental duplicate pairs (including A12 and the recurring true negatives);
  3. no completed event after 2026-10-22;
  4. vendor closures after all legitimate activity;
  5. over-receipt beyond tolerance reported as labelled.
- The Stage-2 carry-forward items.

Generate both scales yourself into your scratch area and check them with your own independent checker. Do not rely on
the repo's `validate --quick` alone. Look especially at:
- realism of the distributions (Evaluation Focus (a));
- lifecycle consistency across entities;
- whether every label is truly rule-derived (oracle vs intent), with nothing randomly assigned;
- whether ground truth stays out of the input tables.

## DEV's open points: give a ruling on each
1. Forwarding mailboxes are 10.3% of e-mails (35 of 340), the low end of ADR-037's 10–15% range. Should DEV switch to
   an exact quota? It would change the dataset hashes.
2. PAYMENT_DUE_DATE_PASSED and the 7 ADR-036 exception types do not occur in the generated data. The plan is
   unit-test fixtures plus "not present" metrics in Stage 4. Is that acceptable, or should some appear in the data?
3. The full build is 18.2 MB before invoice documents, against your Q3 budget of about 25 MB. The plan is compact JSON
   in Stage 5 if needed. Any guidance now?
4. Every date falls on a business day. Is that an acceptable simplification?

## Logistics
Write `/home/claude/sprint/reviews/stage-2-review-1.md` and update `FINDINGS_TRACKER.md`; if the harness blocks a
write, return the full text. Budget: the rolling 5-hour usage limit still applies, so stay economical. Reply in 12
lines or fewer.
