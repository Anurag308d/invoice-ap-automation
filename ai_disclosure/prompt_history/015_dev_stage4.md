# Prompt 015 — Orchestrator → DEV: Stage 4 assignment (decision engine and evaluation)

Stage 3 is closed: REV gave **PASS-WITH-NITS** at `0a2ca58` (`reviews/stage-3-review-1.md`). Read that review, including
its rulings:
- Budget: don't commit the full-scale JSON; if a commit goes over about 25 MB, drop `decision_trace.jsonl` first, then
  `extraction_field.csv`.
- VEN-04 precedence: test that a duplicate with a forged sender reports DUPLICATE as its primary issue.
- GST12: a 2026 invoice that prints the retired code must still raise the invalid-tax-code exception.

## Scope (SPRINT_PLAN §4, Stage 4), implemented per your spec
- **Header validation:** vendor status at invoice date, vendor identity, PO existence and PO vendor, date rules,
  header-vs-lines arithmetic, tax.
- **Duplicate detection:** exact resubmission vs number reuse; output pairs (duplicate → original); true negatives must
  stay clean.
- **Three-way match per line:** cumulative quantities, price / quantity / tax tolerances, missing receipt, exceeds-PO,
  over-receipt, partial delivery, and the A12 N:M allocation bridge exercised in both directions. Derive the match
  status with the documented precedence.
- **Exceptions:** type, severity, blocking flag, expected vs actual, tolerance, actor role and queue, SLA due date,
  status.
- **Routing:** to the five actors.
- **Approvals and payments:** approvals only for eligible invoices, per the matrix; payments only for unblocked,
  fully approved invoices (payment-ready).
- **History and explainability:** an append-only event log validated by the state machine, current status equal to the
  last event, and a per-invoice decision trace (`explain`).
- **Time-travel sandbox (REV's carry-forward):** no decision depends on the `snapshot_*` columns or on information from
  after the as-of date.
- **Exception types absent from the data** (Q2): each gets a unit-test fixture, and the metrics report them as "not
  present".
- **Evaluation vs ground truth:**
  - per-type precision, recall and F1, and a confusion matrix on the primary outcome;
  - duplicate pair accuracy, approval-level agreement, payment-ready safety (0 blocked invoices marked ready);
  - STP rate and value at risk;
  - output in JSON and Markdown.
- **Per-invoice acceptance check over all invoices (R34a–e):**
  - extracted fields equal the source;
  - arithmetic and tax reconcile;
  - the duplicate pair is correct;
  - match and approval outcomes agree with policy;
  - no blocked invoice is payment-ready.

  Report pass/fail counts; any deviation must be explained.
- Close every Stage-4 carry-forward item in DEV_LOG and the reviews.

## Finish
- Write `dev_reports/stage-4-report.md` with evidence, and update DEV_LOG.
- Commit with the trailers. Don't commit data.
- Be efficient: the rolling 5-hour usage limit still applies.
- Reply in 15 lines or fewer.
