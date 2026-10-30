# Stage 4 review, round 1 (REV): decision engine and evaluation

- **Commits reviewed:** `d105b00` and `ad005fb`, in a fresh clone at `reviews/scratch/s4/clone`. The repo itself was
  not touched.
- **Builds:** REV ran generate, run and evaluate at both scales, twice, into `reviews/scratch/s4/b1` and `b2`.
- **Independent checker:** `reviews/scratch/rev_s4_check.py`. It uses only the standard library and reads the policy
  TOML plus the processed, master and inbox CSVs. It never imports repo code.

**Verdict: PASS-WITH-NITS.** Stage 5 may start.

## Summary
1. **Tests and determinism:** 521 tests pass. All 2,316 files, including processed output and reports, are
   byte-identical across PYTHONHASHSEED=1 and =2.
2. **REV's independent recomputation agrees completely at both scales (0 problems):**
   - Engine vs ground truth, joined on doc_id: invoice ID, issue set, primary issue, match status, final status,
     payment-ready and duplicate_of. Full 2,000/2,000 on every item; starter 200/200.
   - Policy applied correctly. Every exception's role, queue, severity, blocking flag and SLA due date (in business
     days) matches `routing.types`, and every assignee holds that role.
   - Every approval band and level list is recomputed from the captured gross and the PO path, and the levels are
     sequential. Approver roles and turnaround days match `approval.levels`.
   - All 1,348 payments recomputed: due date = invoice date + PO (or vendor) terms; scheduled date = due date moved to
     the previous business day, but not earlier than the next business day after ready; RTGS from 2 lakh;
     amount = captured gross; PAID if and only if scheduled ≤ as-of.
3. **R34e holds:** no payment exists for a blocked invoice, a partly approved invoice, or a vendor not payable on the
   ready date. No approval exists on an invoice with an open blocking exception.
4. **Event log:** 16,215 events across 5,590 chains replayed against REV's own state machines from `schema.md`:
   continuous from/to statuses, time-ordered, only allowed transitions, nothing after 2026-10-22. Every `status_as_of`
   equals its last event, for invoices, exceptions, approvals and payments.
5. **Bridge (A-26):** 16 GRN lines serve 2 or more invoice lines, and 64 invoice lines span 2 or more GRN lines. No
   GRN line is over-allocated, and no allocation uses a GRN posted after the invoice's intake.
6. **The agreement is not circular.** REV ran two mutation probes on a scratch copy:
   - Engine-side policy only, over-receipt tolerance changed from 5% to 6% on the starter data: issue types 199/200,
     acceptance fails 1, `evaluate` exits 1.
   - Engine code only, leading-zero stripping removed from DUP normalisation in `capture.py:23`: issue types 198/200,
     acceptance fails 2, `evaluate` exits 1.
7. **The five actors all hold work:** the four exception roles (requester 485, analyst 170, process owner 70, system
   administrator 20), plus APPROVER on the approval levels.
8. **One NIT:** the generated `reports/evaluation.md` prints raw Python dicts and has no metric definitions.

## Stage-4 checklist

| Item | Status | REV evidence |
|---|---|---|
| A-01 end to end (generate → run → evaluate) | met | Exit 0 at both scales; every invoice has one final status and a trace |
| A-04 three-way match | met | match_result recompute: 0 disagreements on price status, OK quantity and EXCEEDS_PO; match status agrees 2,000/2,000 |
| A-05 routing | met | TOML routing matrix and SLA business days verified for all 745 exceptions |
| A-06 / A-20 / A-59 payment readiness and safety | met | All payments recomputed; 0 unsafe; approvals only on eligible invoices |
| A-07 / A-08 explain and traceability | met | `explain` and decision_trace present (DEV tests). Payment → approval → captured invoice → doc → manifest joins all resolve in REV's checker |
| A-09 metrics | met (NIT) | P/R/F1, confusion, duplicate pairs, STP, value at risk. Definitions are in `evaluation_plan.md` E10 and ADR-041 but missing from `evaluation.md` (S4-R1-01) |
| A-10 non-circular | met | Two independent mutation probes are detected |
| A-12 actors | met | See Summary item 7 |
| A-21 engine events | met | Replay clean; `status_as_of` = last event |
| A-26 bridge both directions | met | 16 / 64, no over-allocation, no future GRN |
| A-40..A-48 detection | met | Issue sets equal ground truth on 2,000/2,000; duplicate pairs 100/100; true negatives 0 FP (DEV test) |
| A-56..A-58 / A-60 per invoice | met | `acceptance_per_invoice.csv`: 2,000 pass; REV agreement as above |
| A-63 / A-67 time semantics | met | No event after as-of; no future GRN in allocations; DEV's time-travel test |
| Ruling 2 (VEN-04 precedence) and ruling 3 (GST12) | met | DEV tests present and passing (`test_decisions.py`) |
| Absent types (Q2 ruling) | met | 8 fixtures through the engine; reported as "not present" |

## Findings

### S4-R1-01 · NIT · A-09, A-76 (R4, clarity): `evaluation.md` has no definitions and prints raw dicts
- **Finding:** the KPI section prints `stp_rate`, `exception_rate`, `open_by_role` and the like as Python dict
  literals, with no definitions. The definitions exist only in `docs/evaluation_plan.md` E10 and ADR-041. This is the
  file evaluators will open first.
- **Fix (in the Stage-5 commit):**
  - Add a one-line definition per KPI, or a "Definitions" section that links to E10.
  - Render the dicts as small tables.
  - State the snapshot caveat for overdue counts (see ruling 2).
- **Acceptance test:** `evaluation.md` contains no `{'` text, and every KPI name has a definition.

## Rulings on DEV's open points
1. **Budget: accepted.** About 23.5 MB for both scales, achieved by leaving out the full-scale JSON exports and the
   full `decision_trace.jsonl`. Stage 5 must:
   - measure the actual committed size;
   - record SHA-256 values for the omitted, regenerable files;
   - say in the README which full-scale files are regenerated by `build-all`;
   - prove parity: committed data equals a fresh build (A-54).
2. **Overdue backlog: keep the SLA dates and intake timing as they are.** Inventing resolutions would bring back
   random-looking human decisions (ADR-011). Present the backlog honestly instead:
   - in `evaluation.md` and the dashboard, call it "open and past SLA at the snapshot (no resolutions simulated)";
   - add an age-in-business-days split, e.g. ≤ 5, 6–20, > 20;
   - list it in the README limitations.

## Carry-forward
- **Stage 5:**
  - S4-R1-01 and ruling 2 presentation;
  - budget and parity (ruling 1);
  - full validation suite over every table, including the FK set from the spec and the polymorphic event references;
  - SQL seed with PK/FK/CHECK, loaded with `PRAGMA foreign_keys=ON` and a clean `foreign_key_check`;
    `evaluation_seed.sql` kept separate;
  - `build-all`, `repro` (two builds plus a second seed), the queue CLI and the dashboard (offline, no CDN).
- **Stage 6:** S1-R1-09; README limitations (business days only, no simulated rejections or resolutions, the 8 absent
  types).

## Regression check
- REV's Stage-2 and Stage-3 properties still hold in this build: the counts, the mix, and 0 silent extraction errors
  (DEV's report agrees).
- The blind-run and time-travel properties are covered by DEV's tests, which pass.
- No regression found.
