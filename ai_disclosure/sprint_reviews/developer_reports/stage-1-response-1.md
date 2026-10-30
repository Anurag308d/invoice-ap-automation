# Stage 1, response to review 1

Commit: `66b1f07` on `main` ("stage-1 fix-1: vendor identity from documents only, CAPTURE_REVIEW, A12,
as-of 2026-10-22"), both trailers present. Also passes on Python 3.11 (421 passed).

Verification after all fixes:

```text
$ python3 -m pytest                      -> 421 passed in 0.52s   (was 408)
$ python3 -m invoice_ap docs --check     -> docs up to date
$ python3 -m invoice_ap policy           -> AP-POLICY 1.0.0 (sha256 ece9400b...) as-of 2026-10-22: valid
                                            24 routed exception types, 7 approval bands
$ python3 -I reviews/scratch/rev_s1_check.py plan_full.md plan_starter.md data_dictionary.json   (REV's checker, run read-only)
[plan full] totals=... clean=1350 subs=41 EC=[35, 15, 20, 550, 15, 30, 50, 65] -> OK
[plan starter] totals=... clean=135 subs=41 EC=[3, 1, 2, 55, 1, 3, 5, 7] -> OK
[spec] every field has all checked attributes
$ python3 -I <scratchpad>/check_allocation_tables.py docs/data_generation.md   (DEV's independent parser)
ALL CHECKS PASSED   (both scales: categories, archetype POs/GRNs/invoices, populations, histogram, sub-scenarios, EC >= 1)
```

## Finding -> change -> evidence

| ID | Change | Evidence |
|---|---|---|
| **S1-R1-01** MAJOR | **Both paths taken (ADR-037).** See the paths (a) and (b) and the tests below. | `tests/test_spec.py::test_intake_manifest_never_hands_the_engine_a_vendor` and `test_boundary.py::test_engine_never_takes_the_vendor_from_the_sender_or_an_id` pass; `test_policy.py::test_vendor_identity_rules` passes; routing matrix row 6 = `VENDOR_SENDER_MISMATCH \| VEN-04 \| HIGH \| yes \| OPERATIONS_ANALYST \| AP_VALIDATION \| 2`; traceability R30 and A-10 / A-50 rows list both Stage-3 tests |
| S1-R1-02 MINOR | Master snapshots renamed `snapshot_status` (vendor, PO, GRN) and `snapshot_received_qty` / `snapshot_open_qty` (PO line), and flagged `reporting_only=True`. The dictionary row says "**Reporting only, never an engine input.**" Recorded in ADR-038 and architecture §5. A test ties the flag to the `snapshot_` prefix, so the active static ban on `snapshot_` in engine code covers every such column. The Stage-4 **time-travel sandbox** is planned: drop rows and events after processing time, blank snapshots, decision unchanged | `test_spec.py::test_snapshot_columns_are_reporting_only_and_named_for_the_static_ban` passes; traceability R30 and A-67 rows |
| S1-R1-03 MINOR | New category **CAPTURE_REVIEW** (sub-scenario `CAP-DEGRADED-SCAN`, 10 full / 1 starter). CLEAN is now 1,350 (67.5%) / 135. `is_anomaly` = "intended_issue_types is not empty". Invariant test: every CLEAN sub-scenario has no intended issue and decision APPROVAL_PATH, and every other sub-scenario has issues and HOLD/REJECT. ADR-005 and ADR-017 updated | `plan` G2 row `CAPTURE_REVIEW \| (degraded scans) \| 10 \| 0.5% \| 1 \| 0.5%`, G6 row `CAP-DEGRADED-SCAN`; `test_allocation.py::test_clean_means_no_issue_and_the_approval_path` passes; REV checker OK |
| S1-R1-04 MINOR | `as_of_date = "2026-10-22"` (a Thursday; a config constant, never the clock). The data window ends there: intake closes 2026-10-21, and late POs are open or received-not-invoiced. Only due, SLA and scheduled dates may come later. Updated: time model (architecture §7), ADR-011, ADR-004 (all dates now in 2026), schema §7, data_generation §2/§5/§9. The Stage-2 test "no completed-event timestamp > as_of_date" is planned in data_generation §9. The holiday list is kept (2026-12-25 stays for forward dates) | `policy` prints `as-of 2026-10-22: valid`; `test_policy.py` asserts the date; allocation proofs pass |
| S1-R1-05 MINOR | New archetype **A12** "single delivery billed on two invoices" (1 GRN line -> 2 invoice lines): `n12 = max(1, round_half_up(POs/150))` = 10 full / 1 starter, sub-scenario `C-PARTIAL-BILLING` (20 / 2 invoices). Identities re-solved: full A11 915, A22 295, A33 50, A21 45, A12 10, A01 80, A10 45, A00 60; C-STD rebalanced to 310 so full-scale counts stay exact. Schema C11 text and ADR-022 updated | G4 total row `1500 \| 1800 \| 1800` (full) and `150 \| 180 \| 180` (starter); `test_allocation.py::test_many_to_many_bridge_is_exercised_in_both_directions`; REV checker OK. The Stage-2/4 data check for >= 1 GRN line on >= 2 invoice lines is in the traceability A-26 row |
| S1-R1-06 MINOR | Rules added to all 16 fields, for example: `captured_at >= received_at`, `created_at`/`decided_at >= captured_at` and `<= as_of_date`, `recorded_at <= effective_date` (no back-dating), `valid_from < valid_to`, `as_of_date >= effective_from`; rule-ID list patterns for `rule_ids`/`oracle_rule_ids`; allowed key set for `matched_keys`. Confidence fields carry unit "score 0-1", integers "count" or "ordinal", booleans an explicit true/false set. New test enforces a rule on every non-text field and a unit on every numeric field | `test_spec.py::test_every_non_text_field_has_a_rule_and_every_numeric_field_a_unit` passes; REV checker: "every field has all checked attributes" |
| S1-R1-07 MINOR | `lifecycle.py` now stores `Transition(label, detail, simulated)` with explicit short labels; the renderer has no truncation. Tables show label, full trigger and "produced by the simulation" | `tests/test_lifecycle.py` (labels <= 32 chars, no `:;()`, each rendered in full in schema.md) passes; probe for the old fragments ("who confirm", "or res", "on or ") finds 0; longest label 25 chars |
| S1-R1-08 MINOR | New section "REV-added acceptance items (ACCEPTANCE_CHECKLIST §C.2)" covering A-10, A-50, A-67, A-54, A-60, A-36/A-39, A-26, A-61, A-03/A-72, A-64, A-74, A-80, A-81, A-82, A-31/A-32, A-35, A-65/A-66/A-68, each with location, planned evidence, stage and status | `grep` finds A-10, A-50, A-54, A-60, A-67, A-80 and A-81; 17 A-item rows |
| S1-R1-09 NIT | No action, per the orchestrator. It is listed for the candidate in the A-81 hand-off row | traceability A-81 row |

S1-R1-01 detail:
- **(a) Channel-realistic intake.**
  - `intake_manifest` no longer has `invoice_id`. It has `intake_seq`.
  - `sender_vendor_id` is optional, required only when the channel is PORTAL or EDI. It is empty
    for EMAIL and SCAN.
  - `sender_address` is a forwarding mailbox for about 15% of EMAIL documents, and a mailroom batch
    ID for SCAN.
  - New rule **ID-01**: the engine assigns `invoice_id = INV-<VEN-01 vendor or VND-00000>-2026-<intake_seq>`
    after vendor resolution. `captured_invoice.invoice_id` has origin `decided`.
  - VEN-01 is the only source of `captured_invoice.vendor_id`.
- **(b) New rule VEN-04 `VENDOR_SENDER_MISMATCH`.** The authenticated sender must equal the VEN-01
  vendor. It is blocking, routes to OPERATIONS_ANALYST / AP_VALIDATION with SLA 2, and has a routing
  row and a precedence slot right after VENDOR_NOT_FOUND. It is unit-test-only data-wise (ADR-036).
- **Tests.**
  - The static ban is active now: engine code may not read sender fields outside
    `engine/vendor_identity.py`, call `vendor_of_invoice`, or slice an `invoice_id`.
  - The **ID-blind sandbox** `tests/test_engine_sandbox.py::test_id_blind_run` is planned for
    Stage 3 in architecture §5 and the traceability matrix. It blanks `sender_vendor_id` and
    `sender_address` and requires identical decisions.
- **Docs.** Schema §1 / C17 now join source and captured invoices on `doc_id`, and invoice-ID
  agreement is a measured vendor-resolution outcome (evaluation_plan R34a and E1).
- **Plan wording.** The plan's "manifest records invoice id" is a recorded deviation (ADR-003).

## Rulings applied consistently

- **Q1 (68% clean): accepted.** CLEAN is now 1,350 (67.5%) because of Q2, above REV's floor of
  1,340. This is asserted in `test_full_scale_mix_is_exact`.
- **Q2: CAPTURE_REVIEW category** (S1-R1-03).
- **Q3: conditions recorded** in ADR-028 and architecture §9:
  - committed data at or below about 25 MB;
  - starter JSON/SQL always committed, full-scale JSON/SQL only within budget;
  - data committed only when Stages 5 and 6 close;
  - a parity check against a fresh build.
- **Q4: flat layout accepted** (ADR-001).
- **As-of date** moved to 2026-10-22 (S1-R1-04).

## Also changed (spec-level needs of the carry-forward)

- Exports split: `exports/sql/evaluation_seed.sql` and `exports/json/evaluation/` hold source and
  ground truth, separate from the operational seed (architecture §1 diagram, §3, §5; A-50 / P-4).
- The PYTHONHASHSEED 1-vs-2 probe is stated in architecture §6 and data_generation §9.
- Scenario spread across the timeline (A-61) is stated in data_generation §9.
- Every carry-forward item is recorded under its stage in `/home/claude/sprint/DEV_LOG.md`.

## Disagreements

None. One note: policy version stays `1.0.0`, because no data has yet been built with any policy
version. 1.0.0 is the first version that will produce data.
