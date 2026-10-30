# Prompt 014 — Orchestrator → REV: Stage 3 review, round 1 (intake and field extraction)

DEV reports that Stage 3 is complete at commit `0a2ca58`. Report: `/home/claude/sprint/dev_reports/stage-3-report.md`.

Review it against:
- SPRINT_PLAN §4, Stage 3;
- the Stage 3 row of your gate map;
- your P-2 and P-3 guards (mutation and negative tests, vendor resolved from the document, the ID-blind sandbox);
- the closure of S2-R1-01 and the Q1, Q3 and Q4 actions.

Verify independently:
- Compare the extraction output against `source/` with your own script.
- Run your own corruption probe on a scratch copy.
- Do the blind run (delete `ground_truth/` and `source/`) and diff the outputs.
- Check determinism.

Give a ruling on DEV's open points:
1. The data budget: the full build is 26.5 MB (9.8 MB of it full-scale JSON). Without the full-scale JSON it is about
   19.4 MB, and `extraction_field.csv` will grow in Stage 4.
2. The sender check is not yet ordered behind the duplicate checks; that happens in Stage 4.
3. An unknown tax code is treated as unreadable, so the invalid-tax-code exception exists only in unit tests.

Write `reviews/stage-3-review-1.md` and update the tracker. Be economical. Reply in 12 lines or fewer.
