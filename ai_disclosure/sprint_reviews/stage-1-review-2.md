# Stage 1 review, round 2 (REV): re-review of fix round 1

- **Commit reviewed:** `66b1f07` on `main`, checked in a fresh clone at `reviews/scratch/s1r2/clone`. The repo itself
  was not touched.
- **Diff since round 1:** `12f551a..66b1f07`, 28 files changed (+1203 / −482).
- **DEV response:** `dev_reports/stage-1-response-1.md`.

**Verdict: PASS-WITH-NITS.** Stage 2 may start.

## Summary
1. All eight MAJOR and MINOR findings are fixed and verified with REV's own evidence.
2. The only item left open is NIT S1-R1-09, deferred to the candidate's Stage-6 hand-off.
3. 421 tests pass on Python 3.13, 3.11 and 3.12.
4. Regenerating the docs gives zero diff, and `docs --check` passes. The policy is valid, with as-of 2026-10-22 and 24
   routed types.
5. REV's independent checker, extended with the new S12 placement, passes at both scales:
   - exact 300 / 1,500 / 2,200 / 1,800 / 2,000;
   - CLEAN 1,350 (67.5%) and CAPTURE_REVIEW 10, at starter 135 and 1;
   - all 41 sub-scenarios ≥ 1, edge-case counts unchanged;
   - the spec has every checked attribute.
6. No regressions, and no new findings.

## Re-verification of each finding

| ID | Status | REV evidence |
|---|---|---|
| S1-R1-01 MAJOR | **verified** | The `intake_manifest` fields are now `doc_id, intake_seq, channel, file_format, received_at, sender_address, sender_vendor_id, file_path, file_sha256, file_bytes`; there is no `invoice_id`. `sender_vendor_id` has required=False, required_when "channel in (PORTAL, EDI)". `captured_invoice.invoice_id` has origin=decided and rule "ID-01: INV-<VEN-01 vendor_id, or VND-00000 if unresolved>-2026-<intake_seq>". VEN-04 `VENDOR_SENDER_MISMATCH` is in the routing matrix (24 types). Two mutation probes in `engine/__init__.py` each make the suite report "1 failed, 420 passed": `row["sender_vendor_id"]` and `invoice_id[4:13]`. The ID-blind sandbox is planned for Stage 3 (architecture §5, traceability) |
| S1-R1-02 MINOR | **verified** | The master columns are now `snapshot_status` (vendor, PO, GRN) and `snapshot_received_qty` / `snapshot_open_qty` (PO line), all with `reporting_only=True`. No master `*_as_of` column remains. A probe using `vendor["snapshot_status"]` in engine code makes the suite report "1 failed, 420 passed". The time-travel sandbox is planned for Stage 4 |
| S1-R1-03 MINOR | **verified** | `plan` G2 has `CAPTURE_REVIEW 10 (0.5%) / 1`, and G6 has `CAP-DEGRADED-SCAN`. `ground_truth.is_anomaly` is derived as "intended_issue_types is not empty". `test_clean_means_no_issue_and_the_approval_path` is present and passes |
| S1-R1-04 MINOR | **verified** | `policy` prints `as-of 2026-10-22: valid`. Architecture §7 says POs are issued from 5 January, invoices arrive until 21 October, and "No completed event lies after the as-of date". `git grep` finds no `2026-12-31`, `24 Dec` or `2027` in docs, code, config or README. The Stage-2 test is planned (data_generation §9) |
| S1-R1-05 MINOR | **verified** | Archetype A12 "single delivery billed on two invoices": 10 POs / 10 GRNs / 20 invoices at full scale (starter 1 / 1 / 2), with `C-PARTIAL-BILLING` on placement S12. Full identities by hand: POs 915+295+50+45+10+80+45+60 = 1,500; GRNs 915+590+150+90+10+45 = 1,800; invoices 915+590+150+45+20+80 = 1,800. The checker capacity S12 = 2 × A12 is OK. `test_many_to_many_bridge_is_exercised_in_both_directions` is present |
| S1-R1-06 MINOR | **verified** | `rev_s1_check.py` reports "[spec] every field has all checked attributes" across 29 tables and 336 fields. `test_every_non_text_field_has_a_rule_and_every_numeric_field_a_unit` is present |
| S1-R1-07 MINOR | **verified** | `schema_render.py` no longer slices labels. The only regex hit in schema.md is the full trigger text "the business requester who confirmed the receipt posts the GRN" (line 297), not a truncation |
| S1-R1-08 MINOR | **verified** | requirements_traceability.md now cites A-03, A-10, A-26, A-31, A-32, A-35, A-36, A-39, A-50, A-54, A-60, A-61, A-64, A-65, A-66, A-67, A-68, A-72, A-74, A-80, A-81 and A-82. That covers every item in ACCEPTANCE_CHECKLIST §C.2 |
| S1-R1-09 NIT | open (deferred) | A candidate decision at the Stage-6 hand-off; listed in the A-81 traceability row |

## Regression check
- **Volumes and mix after the CAPTURE_REVIEW and A12 changes:** exact at both scales. REV's checker covers:
  - G1;
  - G2 = G6 summed by category;
  - G3;
  - G4 row arithmetic and identities;
  - the G5 histogram;
  - placement capacities, including S12;
  - G7 = sum of its sub-scenarios;
  - every sub-scenario ≥ 1.

  EC full [35, 15, 20, 550, 15, 30, 50, 65], starter [3, 1, 2, 55, 1, 3, 5, 7].
- **Time model:** consistent across architecture §7, data_generation (dates 2026-01-05 to 2026-10-22, intake until
  2026-10-21) and the policy. Only forward-dated plans may follow the as-of date: due, SLA and scheduled dates.
- **Tests:** 408 → 421. Every old test still passes; the 7 new tests listed in the response exist.
- **Docs and spec:** regenerated with no diff; `docs --check` exits 0.

## New findings
None.

## Carry-forward for Stage 2 (the REV Stage-2 review will test these)
1. **Exact boundary construction.** PO prices for C-PRICE-AT-TOL must make +2.00% an exact cent, and the one-cent
   inside/outside cases must be exact. The same applies to C-QTY-AT-TOL and QM-BOUNDARY-OUT.
2. **No unintended duplicate pairs.** The oracle must assert that no unintended DUP-01, DUP-02 or DUP-03 pair exists.
   Check specifically the two invoices of each A12 PO (C-PARTIAL-BILLING), the C-TN-SAME-DAY pairs and
   C-NPO-RECURRING. Their date, gross or PO must differ so that DUP-03 cannot fire (ADR-009 trade-off).
3. **Vendor closures and blocks** must come after the vendor's other activity (ADR-025).
4. **The as-of date is a hard limit.** No completed event may fall after 2026-10-22, and a test must enforce it.
5. **Stage 2/5:** GRN over-receipts beyond tolerance (`QM-EXCEEDS-PO-*`) must be reported as labelled, not as
   violations.
6. **Stage 4 data check:** at least one GRN line allocated to at least two invoice lines (A-26).
7. **REV's Stage-2 method.** REV-IC runs on the generated CSVs at both scales and covers:
   - counts, ID regexes and embeddings, FK orphan sets;
   - Decimal recomputation of totals and tax;
   - the mix from ground truth;
   - edge-case conditions vs labels, by set equality;
   - date order and state-machine replay;
   - distribution statistics;
   - determinism: two builds compared by SHA-256, with PYTHONHASHSEED=1 vs 2.
8. **Earlier carry-forwards** (Stages 3–6) remain as listed in `stage-1-review-1.md` and DEV_LOG.
