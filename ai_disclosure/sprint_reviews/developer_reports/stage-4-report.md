# Stage 4 report: decision engine and evaluation

Commits on `main`, both with the trailers:
- `d105b00` "stage-4: decision engine, event log, explain and evaluation against ground truth";
- `ad005fb` "stage-4: value at risk counts tax differences".

No generated data is committed.

## 1. What was built

| Module | Role |
|---|---|
| `engine/master.py` | Master data as of a moment (details below). Snapshot columns are never read |
| `engine/validate.py` | The gates, the collected checks and the receipt bridge (details below) |
| `engine/decide.py` | PRI-01 outcome, RTE-01 exceptions for the five actors with SLA and overdue flag, APR-01/APR-SIM-01 approvals, PAY-01..06 payments, and the append-only `ap_event` log for INVOICE, EXCEPTION, APPROVAL and PAYMENT |
| `engine/pipeline.py` | Intake order: capture -> CAP-01 / VEN-01 gates -> DUP gates -> VEN-04 -> checks -> decision. Writes 12 processed tables, including `policy_version`, plus `decision_trace.jsonl` |
| `engine/explain.py` and CLI `explain <invoice_id>` | Rebuilds one invoice from `processed/` only: capture, status, rules, exceptions (expected / actual / variance / tolerance, role, user, queue, SLA), line match, bridge rows, approvals, payment, events and trace |
| `evaluation/decisions.py` and CLI `evaluate` | Metrics against ground truth (details below). Outputs `reports/evaluation.{json,md}` and `reports/acceptance_per_invoice.csv` (A-60). `evaluate` exits 1 on any acceptance failure or unsafe payment |
| `quality/quick.py` | The validator now also checks `ap_event`, and checks completed engine timestamps against the as-of date (details below) |

`engine/master.py` resolves each lookup as of the moment of the decision:
- a vendor status counts only if it is effective on the day asked and was recorded by that moment;
- a receipt counts only if it was posted by the intake time;
- a PO counts only if it was dated by the processing day.

`engine/validate.py` applies, in order:
- the DUP-01..03 gates, pairing each duplicate with the earliest original;
- VEN-02/03, PO-01/02, DATE-01/02, ARI-01/02 and TAX-01/03;
- per line: PO-03, TAX-02 and MAT-01..04, using cumulative prior-invoiced quantity and receipts up
  to processing time;
- the FIFO N:M receipt bridge (A-26).

`evaluation/decisions.py` reports:
- per-type precision / recall / F1 at invoice and line level;
- primary-issue and final-status confusion;
- line status agreement;
- duplicate pair accuracy by type, and false positives on true negatives;
- approvals, payment safety, STP, exception rate, open and overdue counts by role and queue, cycle
  days, and value at risk;
- the per-invoice acceptance check R34a-e.

`quality/quick.py` additions:
- `ap_event` state machines, sequence and time order;
- `status_as_of` equal to the last event for decisions, exceptions, approvals and payments;
- completed engine timestamps must not fall after the as-of date.

ADR-041 records the mechanics: processing-time semantics, the gate order, the bridge, the approval
and payment clock, assignment, and the metric definitions. The oracle was aligned on two
details that leave the data unchanged:
- an unmatched line gives NOT_EVALUATED;
- the variance display rounds ROUND_HALF_UP.

## 2. Evidence (full scale unless stated; reproduced by `generate`, `run`, `evaluate`)

```text
engine: 2000 documents in 1.65-1.80s; capture review 10, vendor not found 0, exceptions 745
decisions: issue types 2000/2000 (100.00%), primary 2000/2000, final status 2000/2000, duplicate pairs 100/100, unsafe payments 0, STP 46.05%
acceptance (R34a-e): pass 2000/2000, fail 0 (capture review flagged 10)
starter: 200/200 on every item; acceptance 200/200
```

- **Agreement with ground truth:** 2,000/2,000 on each of 15 invoice items:
  - invoice ID, issue-type set, primary issue, blocked flag, match status;
  - duplicate pair, assigned roles, queues;
  - approval band and levels;
  - final status, payment ready, payment status, due date, scheduled date.

  At line level, 2,960/2,960 agree on price, quantity and tax status, received quantity and prior
  invoiced quantity.
- **Per type:** every one of the 16 types present has TP = support, FP = 0 and FN = 0 at invoice
  and line level; the primary-issue confusion is purely diagonal. The 8 absent types report
  "not present", never 0/0: VENDOR_NOT_FOUND, VENDOR_SENDER_MISMATCH, PO_NOT_FOUND,
  INVOICE_DATE_IN_FUTURE, TAX_CODE_INVALID, PO_LINE_UNMATCHED, VENDOR_NOT_PAYABLE and
  PAYMENT_DUE_DATE_PASSED.
- **Duplicates:** 100 detected, 100 expected, 100 correct. By type: EXACT 25, NORMALIZED 20,
  EXACT-NPO 5, NUMBER-REUSE 35, CONTENT 15. True negatives produced 0 false positives (recurring
  series, same-day different PO, A12 partial billing).
- **Approvals:** 1,350 eligible invoices, all agreeing on band and levels: P1 921, P2 283, P3 49,
  P4 2, N1 5, N2 86, N3 4. 2 approvals are pending at the as-of date, and 0 approvals exist for
  blocked invoices.
- **Payments:** 1,348 records (1,192 PAID, 156 SCHEDULED, 361 RTGS) and **0 blocked or unapproved
  invoices with a payment** (R34e).
