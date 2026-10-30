# Stage 1 review, round 1 (REV)

Commit reviewed: `12f551a` on `main`. REV reviewed a fresh clone at `reviews/scratch/s1/clone`; the repo itself was not
touched.
Measured against: SPRINT_PLAN §4 Stage-1 DoD, and the ACCEPTANCE_CHECKLIST §E Stage-1 row.

**Verdict: REVISE**

## Summary
1. Stage 1 is strong overall:
   - 8 design docs, a validated and versioned policy, and a 29-table / 336-field machine-readable spec.
   - Generated docs are proven to match the code. Regenerating leaves zero diff, and `docs --check` exits 1 on drift.
   - 408 tests pass on Python 3.11, 3.12 and 3.13.
2. The volume and mix allocation is exact at both scales. REV's own parser (no repo imports) re-derived every
   identity: 300/1,500/2,200/1,800/2,000, the archetypes, the line histogram, placement capacities, and all 40
   sub-scenarios. Every edge case has ≥ 15 invoices at full scale and ≥ 1 at starter.
3. **One MAJOR.** The engine-readable intake manifest gives the engine the true vendor for every document:
   `sender_vendor_id` is required for all channels including SCAN, and the vendor code is embedded in `invoice_id`.
   No data case makes these differ from the printed vendor, so if the engine used this shortcut instead of VEN-01,
   no metric could detect it.
