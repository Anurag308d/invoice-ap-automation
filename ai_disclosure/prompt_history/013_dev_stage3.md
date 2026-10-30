# Prompt 013 — Orchestrator → DEV: Stage 3 assignment (invoice intake and field extraction)

Stage 2 is closed: REV gave **PASS-WITH-NITS** at `22c2e6a` (`reviews/stage-2-review-1.md`). Read that review first.
In this stage's commit, include:
- NIT S2-R1-01: ground-truth list fields and manifest fields that are marked required but are legitimately empty.
- Q1: keep the random draw and reword ADR-037.
- Q3: switch to compact JSON now.
- Q4 (S2-R1-02): add business-days-only to the documented limitations.
- Q2 needs no action yet; it is Stage 4 work.

## Scope (SPRINT_PLAN §4, Stage 3)
- Render every invoice into its intake channel per your spec: at least 3 heterogeneous formats, vendor templates,
  recoverable variation, and the CAPTURE_REVIEW degraded scans. Write the intake manifest without invoice_id, with
  sender_vendor_id for PORTAL/EDI only (ADR-037).
- Build the extraction engine:
  - one adapter per channel;
  - label synonyms and normalisation;
  - per-field confidence;
  - printed values are never corrected (the ARITHMETIC defect must survive);
  - the vendor is resolved from document content (the printed tax ID);
  - the engine assigns invoice IDs (`INV-<vendor>-2026-<seq>`) and line IDs;
  - the VENDOR_SENDER_MISMATCH check;
  - low confidence routes to the operations analyst.
- Build the extraction evaluation against `source/`:
  - field-level and document-level accuracy, per channel and per field;
  - a mismatch listing;
  - JSON and Markdown output.
- Target: every non-degraded invoice matches the source on every field. The degraded ones must be flagged, never wrong
  without a flag.
- Credibility tests (REV's P-2):
  - negative and mutation tests: corrupt documents in a temp copy and assert the extractor either flags them or
    produces the corrupted value, never a silent "correct" value from somewhere else;
  - tests for tricky formats.
- Boundary enforcement:
  - the static ban already exists;
  - add the ID-blind sandbox test REV specified. Hide or delete `ground_truth/` and `source/`, and remove the
    manifest's sender vendor where your spec says it is optional; the engine's extraction outputs must be identical, or
    the decisions identical for the parts that do not depend on the sender.

## Finish
- Write `dev_reports/stage-3-report.md` with evidence (accuracy tables, test summary, determinism), and update
  `DEV_LOG`.
- Commit with the required trailers. Do not commit generated data.
- Budget: rolling 5-hour usage limit, so be efficient.
- Reply in 15 lines or fewer.