- **KPIs:**
  - STP 46.05% and exception rate 32.50%;
  - capture-to-ready cycle: median 0 days, p90 4 days;
  - open exceptions by role: requester 485, analyst 120, process owner 70, system administrator 20.
    Nearly all are overdue at the as-of date, because the snapshot simulates no resolution
    (ADR-011).
- **Value at risk held:** INR 7,54,12,564.65, with 0.00 released in error. The largest holds are
  missing receipts (2.27 crore), exact duplicates (97 lakh) and quantity over received (86 lakh).
- **Per-invoice acceptance (A-60):** 2,000 pass and 0 fail. R34a passes for 1,990; the other 10
  are degraded scans, flagged for capture review as designed. R34b-e pass for all 2,000. R34b also
  compares ground truth with an independent recomputation from the source. There are no deviations
  to explain.
- **Validator** (`validate --quick --scale full`, including all processed tables and the event
  log): PASS, 0 violations, 187 labelled defects.

Tests: **521 pass** (3.13 in 29.8 s, 3.11 in 30.0 s), and `docs --check` is clean. The 18 new tests
in `tests/test_decisions.py` cover:
- agreement at both scales, the "not present" metrics, and validator plus event-log order;
- A-26: a GRN line split across invoice lines, and an invoice line split across GRN lines, never
  over received and never a future GRN;
- payment safety, and `explain`;
- **fixtures for the 8 absent types** through the engine, each checking type, role, queue, rule and
  blocking flag:
  - 5 by document edits: unknown TRN, missing PO, future invoice date, unknown PO line, and GST12 on
    a 2026 invoice;
  - VENDOR_NOT_PAYABLE: a vendor blocked between the decision and L1 approval gives ON_HOLD with no
    payment;
  - PAYMENT_DUE_DATE_PASSED: zero-day terms give a non-blocking PAYMENT_WATCH warning, paid on the
    next business day after ready;
  - VENDOR_SENDER_MISMATCH: covered by the forged-sender control in the ruling-2 test (and by
    Stage 3's sandbox test);
- **REV ruling 2:** a forged sender on a duplicate gives a DUPLICATE_* primary and no VEN-04, while
  the control invoice raises VENDOR_SENDER_MISMATCH;
- **time travel:**
  - blanked snapshots plus a vendor status change and a GRN after the as-of date leave all 12
    tables byte-identical (full scale);
  - for 25 sampled starter invoices, truncating master to what was recorded by the invoice's intake,
    and the inbox to earlier documents, leaves the processing-time decision unchanged (match
    status, duplicate, exceptions, line match);
- **rule mutation:** a price tolerance of 2.50% makes the engine drop the +2% plus one cent
  invoices, and the evaluation reports PRICE_VARIANCE FN >= 1 and acceptance failures. The
  comparison is therefore not circular.

**Determinism:** generate, run and evaluate under PYTHONHASHSEED 1 and 2 at `d105b00` (with report
titles taken from the dataset scale, not the folder name):

| Scale | Files | Differing | Tree hash |
|---|---|---|---|
| Starter | 258 | 0 | `158751c404c0c492` |
| Full | 2,058 | 0 | `b8550ec69042b117` |

At full scale, `invoice_decision` hashes to `6178ce648333cf71` and `ap_event` to `f82fcee8a0c39478`.
`ad005fb` changes only the value-at-risk arithmetic in `reports/evaluation.*`.

## 3. Rulings and carry-forward closed

- **Ruling 2 (VEN-04 precedence):** enforced, with the test above.
- **Ruling 3 (GST12 -> TAX_CODE_INVALID):** the fixture passes, and the line also gets TAX_MISMATCH.
- **Q2 (absent types):** unit fixtures, "not present" metrics, and the README limitations list.
- **Carry-forward:**
  - the time-travel sandbox;
  - A-26 data check (2 directions);
  - A-60 acceptance report;
  - invoice-ID agreement as a vendor-resolution outcome (2,000/2,000);
  - README: approver rejection is not simulated (A-78).
- **Ruling 1 (budget)** is applied in Stage 5. Measured now, full scale is 32.6 MB in total:

  | Part | MB |
  |---|---|
  | JSON exports | 9.8 |
  | `extraction_field.csv` | 6.5 |
  | `ap_event.csv` | 2.9 |
  | `decision_trace.jsonl` | 2.6 |

  Starter is 3.3 MB. Leaving out the full JSON gives about 26.1 MB for both scales. Dropping the
  full `decision_trace.jsonl` next, as the ruling orders, gives about 23.5 MB, under 25.

## 4. Requirements and A-items

**Done in Stage 4** (`docs/requirements_traceability.md` updated):
- R1 (through `evaluate`/`explain`; `build-all` in Stage 5);
- R2, R3, R4, R5, R9g, R9h;
- R10 (AP events), R30 (time travel), R34a-e;
- A-03/A-72 (rule mutations), A-26, A-60, A-67.

**Stage-4 gate:**
- A-01, A-04..A-12;
- A-20, A-21 (engine), A-23;
- A-26, A-40..A-48 (detection);
- A-56..A-60, A-63, A-67.

## 5. Known gaps

- Exceptions are never resolved within the snapshot, so nearly every open exception is overdue at
  the as-of date. This follows from ADR-011 and is not a defect.
- Engine and oracle share one author (ADR-016). The tolerance-mutation test shows that the
  evaluation detects divergence; it does not prove independent judgement.
- Exceptions raised after approval (PAY-03 and PAY-06) take the next exception IDs when raised, so
  exception IDs are not strictly chronological across invoices (ADR-041).
- Exports, the full validation suite, the dashboard, `build-all`, `repro`, `queue` and the data
  commit with parity are Stage 5. S1-R1-09 remains for the candidate in Stage 6.
