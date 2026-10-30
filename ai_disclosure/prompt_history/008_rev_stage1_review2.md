# Prompt 008 — Orchestrator → REV: Stage 1 re-review (round 2)

DEV has committed fix round 1 as `66b1f07` and reports every MAJOR and MINOR finding fixed. S1-R1-09 (NIT) was
deliberately left for the candidate's hand-off.
- DEV's response, with evidence for each finding: `/home/claude/sprint/dev_reports/stage-1-response-1.md`.
- Notable changes:
  - ADR-037: the manifest drops invoice_id and keeps sender_vendor_id for PORTAL/EDI only; the engine assigns IDs
    after printed-tax-ID vendor resolution; new blocking VENDOR_SENDER_MISMATCH check.
  - ADR-038: snapshot_* columns are reporting-only, with a static ban.
  - New CAPTURE_REVIEW category (clean = 1,350).
  - as-of date 2026-10-22, with the time model re-derived.
  - Archetype A12 for the N:M direction.
  - Spec completeness, label-truncation and traceability updates.

## What to do
Follow your re-review rules:
1. Verify each finding S1-R1-01 to S1-R1-08 individually, with your own evidence. Re-run your
   `scratch/rev_s1_check.py` (update it if the spec moved), the test suite and `docs --check`.
2. Check for regressions, especially volume and mix exactness at both scales after the CAPTURE_REVIEW change and the
   A12 archetype, and time-model consistency now that the as-of date is 2026-10-22.
3. Raise new findings only if they are real.
4. Write `/home/claude/sprint/reviews/stage-1-review-2.md` and update `FINDINGS_TRACKER.md`.

Verdict: PASS or PASS-WITH-NITS lets Stage 2 start. Budget: the rolling 5-hour usage limit still applies, so stay
economical. Reply in 12 lines or fewer.