4. Seven MINOR findings and one NIT:
   - year-end `*_as_of` snapshot columns exposed to the engine;
   - degraded-capture invoices labelled CLEAN but expected to be held;
   - as-of date 2026-12-31 lies after the submission date (orchestrator's point, accepted);
   - the N:M bridge is exercised in only one direction;
   - 16 fields lack a validation rule;
   - state-machine labels are truncated mid-word;
   - the traceability matrix lacks REV-added items.
5. Rulings on DEV's questions: Q1 (68% clean) accepted; Q2, the capture overlay gets its own category; Q3, commit the
   full build with conditions; Q4, flat layout accepted. The as-of date moves to a fixed past date (2026-10-22
   recommended).

## Stage-1 checklist

| Item | Status | Evidence |
|---|---|---|
| DoD: every requirement has a planned home | met | `docs/requirements_traceability.md` covers R1–R37 (with sub-items) and G1–G11. REV-added items are missing (S1-R1-08) |
| DoD: volume math feasible and exact | met | `rev_s1_check.py` on `plan --scale full/starter`: all identities OK (see Verification) |
| DoD: mix and edge cases consistent with ~70/10/8/5/4/3, all 8 covered | met | CLEAN 1,360 (68.0%), the five named categories exact, ARITHMETIC 20, INVOICE_BEFORE_PO 20. EC full [35,15,20,550,15,30,50,65], starter [3,1,2,55,1,3,5,7] |
| DoD: IDs follow the conventions | met | `ids.PATTERNS` match the assignment examples and reject malformed variants. Every unspecified ID has a pattern |
| DoD: ambiguities resolved and documented | met | ADR-001..036 cover REV's AMB-01..33. The four open questions are ruled below |
| DoD: design has no leakage path | partial | Static boundary is tested and the mutation probe was caught. Gaps: vendor identity in the inbox (S1-R1-01) and future snapshot columns in master (S1-R1-02) |
| A-05 routing spec | met | business_rules §6, generated from the TOML: 23 types → severity, blocking, role, queue, SLA. Deterministic assignment |
| A-10 engine boundary (design) | partial | `tests/test_boundary.py` fails on an injected `from ..generator import allocation`. Runtime sandbox planned for Stage 3. See S1-R1-01 |
| A-12 five actors | met | business_rules §10; `test_policy::test_all_five_actors_have_work` |
| A-17 non-PO path | met | ADR-008: 100 non-PO originals (5%), NPO placements, requester approval |
| A-19 policy config | met | `config/ap_policy.toml` 1.0.0 validated on load; 9 mutation tests; justified tolerances; rule IDs |
| A-21 events and state machines | met | ADR-018. Machines are generated from `lifecycle.py`; label truncation is S1-R1-07 |
| A-22 oracle design | met | architecture §5, ADR-016: the oracle is asserted equal to intent; the RNG never decides counts or labels |
| A-24 keys | met | schema §4 is generated: 29 tables, 70 FKs |
| A-25 cardinality, optionality, effective dates | met (with MINOR) | schema §5–§7: C1–C23, effective-date table; S1-R1-07 |
| A-26 bridge N:M | partial | `match_allocation` exists, but only one direction is planned (S1-R1-05) |
| A-29 / A-31 / A-32 IDs | met | Patterns verified; `vendor_invoice_number` is separate; resubmissions get a new `invoice_id` |
| A-33 data dictionary | partial | 336 fields, origin and derivation present; 16 fields have no rule beyond type and 3 have no unit (S1-R1-06) |
| A-35 allocation proof | met | DEV's tests plus REV's independent parser, both scales |
| A-36 mix | met | Ruling Q1 accepted; adjusted by S1-R1-03 |
| A-39 / A-40–47 edge-case mapping | met | `catalogue.py`, G6/G7; each EC tagged; boundary trios and true negatives |
| A-48 boundary and true negatives | met (plan) | C-PRICE-AT-TOL / C-PRICE-INSIDE / PV-BOUNDARY-OUT, C-QTY-AT-TOL / QM-BOUNDARY-OUT, C-TAX-ROUNDING, C-NPO-RECURRING, C-TN-SAME-DAY |
| A-49 derived values | met (spec) | Every field has an origin (source / derived / assigned / captured / decided) and a derivation formula |
| A-50 separate GT, label-free inputs | partial | Layers are separate and `test_spec` bans label-like input columns. S1-R1-01, S1-R1-02 |
| A-62 evaluation focus (a)–(g) | met (plan) | `evaluation_plan.md` lines 62–68 |
| A-65 Decimal | met | business_rules §1, ADR-014, `tests/test_ids_and_money.py` |
| A-66 determinism | met (plan) | `test_repo_hygiene` bans the wall clock, global RNG, libm and uuid. The PYTHONHASHSEED probe is carried forward |
| A-67 time semantics | met (spec) | ADR-012/024; `receipt_cutoff = PROCESSING_TIME`. The guard is S1-R1-02 |
| A-70 README stub | met | The quickstart commands ran in a fresh clone |
| A-73 skeleton and commit | met | `.gitattributes` LF, `.gitignore`, MIT LICENSE, pyproject, 1 commit with both trailers |
| A-76 ADRs | met | 36 ADRs with alternatives and trade-offs |
| A-79 hygiene | met | No secrets or PII in tracked files. Author-email NIT S1-R1-09 |
| A-82 traceability (planned) | partial | 0 A-item references (S1-R1-08) |

## Verification (REV-run)
- **Tests:** `python3 -m pytest -p no:cacheprovider` gives `408 passed` on 3.13 (0.34 s), 3.11 (0.50 s) and 3.12
  (0.53 s).
- **Generated docs match the code:** `python3 -m invoice_ap docs` followed by `git status --porcelain` shows no
  changes. Drift probes on the clone (each reverted afterwards):
  - a spec text edit makes `docs --check` report "2 item(s) stale" and exit 1;
  - an SLA edit in the policy makes it report "1 item(s) stale";
  - an injected `from ..generator import allocation` in `engine/__init__.py` makes `test_boundary.py` report
    "1 failed, 3 passed".
- **Allocation:** `python3 -I reviews/scratch/rev_s1_check.py plan_full.md plan_starter.md data_dictionary.json`
  reports `[plan full] ... -> OK` and `[plan starter] ... -> OK`. It checks:
  - G1 totals;
  - G2 = G6 summed by category;
  - G3 population sums;
  - G4 row arithmetic and the PO/GRN/invoice identities;
  - G5 histogram (1–8 lines, 1,500 POs / 2,200 lines);
  - placement capacities (S11 + PAIR11 = A11, split slots, S21 = A21, F = A01);
  - G7 = sum of its sub-scenarios;
  - every sub-scenario ≥ 1.
- **Policy:** `python3 -m invoice_ap policy` prints `AP-POLICY 1.0.0 ... valid, 23 routed exception types, 7 approval
  bands`.

## Findings

### S1-R1-01 · MAJOR · A-10, A-50, A-55 (R30, R34a): the inbox hands the engine the true vendor, and no data case can expose a shortcut
- **Finding:**
  - The engine-readable `intake_manifest` carries `invoice_id`, defined as "vendor code = sender_vendor_id (ADR-003)".
  - It also carries `sender_vendor_id`, a required FK whose rule is "equals the vendor code embedded in invoice_id".
    This holds for every channel, including SCAN ("mailroom batch").
  - VEN-01 says "Vendor identity comes from the document, not from the sender", but nothing enforces it.
  - No sub-scenario makes the indexed vendor differ from the printed vendor; VENDOR_NOT_FOUND is unit-test only
    (ADR-036).
  - So an engine that took the vendor from the manifest would score exactly the same. Vendor resolution, and the
    vendor part of "extracted fields match source", would be unverifiable. That is a leakage path against the
    Stage-1 DoD "design has no leakage path".
- **Evidence:**
  - `invoice_ap/spec/tables_documents.py:16-25`
  - `docs/business_rules.md:30` (VEN-01)
  - `docs/assumptions_and_decisions.md` ADR-003, ADR-036
  - `invoice_ap/generator/catalogue.py`: no sender ≠ printed-vendor scenario
- **Required fix:** pick one path and record it as an ADR.
  - (a) Make intake channel-realistic. Provide `sender_vendor_id` only where the channel authenticates the sender
    (PORTAL, EDI). EMAIL keeps only `sender_address`, which the engine may map through `vendor.remit_email`. SCAN keeps
    a batch id only. The engine treats `invoice_id` as opaque, or assigns it after VEN-01.
  - (b) Keep indexing as-is, but add a blocking rule: "printed TRN vendor ≠ indexed sender vendor", e.g.
    `VENDOR_SENDER_MISMATCH` → OPERATIONS_ANALYST, with a routing row. State that `captured_invoice.vendor_id` comes
    only from VEN-01.
  - Either way, plan two tests for Stage 3, in architecture §5 and the traceability matrix:
    - a static ban on engine code parsing `invoice_id` or reading `sender_vendor_id` for vendor resolution;
    - an ID-blind sandbox run: blank `sender_vendor_id` and mask the vendor code inside `invoice_id` in a temp copy of
      the inbox. Engine decisions must be identical, apart from the ID mapping.
- **Acceptance test:** REV re-reads the `intake_manifest` spec rows, architecture §5, business_rules and the ADR. If
  path (b) is taken, the routing matrix contains the new type and `docs --check` passes. The two tests appear in the
  traceability matrix as Stage-3 evidence.

### S1-R1-02 · MINOR · A-67, A-10 (R30, R35c): year-end snapshot columns are engine-readable
- **Finding:** these master columns are computed at the as-of date, which is in the future for most processing times:
  - `vendor.status_as_of`
  - `purchase_order.status_as_of`
  - `purchase_order_line.received_qty_as_of` and `open_qty_as_of`
  - `goods_receipt.status_as_of`

  The rules correctly require effective-dated history and "receipts posted before processing". Nothing stops the
  engine from reading the snapshots, which would mean using future receipts or closures.
- **Evidence:** REV query of `data_dictionary.json` (master layer `*_as_of` fields); ADR-012; ADR-025.
- **Required fix:**
  - Mark these columns "reporting only, never an engine input", in the spec (a flag or rule text) and in
    architecture §5. Or move them out of `master/`.
  - Plan a static test: engine code never references a master `*_as_of` column.
  - Plan a Stage-4 time-travel sandbox: drop master rows and events dated after an invoice's processing time. That
    invoice's decision must be unchanged.
- **Acceptance test:** spec and docs updated; `docs --check` passes; both tests are listed in the traceability matrix
  (Stage 3–4).

### S1-R1-03 · MINOR · A-36, AMB-05 (R24): degraded-capture invoices are labelled CLEAN but expected to be held (ruling on Q2)
- **Finding:**
  - `C-CAPTURE-DEGRADED` (10 full / 1 starter) has category CLEAN, but intends `EXT_LOW_CONFIDENCE` with decision
    HOLD.
  - Ground truth derives `is_anomaly = scenario_category != CLEAN`, so these invoices get `is_anomaly = false` while
    `expected_blocked = true`.
  - That contradiction distorts metrics on clean invoices (STP, false-positive rate) and the meaning of "clean
    matches".
- **Evidence:** `invoice_ap/generator/catalogue.py:71-72`; `invoice_ap/spec/tables_documents.py:109-110`; ADR-017.
- **Required fix:**
  - Make it its own category, e.g. `CAPTURE_REVIEW`, carved from CLEAN the same way as ARITHMETIC and
    INVOICE_BEFORE_PO. CLEAN then becomes 1,350 (67.5%) at full scale and 135 at starter; both are still within
    A-36's floor.
  - Define `is_anomaly` as "intended issues non-empty".
  - Add an invariant test: every CLEAN sub-scenario has no intended issues and decision APPROVAL_PATH.
- **Acceptance test:** `plan` shows the new row in G2 and G6; `rev_s1_check.py` passes; ADR-017 is updated; the
  invariant test exists and passes.

### S1-R1-04 · MINOR · A-63, AMB-03 (R35c): the as-of date lies after the submission date (orchestrator point, accepted on the merits)
- **Finding:**
  - `as_of_date = "2026-12-31"` and invoices "arrive until 24 December".
  - The committed dataset would therefore record received invoices, posted receipts, decided approvals and PAID
    payments dated after the October 2026 submission.
  - This breaks no explicit rule, but an evaluator will see completed events in the future of the artefact
    timestamps. A fixed past snapshot is cleaner, and it is free to change now and costly after Stage 2.
- **Evidence:** `config/ap_policy.toml:18`; `docs/architecture.md:151-157`; ADR-011; `docs/data_generation.md:33`.
- **Required fix:**
  - Set `as_of_date` to a fixed past date on or before the start of the submission window: 2026-10-22, which matches
    the seed, is recommended. Any fixed date ≤ 2026-10-28 is acceptable.
  - End the data window there. Every completed event must be ≤ as-of: GRN posted, invoice received, approval
    decided, payment PAID, vendor status change.
  - Forward-dated plans may fall after as-of and stay SCHEDULED or PENDING: due dates, SLA due dates, scheduled
    payment dates.
  - Keep it a config constant, never read from the clock.
  - Update the time model, ADR-011 and the holiday list as needed, and plan the Stage-2 test "no completed-event
    timestamp > as_of_date".
- **Acceptance test:** `python -m invoice_ap policy` prints the new as-of; docs are updated and `docs --check` passes;
  allocation proofs still pass.

### S1-R1-05 · MINOR · A-26 (R15): N:M is claimed in both directions, but only one is planned
- **Finding:** schema.md says a receipt line "can be consumed by several invoice lines when a vendor bills one delivery
  in parts". No archetype or placement produces that: G4 has only A11, A22, A33, A21, A01, A10 and A00. Only
  `C-CONSOLIDATED` exercises the other direction (one invoice line → two GRN lines). The bridge's data would then be
  1:N in practice, which a strict evaluator can notice.
- **Evidence:** `docs/schema.md:205-207`; plan Table G4; `catalogue.py` placements.
- **Required fix:**
  - Add a small clean placement, e.g. archetype A12 "one delivery billed on two invoices" (≥ 10 full, ≥ 1 starter),
    and re-solve the identities.
  - Stating "one direction only" would leave A-26 partial at Stage 4.
- **Acceptance test:** G4 and G6 include it; `rev_s1_check.py` passes; Stage 2/4 data has ≥ 1 GRN line allocated to
  ≥ 2 invoice lines.

### S1-R1-06 · MINOR · A-33 (R20): 16 fields have no validation rule, and 3 have no unit
- **Finding:** Step 1 requires a validation rule for every field. 16 of 336 non-text fields have no allowed values,
  format, range, rule or derivation beyond their type. They include 11 date, datetime or decimal fields whose
  ordering rules are exactly what Step 8 checks:
  - `app_user.active_from`, `tax_code.valid_from`
  - `vendor_status_history.recorded_at`
  - `captured_invoice.captured_at`
  - `ap_exception.created_at`
  - `invoice_decision.decided_at`
  - `policy_version.as_of_date` and `effective_from`

  The confidence fields `captured_invoice.min_field_confidence`, `captured_invoice_line.min_field_confidence` and
  `extraction_field.confidence` have no unit.
- **Evidence:** `rev_s1_check.py` output; `docs/data_dictionary.md:93` (`active_from` shows "-" in the rule column).
- **Required fix:**
  - Add the rules, e.g. `captured_at` ≥ manifest `received_at`, `created_at` ≥ `captured_at`,
    `recorded_at` ≥ `effective_date`, `valid_from` < `valid_to`, `as_of_date` ≥ `effective_from`.
  - Give the confidence fields a unit ("score 0–1").
  - Add a spec test: every non-text field has a rule, format, allowed set or derivation, and every numeric field has
    a unit.
- **Acceptance test:** `rev_s1_check.py` reports no "missing" lines.

### S1-R1-07 · MINOR · A-25 (R14, clarity): generated state-machine labels are cut mid-word
- **Finding:** `schema_render.py:30` truncates labels with `[:48]`. In schema.md this produces "who confirm" (line 285),
  "or res" (line 332) and "on or " (line 363), in a diagram evaluators will read.
- **Required fix:** shorten the labels at their source, or wrap them; add a test that no rendered label is cut
  mid-word.
- **Acceptance test:** schema.md labels are complete and `docs --check` passes.

### S1-R1-08 · MINOR · A-82: the traceability matrix omits REV-added items
- **Finding:** `requirements_traceability.md` has 0 A-item references. DEV had not seen the checklist, so this is new
  scope.
- **Required fix:** add a "REV-added" section covering every A-item in ACCEPTANCE_CHECKLIST §C.2 (location, planned
  evidence, stage). At minimum include: A-10 blind run, A-50 sandbox tests, A-54 PYTHONHASHSEED and committed-data
  parity, A-60 per-invoice report, A-67 time semantics, A-80 timeline, A-81 hand-off.
- **Acceptance test:** grep finds each listed A-id in the matrix.

### S1-R1-09 · NIT · A-79, A-81: commit author e-mail (no DEV action now)
- **Finding:** commits are authored with the candidate's personal Gmail. This becomes public when pushed.
- **Fix:** Stage-6 hand-off item. The candidate decides whether to keep it or switch to a GitHub noreply address
  before pushing.

## Rulings on the open questions
1. **Q1, CLEAN at 68.0% (ADR-005): accepted.** The five named categories are exact, the carve-outs are their own
   reported rows, and clean stays within "~70%" (≥ 1,340 per A-36). Folding into families is not required. With
   S1-R1-03, CLEAN becomes 1,350 (67.5%), which is also accepted.
2. **Q2, degraded-capture overlay: its own labelled category,** not CLEAN. See S1-R1-03.
3. **Q3, size: committing the full build is accepted, under these conditions:**
   - Commit the full CSV layers, inbox documents, reports and manifest.
   - Commit JSON and SQL exports for the starter build.
   - Commit the full-scale JSON and SQL only if the total committed data stays at or below about 25 MB, as measured.
     Otherwise record their checksums in the manifest and regenerate them with `build-all`.
   - Commit generated data only when Stages 5 and 6 close, not in every fix round, so history stays small.
   - A check must prove the committed data equals a fresh build (A-54).
4. **Q4, flat layout (ADR-001): accepted.** `python -m invoice_ap` works with no install step, and the boundary is
   enforced by tests. REV's mutation probe confirmed it.
5. **Orchestrator, as-of date: accepted.** Move it to a fixed past date (2026-10-22 recommended). See S1-R1-04.

## Carry-forward (tracked; not findings yet)
- **Stage 2:**
  - Construct exact boundaries: C-PRICE-AT-TOL needs PO prices where +2.00% is an exact cent. REV will check the
    variance is exactly 2.00% and that the one-cent cases are exact.
  - The oracle must assert that no unintended DUP-03 pair exists (the ADR-009 trade-off).
  - Closures must come after the vendor's other activity (ADR-025).
  - No completed event may fall after as-of (S1-R1-04).
- **Stage 2/5:** GRN over-receipts beyond tolerance (`QM-EXCEEDS-PO-*`) must be reported as labelled, not as
  violations.
- **Stage 3:** runtime no-leakage sandbox plus the ID-blind test (S1-R1-01); negative and mutation tests for extraction
  (A-03).
- **Stage 4:**
  - time-travel sandbox (S1-R1-02);
  - per-type metrics for the "not present" types in ADR-036, with no division by zero;
  - the limitation "approver rejection not simulated" (ADR-011) stated in the README (A-78).
- **Stage 5:**
  - Keep ground truth and source out of the main SQL seed's input tables. architecture.md:46 routes SRC and GT into
    "exports: CSV / JSON / SQL seed", so specify a separate file or schema (A-50, P-4).
  - PYTHONHASHSEED probe, committed data equals a fresh build, and size measured against the Q3 ruling (A-54).
- **Stage 6:** S1-R1-09; the candidate confirms the MIT licence; the `[CANDIDATE TO COMPLETE]` placeholder stays.

## Regression check
Not applicable (round 1).
