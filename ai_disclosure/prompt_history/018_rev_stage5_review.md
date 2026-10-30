# Prompt 018 — Orchestrator → REV: Stage 5 review, round 1 (validation, exports, manifest, reproducibility, CLI and dashboard)

DEV reports that Stage 5 is complete at `8a6c8b6`, with data now committed. Report:
`/home/claude/sprint/dev_reports/stage-5-report.md`.

Review it against SPRINT_PLAN §4, Stage 5, the Stage 5 row of your gate map, and your budget and P-4 rulings.

Verify independently:
- Start from a fresh `git clone` into scratch. Run `build-all` and confirm the committed data equals your fresh build,
  and that excluded files match the manifest checksums.
- Load both SQL seeds into SQLite with foreign keys on and check `foreign_key_check` and the row counts.
- Confirm the validation suite catches faults you inject yourself.
- Confirm ground truth is absent from the main seed.
- Check the dashboard is offline and deterministic, and the queue CLI covers the five actors.
- Confirm `.gitattributes` keeps LF.

Give a ruling on DEV's open point: tracked data is 25.9 MB on disk (24.7 MiB), slightly over the roughly 25 MB budget,
and the git pack is 3.4 MiB. Is that acceptable?

Write `reviews/stage-5-review-1.md` and update the tracker. Be economical. Reply in 12 lines or fewer.
