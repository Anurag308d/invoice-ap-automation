# Prompt 016 — Orchestrator → REV: Stage 4 review, round 1 (decision engine and evaluation)

DEV reports that Stage 4 is complete: commit `d105b00`, plus the value-at-risk fix `ad005fb`. Report:
`/home/claude/sprint/dev_reports/stage-4-report.md`.

Review it against:
- SPRINT_PLAN §4, Stage 4;
- the Stage 4 row of your gate map;
- the Stage 4 carry-forwards: the time-travel sandbox, the absent exception types, the VEN-04 precedence and GST12.

Verify independently with your own scripts. Three things matter most. First, whether R34a–e really hold per invoice.
Second, whether the policy is applied correctly: recompute a sample of match, approval-level and payment decisions from
the policy TOML by hand or by script. Third, whether the 100% agreement with ground truth is credible rather than
circular; do your own mutation probe. Also check the event log against the state machines, routing to the five
actors, the bridge exercised in both directions, payments only for eligible invoices, and the KPIs' definitions.

Give a ruling on DEV's open points:
1. The 32.6 MB full scale comes to about 23.5 MB across both scales once your budget ruling is applied in Stage 5.
2. No exception is resolved within the snapshot, so almost all open exceptions are overdue at the as-of date. Is that
   realistic, or should SLA dates and intake timing change?

Write `reviews/stage-4-review-1.md` and update the tracker. Be economical. Reply in 12 lines or fewer.
