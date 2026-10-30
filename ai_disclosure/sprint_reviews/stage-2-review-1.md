# Stage 2 review, round 1 (REV): synthetic generator and ground truth

- **Commit reviewed:** `22c2e6a`, in a fresh clone at `reviews/scratch/s2/clone`. The repo itself was not touched.
- **Builds:** REV generated both scales twice into `reviews/scratch/s2/b1` and `b2`.
- **Checker:** `reviews/scratch/rev_s2_check.py`. It uses only the standard library, reads the CSVs and the JSON spec,
  and never imports repo code.

**Verdict: PASS-WITH-NITS.** Stage 3 may start.

## Summary
1. **Build and tests:** 456 tests pass. The two builds, one with PYTHONHASHSEED=1 and one with =2, are byte-identical
   across all 80 files. Generation takes about 2.2 s at full scale and 0.2 s at starter.
2. **Volumes and mix are exact** at both scales:
   - full: 300 / 1,500 / 2,200 / 1,800 / 2,000;
   - mix: CLEAN 1,350, PV 200, QM 160, DUP 100, MR 80, TV 60, ARITH 20, IBP 20, CAPTURE 10;
   - edge cases EC-01..08 = 35 / 15 / 20 / 550 / 15 / 30 / 50 / 65 (starter 3 / 1 / 2 / 55 / 1 / 3 / 5 / 7).
3. **Labels match REV's own recomputation exactly.** REV recomputed each rule from the raw data and compared it with
   the ground-truth labels by set equality:
   - HEADER_TOTAL, LINE_AMOUNT, TAX_AMOUNT and TAX_CODE mismatches;
   - PRICE_VARIANCE (200), INVOICE_BEFORE_PO;
   - VENDOR_CLOSED and VENDOR_BLOCKED, from effective-dated history;
   - VENDOR_PO_MISMATCH;
   - MISSING_RECEIPT, using receipts posted before intake;
   - all 100 duplicate pairs, using DUP keys in intake order.

   Every set matched exactly at both scales.
