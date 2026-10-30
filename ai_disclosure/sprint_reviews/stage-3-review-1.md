# Stage 3 review, round 1 (REV): intake and field extraction

- **Commit reviewed:** `0a2ca58`, in a fresh clone at `reviews/scratch/s3/clone`. The repo itself was not touched.
- **Builds:** REV generated and ran both scales twice into `reviews/scratch/s3/b1` and `b2`.
- **Independent scripts:** `reviews/scratch/rev_s3_extract.py` (extraction vs source) and `rev_s2_check.py`.

**Verdict: PASS-WITH-NITS.** Stage 4 may start. The only open item is the old NIT S1-R1-09, which is for the
candidate.

## Summary
1. **Tests and determinism:** 503 tests pass and `docs --check` is green. The generate-and-run cycle under
   PYTHONHASHSEED=1 and =2 is byte-identical across all 2,290 files, documents and processed output included.
2. **Extraction (REV's own script, captured vs `source/` joined on doc_id):**
   - Full scale: 46,640 fields compared, 8 mismatches. Those are invoice_date 3, vendor_invoice_number 2 and
     header_gross 3, all on LOW_CONFIDENCE documents. Silent errors: 0.
   - Starter: 4,574 fields, 0 mismatches.
   - Invoice-ID agreement (ID-01): 2,000/2,000 and 200/200.
3. **Blind run:** with only `master/` and `inbox/` copied (no `ground_truth/`, no `source/`), `processed/` is
   identical (`diff -rq` is empty).
4. **REV corruption probe** (scratch copy, 16 documents, 4 per channel):
   - every truncated document (4/4) is flagged;
   - every changed invoice-number digit (12/12) is read as printed;
   - no value is ever silently restored.
5. **Document leak scan:** 0 hits in 2,000 documents for scenario codes, category names, label words or `INV-VND-`.
6. **S2-R1-01** and **S2-R1-02** are closed and verified. The Q1, Q3 and Q4 actions are done.

## Stage-3 checklist

| Item | Status | REV evidence |
|---|---|---|
| A-02 intake | met | The manifest's SHA-256 and byte counts are filled. Rerunning the same inbox gives byte-identical output. Four channel formats are used |
| A-03 extraction | met | Per-channel adapters with confidence values. The 120-digit mutation test, the 5 damage modes, and REV's own probe all hold |
| A-10 boundary (runtime) | met | The blind run is identical. `test_blind_run_is_byte_identical` and `test_id_blind_run_gives_identical_decisions` are present and pass |
| A-41 printed total survives extraction | met | REV comparison: header_gross differs only on the 3 flagged scans; all 15 wrong printed totals are captured as printed |
| A-50 no leakage | met | Document scan has 0 hits. The engine reads only `master/` and `inbox/` (blind run) |
| A-55 extracted fields match source | met | 0 silent errors. Every mismatch is LOW_CONFIDENCE and routed to the operations analyst |
| P-3 vendor from the document | met | ID-blind sandbox test; a forged sender raises VEN-04 without changing the vendor; ID agreement is 100% |
| S2-R1-01 | verified | `rev_s2_check.py` on the Stage-3 build reports "PROBLEMS: none" (no empty required fields) |
| S2-R1-02 | verified | README lines 60–61 state the business-days-only limitation |

## Findings
No new findings.

## Rulings on DEV's open points
1. **Data budget (26.5 MB).** Apply the Q3 rule as written:
   - Do not commit the full-scale JSON exports; record their SHA-256 values in the manifest.
   - Starter stays complete, in every format.
   - If Stage 4 growth pushes the full commit back over about 25 MB, drop more from the full-scale commit in this
     order: `decision_trace.jsonl` first, then `extraction_field.csv`. Both are regenerable and checksummed, and the
     README must say so.
   - The full-scale CSVs for master, inbox, source, ground truth and the core processed tables stay committed.
2. **VEN-04 not yet behind the duplicate gates: accepted for Stage 3.** Stage 4 must:
   - enforce the documented precedence;
   - include a test where a duplicate document with a forged sender is reported with the DUPLICATE_* primary issue,
     and VEN-04 is not evaluated, or is only secondary per the docs.
3. **Unknown tax code treated as unreadable: accepted.** A string that is not a tax code is a capture problem.
   `GST12` is a known code in `engine/normalize.py`, so a retired code still reaches TAX-01. Stage 4 needs a unit test
   in which a 2026 invoice printing GST12 raises TAX_CODE_INVALID.

## Carry-forward
- **Stage 4:**
  - rulings 2 and 3;
  - time-travel sandbox;
  - "not present" metrics for the 8 absent types;
  - at least one GRN line allocated to at least two invoice lines (A-26);
  - per-invoice acceptance report (A-60).
- **Stage 5:** apply ruling 1; committed data equals a fresh build (A-54).
- **Stage 6:** S1-R1-09.

## Regression check
- REV's Stage-2 checker on the Stage-3 build:
  - counts, mix and edge cases unchanged;
  - all rule label sets still equal REV's recomputation;
  - 100 duplicate pairs;
  - as-of limit OK.
- No regression.
