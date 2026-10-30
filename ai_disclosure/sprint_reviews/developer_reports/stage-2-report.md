# Stage 2 report: synthetic data generator and ground truth

Commit: `22c2e6a` on `main` ("stage-2: synthetic generator, rule-based oracle and defect-aware
self-checks"), with both trailers. Generated data is written to the git-ignored `data/<scale>/`
(ruling Q3).

## 1. What was built

| Module | Role |
|---|---|
| `invoice_ap/common/calendar.py` | Business-day arithmetic: weekends plus the policy holidays |
| `invoice_ap/generator/rng.py` | Seeded sub-streams. Integer draws only; log-normal values use Decimal (Irwin-Hall Z, `Decimal.exp`) |
| `invoice_ap/generator/params.py` | Every distribution, window and scenario range in one reviewable file |
| `invoice_ap/generator/world.py` | Actor roles, 28 role-labelled users, SKUs, vendors (exact tiers, segments, categories, terms and channels; Zipf activity weights; ONBOARDED history; 2025 block windows and closures) |
| `invoice_ap/generator/planner.py` | Exact archetypes A11..A00 and A12, every sub-scenario slot, line counts, vendor assignment (dedicated vendors for closed/blocked, SCAN vendors for capture review, repeat-order pairs), per-PO timelines with deterministic redraws, non-PO series and one-offs, scenario parameters, duplicates, injected status events |
| `invoice_ap/generator/tables.py` | Two-phase materialization into exact spec rows. **Baseline**: everything clean. **Final**: adds only the labelled injections. Also numbering schemes (including Indian FY numbers), DUP normalisation, the intake manifest, and ERP events derived from receipts |
| `invoice_ap/generator/oracle.py` | Applies the documented rules to the true data in intake order: CAP-01, VEN-01..04, DUP-01..03, PO-01..03, DATE-01..02, ARI-01..02, TAX-01..03, MAT-01..04, MS-01, PRI-01, RTE-01, APR-01/APR-SIM-01 and PAY-01..06. **Raises `OracleMismatch`** unless blocking labels equal the intent and each duplicate points to its planned original |
| `invoice_ap/generator/writer.py` | CSV in exact spec column order and typed JSON (`exports/json/`, evaluation tables in `exports/json/evaluation/`). Refuses columns that differ from the spec and money that is not a whole cent |
| `invoice_ap/generator/build.py` | plan -> baseline (must validate 0/0) -> final -> oracle -> final validation -> write. `reports/source_manifest.json` holds per-file SHA-256, seed, scale, policy SHA and provenance |
| `invoice_ap/quality/quick.py` | `validate --quick`: defect-aware self-checks. Labelled defects are counted as "labelled", never as violations |
| `invoice_ap/report/distribution.py` | `reports/distribution_summary.{json,md}` (Evaluation Focus (a)) |
| CLI | `generate --scale --seed --out`; `validate --quick --scale/--data` |
| `tests/test_generator.py` | 35 test cases (20 functions, some parametrized), below |

Spec changes in the same commit, with `docs --check` green:
- the list-format wording (canonical order);
- the `expected_issue_types` rule now allows the non-blocking PAYMENT_DUE_DATE_PASSED warning;
- the cumulative-quantity definition (business_rules, ADR-024);
- approval turnarounds 2/2/3/3 business days (ADR-030), so approvals are still in flight at the
  as-of date;
- ADR-039, Stage-2 mechanics: two phases, the timeline redraw, dedicated vendors, duplicates
  inheriting labels, and the intake-manifest stub.

## 2. Requirements and A-items covered

In `docs/requirements_traceability.md`, these rows are now "done (Stage 2)", with test-level
evidence:
- R7, R8, R9a-f, R10 and R16 (ERP-data side), R11, R18, R21-R27, R28a-h, R29;
- the REV-added rows A-36 / A-39 and A-61.

The A-items are the Stage-2 gate map in ACCEPTANCE_CHECKLIST §E:
- A-13 to A-18, A-21 (generator), A-22, A-28 to A-32 and A-34;
- A-36 to A-50 (data side; A-39 with the explicit baseline phase);
- A-61, A-63, A-65, A-66 and A-72 (generator tests).

Also covered:
- P-9, the baseline self-checks;
- the PYTHONHASHSEED part of A-54, done early.

## 3. Evidence

Counts (`python3 -m invoice_ap generate --scale full|starter`):

```text
full: 300 vendors, 1500 POs, 2200 PO lines, 1800 GRNs, 2000 invoices -> data/full in 2.08s
baseline: pass (0 violations); final: pass (0 violations, 187 labelled defects reported as expected); oracle == intent
starter: 30 vendors, 150 POs, 220 PO lines, 180 GRNs, 200 invoices -> data/starter in 0.23s
baseline: pass (0 violations); final: pass (0 violations, 19 labelled defects reported as expected); oracle == intent
```

Derived rows at full scale:

| Table | Rows |
|---|---|
| GRN lines | 2,669 |
| ERP events | 5,050 |
| Vendor status rows | 340 |
| Invoice lines | 2,960 |
| Ground-truth lines | 2,960 |

The full build is 39 files and 18.2 MB.

Mix, from `ground_truth.csv`:

| Category | Full | Starter |
|---|---|---|
| CLEAN | 1,350 | 135 |
| PRICE_VARIANCE | 200 | 20 |
| QTY_MISMATCH | 160 | 16 |
| DUPLICATE | 100 | 10 |
| MISSING_RECEIPT | 80 | 8 |
| TAX_VENDOR | 60 | 6 |
| ARITHMETIC | 20 | 2 |
| INVOICE_BEFORE_PO | 20 | 2 |
| CAPTURE_REVIEW | 10 | 1 |

All 41 sub-scenario counts equal the allocation (`test_mix_matches_the_allocation`).

Edge cases (A-40 to A-47), as invoices tagged with each case:

| Edge case | Full | Starter |
|---|---|---|
| EC-01 Duplicate invoice number | 35 | 3 |
| EC-02 Invoice total differs from line sum | 15 | 1 |
| EC-03 Invoice date before PO date | 20 | 2 |
| EC-04 Partial delivery | 550 | 55 |
| EC-05 Closed vendor | 15 | 1 |
| EC-06 Tax mismatch | 30 | 3 |
| EC-07 Invoice exceeds PO quantity | 50 | 5 |
| EC-08 Same invoice submitted twice | 65 | 7 |

Quick validation (`validate --quick --scale full`) has 10 checks, all passing with 0 violations.

Labelled defects are expected and are not counted as violations:

| Check | Labelled | What they are |
|---|---|---|
| Date order and the as-of limit | 22 | The 20 invoices dated before their PO, plus 2 labelled duplicates of them (one DUP-CONTENT, one DUP-EXACT-NORMALIZED) |
| Arithmetic | 65 | 15 invoice headers (ARITH-HEADER-TOTAL), 5 line amounts (ARITH-LINE-EXTENSION), 15 tax lines (TV-TAX-AMOUNT 10, TV-NPO-TAX-AMOUNT 5), and 30 GRN lines received beyond the 5% tolerance on the labelled over-receipt POs |
| No accidental duplicate pairs | 100 | Every colliding pair is a labelled duplicate and its planned original: DUP-EXACT 25, DUP-NUMBER-REUSE 35, DUP-EXACT-NORMALIZED 20, DUP-CONTENT 15, DUP-EXACT-NPO 5 |

At starter scale there are 19 labelled defects. The baseline phase has 0 violations and 0 labelled
defects at both scales.

Boundary exactness, from the full build CSVs and Decimal arithmetic. `test_boundaries_are_exact`
checks every instance at both scales.

```text
C-PRICE-AT-TOL   PO 1379.00  invoice 1406.58  variance 2.00% exactly
C-PRICE-INSIDE   PO 198.00   invoice 201.95   1.9949%  (PO x 1.02 - 0.01)
PV-BOUNDARY-OUT  PO 157.50   invoice 160.66   2.0063%  (PO x 1.02 + 0.01)
C-QTY-AT-TOL     billed == received == ordered x 1.05
QM-BOUNDARY-OUT  billed == received == ordered x 1.05 + one quantum
```

Determinism: at HEAD `22c2e6a`, both scales were built twice by CLI subprocess, with
PYTHONHASHSEED=1 and =2, into fresh folders. Results:
- the two runs are byte-identical file by file;
- they are also identical to `data/<scale>/`;
- build times were full 2.45 s and 2.51 s, starter 0.20 s and 0.26 s.

```text
starter 39 files; identical per-file sha256: True ; manifest 6160937e5c454a46 True
    master/purchase_order.csv 150 rows c3bb6b146f69c040 | source/invoice.csv 200 rows 72827e4090a33c60
full    39 files; identical per-file sha256: True ; manifest c62b4406026617c1 True
    master/purchase_order.csv 1500 rows b03073053ed32f00 | source/invoice.csv 2000 rows 107603fe40ddd833
```

Also tested: same seed in-process gives identical bytes, and seed 7 gives different data with the
same volumes and mix.

Tests:

```text
$ python3 -m pytest -p no:cacheprovider                           -> 456 passed in 4.84s  (Python 3.13)
$ PYTHONPATH=... /usr/bin/python3.11 -m pytest -p no:cacheprovider -> 456 passed in 5.36s  (Python 3.11)
```

`tests/test_generator.py` covers:
- exact volumes; mix = allocation; ID patterns and embeddings;
- self-checks pass and the baseline is clean; totals recompute; edge cases present; exact
  boundaries;
- no completed event after the as-of date; only labelled duplicates collide; true negatives differ
  where DUP-03 looks (A12, same-day pairs, recurring series);
- closures and blocks follow all other activity; over-receipt beyond tolerance only in labelled
  scenarios;
- oracle = intent, clean = no issue;
- **fails loudly**: a corrupted intent raises OracleMismatch;
- injections do not touch unrelated rows (baseline vs final);
- determinism: same seed, PYTHONHASHSEED independence, another seed;
- the inbox never hands over the vendor;
- one GRN line billed by two invoice lines (A-26, data level).

## 4. Distribution statistics (Evaluation Focus (a); `data/full/reports/distribution_summary.md`)

- **Vendor concentration:** of the 270 goods vendors, 217 have POs. The top 20%:
  - ranked by PO count, carry 77.7% of POs;
  - ranked by spend, carry 88.1% of PO spend.
- **Lines per PO:** 1,090 / 260 / 80 / 35 / 15 / 10 / 5 / 5 (exact).
- **Median PO line net by category (INR):**

  | Category | Median |
  |---|---|
  | CANTEEN | 27,946 |
  | OFFICE | 34,286 |
  | MRO | 42,969 |
  | ELECTRICAL | 75,747 |
  | PACKAGING | 82,046 |
  | SAFETY | 103,511 |
  | RAW | 166,015 |
  | IT_HARDWARE | 198,224 |
- **Median lead days:** canteen 3, office 5, packaging and safety 8, electrical 11, raw 14, MRO 17,
  IT 18.
- **Invoice gross:** p10 13,146, median 91,119, p90 586,182, max 8,447,172. All approval bands
  occur at full scale: P1 921, P2 283, P3 49, P4 2, N1 5, N2 86, N3 4.
- **Channels (documents):** EDI 900, PORTAL 656, EMAIL 340 (35, or 10.3%, from forwarding mailboxes; see §6),
  SCAN 104.
- **Payment terms (vendors):** NET15 30, NET30 135, NET45 90, NET60 45.
- **Intake by month:** January 60, then 158 to 266 per month, October 145 (intake closes 21 October).
- **Final status at the as-of date:** PAID 1,192, PAYMENT_READY 156, PENDING_APPROVAL 2,
  ON_HOLD 600, REJECTED 50.
- **Timeline spread (A-61):**
  - PRICE_VARIANCE, QTY_MISMATCH, DUPLICATE, MISSING_RECEIPT and TAX_VENDOR appear in all ten intake
    deciles.
  - INVOICE_BEFORE_PO (20 invoices) appears in 9 of 10.
  - ARITHMETIC (20) and CAPTURE_REVIEW (10) appear in 7 of 10.
- **Weekday share:** 100% for PO dates, receipts, invoice dates and intake, all on business days.

## 5. Carry-forward items closed

| Item | Closed by |
|---|---|
| Exact boundaries | PO price is a multiple of 0.50, so 2% is a whole cent; quantities are multiples of 20, so 5% is a whole unit. The values are asserted when constructed and tested |
| No unintended duplicate pairs | Oracle intent assertion, validator check and test. A12 invoices differ in date and amount; repeat-order pairs differ in PO; series differ in date. Altered numbers use letter suffixes only, so they cannot collide with genuine numbers |
| Closures after activity | Dedicated tail vendors with exactly one 2026 PO, and the status change strictly between receipt and invoice |
| As-of hard limit | Intake closes 2026-10-21, and timelines are redrawn if late; validator and test check every completed timestamp |
| Over-receipt reported as labelled | Validator labelled count; test that the over-tolerance POs are exactly the labelled ones |
| PYTHONHASHSEED and determinism | As above |
| Baseline self-checks (P-9) | The baseline must pass 0/0 or the build fails |

## 6. Known gaps (later stages)

- **Inbox documents are Stage 3.** Until then `intake_manifest.file_sha256` and `file_bytes` are
  empty and reported as pending (ADR-039). `file_path` already names the target file.
- **Engine-side tables are Stages 3-4:** captured invoices, bridge allocations, exceptions,
  approvals, payments and AP events. The ground truth already holds the expected approvals,
  payments, due and scheduled dates.
- **Exception types present:** 16 of the 24 types occur in the full dataset.
  - The 7 ADR-036 types are absent by design: VENDOR_NOT_FOUND, VENDOR_SENDER_MISMATCH,
    PO_NOT_FOUND, INVOICE_DATE_IN_FUTURE, TAX_CODE_INVALID, PO_LINE_UNMATCHED and
    VENDOR_NOT_PAYABLE.
  - The non-blocking PAYMENT_DUE_DATE_PASSED is rule-derived, but with this seed no invoice is ready
    after its due date.
  - All 8 get unit-test fixtures and "not present" per-type metrics in Stage 4.
- **Size:** the full build is 18.2 MB without documents (CSV plus indented JSON exports). Stage 5
  must fit the Q3 limit of about 25 MB with documents, for example with compact JSON or with
  checksums only for the full-scale JSON.
- **Starter coverage:** at starter scale, PENDING_APPROVAL and bands P4, N1 and N3 do not occur.
  Bands depend on amount and approval status depends on timing; both appear at full scale.
- **Forwarding mailboxes:** 35 of 340 EMAIL documents (10.3%) come from a forwarding mailbox. That
  is the low end of the 10-15% stated in ADR-037.
  - Each EMAIL invoice is drawn independently at 15%, giving 34 of 307 originals (11.1%).
  - Duplicates mostly reuse the vendor's own address.
  - An exact quota is possible if REV prefers it, but it would change the dataset hashes.
- **Business days only:** by construction, every PO date, receipt, invoice date and intake timestamp
  falls on a business day (weekday share 100%). This is a simplification: real vendors sometimes
  date invoices on a Saturday, and portal or EDI uploads can arrive at weekends.
- **Boundary sandboxes:** the static import and name bans are active now. The runtime blind and
  ID-blind runs come in Stage 3, and the time-travel run in Stage 4.

## 7. Questions

None blocking. Note for REV: the policy file changed only in its turnaround values. Policy version
stays 1.0.0, because no data has been released under it; the first committed data will use 1.0.0.