4. **Labels are rule-derived, not random.** The oracle has no RNG calls. When REV raised the price tolerance to 2.50%
   in a scratch copy, generation failed loudly with `OracleMismatch` ("PV-BOUNDARY-OUT: oracle [] != intended
   ['PRICE_VARIANCE']").
5. **Ground truth stays out of the inputs.** A scan of master and inbox found no scenario codes, category names or
   label words in any header or value. Evaluation exports sit separately under `exports/json/evaluation/`.
6. **Two NITs only:**
   - list fields flagged "required" but legitimately empty (plus the manifest fields pending until Stage 3);
   - every date falls on a business day.

## Stage-2 checklist (gate-map row, SPRINT_PLAN §4 Stage-2 DoD, and the five announced checks)

| Item | Status | REV evidence |
|---|---|---|
| A-13 / A-21 build order and generator history | met | Build sequence: plan → baseline (0/0) → final → oracle → validate → write. ERP event replay: 0 chain breaks and 0 time-order breaks. Transitions are only `-`→ISSUED, ISSUED→PARTIALLY_RECEIVED, PARTIALLY_RECEIVED→RECEIVED, ISSUED→RECEIVED and `-`→POSTED. Every PO and GRN snapshot equals its last event |
| A-14 / A-15 / A-16 / A-17 / A-18 | met | Header = spec order, PK unique, patterns, enums and FKs: 0 orphans in all layers. No PO or GRN exists while its vendor is not ACTIVE. 30 PO lines are over-received beyond 5%, and all belong to labelled scenarios. Totals recompute in Decimal |
| A-22 labels from rules | met | Oracle = intent assertion; tolerance-mutation probe fails loudly; no RNG in `oracle.py` |
| A-28 no collateral corruption | met | Every REV-detected defect set equals its label set, so no unlabelled row carries a defect. DEV's baseline-vs-final test is also present |
| A-29 / A-30 / A-32 IDs | met | All spec patterns hold. Two builds are byte-identical. Duplicates collide only on the vendor number, never on a PK |
| A-34 / A-36 / A-38 / A-39 | met | Counts, mix and edge cases exact at both scales. `--seed` defaults to 20261022. Baseline phase validates 0/0 |
| A-40..A-47 edge cases | met (data side) | REV set equality on 9 rule families plus duplicate pairs; detection itself comes in Stage 4 |
| A-48 boundaries | met | Full scale: C-PRICE-AT-TOL 20 lines exactly +2.00%, C-PRICE-INSIDE 20 below, PV-BOUNDARY-OUT 20 above |
| A-49 derived values | met | Header and line arithmetic recomputed; only labelled lines differ |
| A-50 GT separation and no leakage | met | Label-vocabulary scan of master and inbox is clean; GT and source sit in separate folders and exports |
| A-61 realism (Evaluation Focus a) | met (NIT) | DEV's summary is consistent with REV's spot checks: vendor concentration (top 20% carry 77.7% of POs), lognormal medians by category, lead times by category, terms and channel mix, intake hours spread from 09:00 to 17:00. Weekday share is 100% (NIT S2-R1-02) |
| A-63 cross-entity lifecycle | met | No completed timestamp after 2026-10-22 across PO, GRN, ERP events, vendor history, intake and invoice dates. invoice_date ≤ received date for all 2,000 invoices |
| A-65 / A-66 Decimal and determinism | met | Decimal recompute matches; PYTHONHASHSEED probe shows byte identity |
| A-72 generator tests | met | `tests/test_generator.py` covers 35 cases, including loud failure, determinism and as-of |
| Check 1: exact boundaries | met | See A-48. Quantity boundaries are covered by DEV's test and are consistent with the over-receipt result |
| Check 2: no accidental duplicate pairs | met | REV's independent DUP-01/02/03 key scan finds 100 pairs, identical to the labelled pairs |
| Check 3: nothing after the as-of date | met | See A-63 |
| Check 4: closures after activity | met | 0 POs or GRNs while the vendor is not ACTIVE. The 7 POs dated after a status change belong to vendors reactivated after 2025 blocks (KYC_RENEWED) |
| Check 5: over-receipt reported as labelled | met | 30 over-tolerance PO lines; every non-duplicate invoice on them is labelled QTY_EXCEEDS_PO |

## Findings

### S2-R1-01 · NIT · A-33, A-51 (R20, R31): "required" list fields and pending manifest fields are empty
- **Finding:** REV's spec check reports "empty required" for these fields, which the spec flags as required:
  - `ground_truth.edge_case_ids`, `intended_issue_types`, `expected_issue_types`, `expected_assigned_roles` and others.
    These are legitimately empty for clean invoices.
  - `intake_manifest.file_sha256` and `file_bytes`, which are pending until Stage 3 (ADR-039).

  The data is correct, but taken literally the dictionary's "required" contradicts it. A strict evaluator, or the
  Stage-5 validation suite, would count these as violations.
- **Fix (by the Stage-3 commit):**
  - Define list semantics in the spec, e.g. "required = column always present; an empty list is allowed" (or
    required=False with an explicit rule).
  - Fill the manifest file fields in Stage 3.
- **Acceptance test:** `rev_s2_check.py` on a Stage-3 build reports no "empty required" entries.

### S2-R1-02 · NIT · A-61 (Evaluation Focus a): every date falls on a business day (DEV Q4)
- **Finding:** 100% of PO dates, receipts, invoice dates and intake timestamps fall on business days.
- **Fix:** acceptable as a documented simplification; state it in the README limitations. Optional: a small weekend
  share for invoice dates or PORTAL/EDI arrivals, with SLA and payment arithmetic still on business days.

## Rulings on DEV's open points
1. **Forwarding mailboxes at 10.3%: keep the independent 15% draw.** No quota is needed. Reword ADR-037 to "drawn at
   15% per e-mail original; realised 10.3% of e-mail documents (11.1% of originals)".
2. **The 8 absent exception types: accepted.** These are the 7 ADR-036 types plus PAYMENT_DUE_DATE_PASSED. Stage 4
   must:
   - give each a hand-computed unit fixture through the engine;
   - report each as "not present" in the per-type metrics, with no division by zero;
   - list them in the README limitations.

   The ID-blind sandbox (Stage 3) remains the evidence for VENDOR_SENDER_MISMATCH and vendor resolution.
3. **Size guidance:**
   - Write compact JSON now: no indent, `sort_keys`, separators `(",", ":")`.
   - Measure with documents in Stage 3.
   - If the committed total would exceed about 25 MB, leave the full-scale JSON exports out of the commit and keep
     their checksums in the manifest. CSV and SQL stay.
4. **Business days only: accepted** as a documented simplification (S2-R1-02).

## Carry-forward
- **Stage 3:**
  - fill `file_sha256` and `file_bytes` (S2-R1-01);
  - runtime blind run and ID-blind sandbox;
  - extraction negative and mutation tests;
  - the starter set exercises the single CAPTURE_REVIEW scan.
- **Stage 4:**
  - time-travel sandbox;
  - "not present" metrics (ruling 2);
  - at least one GRN line allocated to at least two invoice lines (A12 data present);
  - invoice-ID agreement as a vendor-resolution outcome.
- **Stage 5:** committed data equals a fresh build, plus the size ruling above.
- **Stage 6:** S1-R1-09 author e-mail; README limitations (business days only; approver rejection not simulated).

## Regression check
Not applicable (first Stage-2 round). Stage-1 items still hold: `docs --check` is green, and the spec, routing and
allocation are unchanged apart from the changes recorded in the report (turnaround values, list wording).
