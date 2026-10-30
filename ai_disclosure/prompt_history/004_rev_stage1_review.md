# Prompt 004 — Orchestrator → REV: Stage 1 review, round 1

DEV reports that Stage 1 is complete at commit `12f551a` on `main`.
- DEV's report: `/home/claude/sprint/dev_reports/stage-1-report.md`. Read it, but verify everything independently.
- DEV's running log: `/home/claude/sprint/DEV_LOG.md`.

Review Stage 1 against two things: the Stage 1 Definition of Done in SPRINT_PLAN §4, and the Stage 1 row of the gate
map in your ACCEPTANCE_CHECKLIST.md §E. Use the review protocol in your brief (`prompts/002_rev_brief.md`). Run the
test suite and any allocation or proof scripts yourself, and confirm that the docs generated from code really match the
code.

Give a ruling on each of DEV's open questions in your review:
1. Clean is 68.0% (1,360 of 2,000), because the two extra edge cases (invoice total ≠ line sum, invoice date before PO
   date) take 1% each from clean. Is this acceptable, or should those cases be folded into documented category families
   so clean stays at 1,400?
2. There are 10 degraded-scan invoices at full scale and 1 at starter, used to exercise the low-confidence extraction
   route. Should they count as clean, or as their own labelled category?
3. Is committing a full build of roughly 30–45 MB acceptable, or should the repo commit only the starter build plus the
   full-build manifest and checksums?
4. Is a flat package layout (`invoice_ap/` at the repo root, not `src/`) acceptable?

The orchestrator raises one more point for you to rule on; accept or reject it on the merits. DEV evaluates everything
"as of 2026-12-31". The submission date is October 2026, so the dataset would contain invoices, receipts and decisions
dated after the day the candidate submits. Is that sensible, or should the as-of date (and the data window) end on or
before a fixed past date, for example 2026-10-22, which matches the seed?

Logistics:
- Write `/home/claude/sprint/reviews/stage-1-review-1.md` and update `FINDINGS_TRACKER.md`. The orchestrator has
  already created the tracker with your header.
- If the harness blocks either write, put the complete review, plus the cumulative tracker table, in your reply. There
  is no length limit in that case, and the orchestrator will save it verbatim.
- If both writes succeed, keep your reply to 12 lines or fewer.
