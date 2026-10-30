# Assumptions and decisions (ADRs)

Each entry records a decision, the alternatives considered and the trade-off. Entries marked
**deviation** depart from a sprint recommendation, as the brief requires them to be recorded.

## Structure and identifiers

**ADR-001 Flat package layout (deviation, accepted by REV ruling Q4).** The package lives at `invoice_ap/` in the repo root
instead of `src/invoice_ap/`. *Why:* `python -m invoice_ap ...` then works straight after `git clone`
on any OS, with no install step and no `PYTHONPATH`, and the runtime has no dependencies to install
anyway. *Alternative:* src layout plus `pip install -e .`, which prevents accidental imports of
uninstalled code but adds a step that fails offline without build isolation. *Trade-off:* the
no-leakage boundary is enforced by tests (`tests/test_boundary.py`), not by directory layout.
`pip install -e .` still works.

**ADR-002 `<vendor-code>` = `vendor_id`.** `INV-VND-00001-2026-000001` embeds the vendor reference
exactly, so a test can check it. *Alternative:* a short separate vendor code (e.g. `ACME`). That
needs a second unique, immutable key and adds a way for references to disagree.

**ADR-003 Global 6-digit invoice counter, assigned after vendor resolution (deviation).** The
counter is the document's global intake sequence (`intake_seq`, which is also the `DOC-` number). The
vendor's printed number is a separate field (`vendor_invoice_number`), and duplicates collide on that
field. A resubmission is a new document and gets a new `invoice_id`. Because the ID embeds the
vendor, the engine assigns it only after VEN-01 has read the vendor from the document (rule ID-01).
The intake manifest therefore records the document but not the invoice ID, a departure from the
plan's "manifest records invoice id" (ADR-037). *Alternative:* a per-vendor counter
(`...-2026-000001` for each vendor's first invoice). It is equally valid but makes intake order
invisible in IDs.

**ADR-004 Year segment fixed to 2026; extra ID formats.** All business dates fall in 2026, the year
the assignment's formats carry. Reference IDs have no year: `VND-00001`, `SKU-00001`, `USR-0001`,
`VSH-000001`. Transactional IDs follow the assignment style: `POL-<po>-01`, `GRNL-<grn>-01`,
`DOC-`, `ERP-`, `EVT-`, `EXC-`, `APR-`, `PAY-`, `ALC-`, `DUP-`, `EXF-` with `-2026-` and 6 digits.
With the as-of date in October 2026, every completed event and every scheduled payment date also falls in 2026.

## Volumes and mix

**ADR-005 Mix accounting: five exact categories, two edge cases carved from CLEAN.** Price variance
200, quantity mismatch 160, duplicates 100, missing receipt 80 and tax/vendor 60 are exact (10/8/5/4/3%).
"Invoice total differs from line sum" (ARITHMETIC, 20) and "invoice date before PO date" (20) are
required edge cases outside the six named categories. They take 1% each from CLEAN. Degraded scans
(CAPTURE_REVIEW, 10) take 0.5% (ADR-017). CLEAN is therefore 1,350 (67.5%), reported as such and
accepted by REV (rulings Q1 and Q2; the A-36 floor is 1,340). *Alternative:* fold them into category families (for
example arithmetic into "tax/vendor"), keeping clean at 70% but stretching the category names.
*Trade-off:* honest category semantics against a clean share 2.5 points under "~70%".

**ADR-006 Partial delivery is both clean and exception.** Clean: an invoice equal to the received
quantity (`C-PARTIAL-OPEN`, every non-final split delivery, consolidated invoices over partial
receipts). Exception: a partial delivery billed in full (`QM-PARTIAL-BILLED-FULL`).

**ADR-021 One code path for every scale.** Targets are `round_half_up(full x factor)`; every split
uses exact Hamilton apportionment with a minimum of 1 per sub-scenario. Starter = factor 1/10. If a
factor is too small to cover every sub-scenario, the run fails instead of silently dropping cases.
Tested at 0.1, 0.25, 0.5, 1 and 2.

**ADR-022 Exact PO-fulfilment archetypes.** 1,500 POs, 1,800 receipts and 2,000 invoices are tied
together by eight archetypes whose counts solve three linear identities exactly
([data_generation §4](data_generation.md)). A21 (one invoice line over two GRN lines) and A12 (one
GRN line billed on two invoice lines, added for S1-R1-05) exercise the N:M bridge in both
directions. *Alternative:* random draws followed by a repair loop.
It is harder to document and to prove exact, and the mix is less controllable.

**ADR-023 PO line histogram.** A fixed skewed weight vector (mean 1.47 lines/PO), apportioned and
then repaired one PO at a time to hit 2,200 exactly. At least one 1-line and one 8-line PO are kept
whenever the total allows.

**ADR-008 Non-PO invoices (services).** 5% of invoices are non-PO originals from SERVICES vendors:
recurring monthly fees and one-off jobs. They follow vendor, duplicate, arithmetic and tax checks,
then requester approval plus the amount band. They are never matched (`match_status = NOT_APPLICABLE`).

**ADR-017 Degraded scans are their own category, CAPTURE_REVIEW (revised after REV ruling Q2).**
Ten invoices (one at starter scale) are rendered as degraded scans with an unreadable required field.
Their business content is otherwise clean, but the expected outcome is a hold in capture review
(`EXT_LOW_CONFIDENCE`), which exercises the low-confidence route end to end with real data. They are
carved out of CLEAN like ARITHMETIC and INVOICE_BEFORE_PO. CLEAN now means "no intended issue,
approval path" without exception, and `is_anomaly` means "intended issues not empty". A test
enforces this invariant. *Superseded alternative:* counting them inside CLEAN, which made
`is_anomaly = false` contradict `expected_blocked = true` (S1-R1-03).

## Rules and policy

**ADR-007 Inclusive, symmetric tolerances with boundary trios.** Price +-2% of the PO unit price,
inclusive. Over-receipt and over-billing up to ordered x 1.05, inclusive. Tax and arithmetic within
0.01. The data contains just-inside, exactly-at and just-outside cases. *Alternative:* an absolute
cap per line on top of the percentage. Rejected for now because it makes boundaries harder to
explain; it is a listed next step.

**ADR-020 Precedence and gates.** The primary issue is the highest-ranked blocking issue in the
order: capture, duplicates, vendor, PO reference, dates, arithmetic, tax, receipt, quantity, price
([business_rules §5](business_rules.md)). There are three gates. A low-confidence capture stops
checking, because the values cannot be trusted. A detected duplicate stops matching, so it never
consumes receipt quantity. A missing or foreign PO stops line matching. Otherwise every issue is
collected, so multi-issue invoices are fully labelled.

**ADR-024 Cumulative quantity semantics.** Per PO line, prior invoiced = earlier invoices in intake
order that reached line matching, including those on hold, because they are claims on the receipt.
Duplicates, capture holds and foreign-PO invoices are excluded. The
check is against cumulative received at processing time and against ordered x 1.05. *Alternative:*
count only approved invoices. That would let two held invoices both bill the same receipt.

**ADR-012 Time-aware matching, no automatic re-match.** Only receipts posted before the invoice is
processed count. An invoice that arrives before its receipt is held for missing receipt. The
missing-receipt scenarios never receive goods by the as-of date. *Alternative:* re-evaluate held
invoices when a later receipt posts (like SAP MRBR). This is realistic but adds a second decision
path; it is a next step.

**ADR-025 Vendor status model.** The statuses are ACTIVE, BLOCKED and CLOSED, effective-dated in
`vendor_status_history`. VEN-02/03 use the status on the **invoice date** (as the brief specifies).
PAY-03 rechecks payability on the **ready date**. Generated closures and blocks are placed so they
affect only their scenario invoices.

**ADR-009 Duplicate rules.** DUP-01 is an exact resubmission (vendor, normalised number, date and
gross) and is rejected. DUP-02 reuses a number with different content and is held. DUP-03 has the
same content (vendor, date, gross and PO) under an altered number and is held. The lookback covers
all earlier documents. The normalisation is: uppercase, split on non-alphanumerics, strip leading
zeros per numeric token, join. The true negatives are recurring same-amount monthly invoices and
same-day, same-amount invoices on different POs. *Trade-off:* DUP-03 could fire on two genuinely
different same-day deliveries of one PO for the same amount. The generator avoids that pattern, and
the oracle would flag it if it occurred.

**ADR-013 Currency and tax model.** INR only. Tax codes are a simplified, synthetic GST-style set:
GST0, GST5, GST18, EXEMPT, plus GST12 retired on 2025-09-21 to exercise validity dates. There is no
CGST/SGST/IGST split, no reverse charge, no withholding, and it is not tax advice. *Alternative:*
multi-currency with FX. That is out of scope and listed as a next step.

**ADR-014 Exact arithmetic.** Decimal with ROUND_HALF_UP at 0.01, tax per line, and quantities at
the unit of measure's precision. CSV, JSON and SQL carry decimals as canonical strings or numerics,
never binary floats. JSON money is a string, documented in the data dictionary.

**ADR-030 Approval matrix.** Matched PO invoices up to 2,00,000 are approved automatically by the
SYSTEM (touchless, STP). Above that, L1, then L1+L2 above 10 lakh, then L1+L2+L3 above 50 lakh.
Non-PO invoices: the requester always, plus L1 above 50,000 and L2 above 5 lakh. Simulated
turnarounds are 2 business days for REQ and L1 and 3 for L2 and L3. That is realistic, and it leaves
the latest invoices in flight (PENDING_APPROVAL) at the as-of date. STP = invoices that
became payment-ready with only SYSTEM actions. *Alternative:* human approval for everything, which
makes the STP rate meaningless.

**ADR-031 Payment scheduling.** Pay on the due date (invoice date + term days, moved to the previous
business day), never before the next business day after readiness. If the due date has passed, pay
the next business day and raise the non-blocking `PAYMENT_DUE_DATE_PASSED`. RTGS at or above 2 lakh,
otherwise NEFT. A simulated payment run marks scheduled dates on or before the as-of date as PAID.

**ADR-032 Extraction never corrects printed values.** Each field carries raw text, a normalised
value, a method and a confidence. Below 0.90 the document routes to the operations analyst. A wrong
printed total survives extraction so that ARI-02 catches it. The extractor has no access to PO or
master values when it reads a field; it may use only the label synonyms and format rules of its
channel.

## Process model

**ADR-010 The engine creates approvals and payments.** The assignment lists approval and payment
creation inside its generation logic. Here the engine creates them, as an AP system would, from its
own decisions. The oracle's expected approvals and payments sit in ground truth, so R9h is
evaluated rather than assumed. The exported relational dataset contains both.

**ADR-011 As-of snapshot semantics.** Everything is evaluated at the fixed past date
`as_of_date = 2026-10-22` (S1-R1-04). It precedes the submission window and is never read from the
clock. No completed event lies after it: vendor status changes, GRN postings, invoice receipt and
capture, raised exceptions, approval decisions and PAID payments. Only forward-dated plans may: due
dates, SLA dates and scheduled payment dates. At the as-of date:
- exceptions are routed with SLAs but not resolved (no simulated human fixes), so held invoices
  stay ON_HOLD;
- simulated approvers approve after fixed turnarounds, and levels still undecided at the as-of date
  stay PENDING;
- rejection paths exist in the state machines but are not produced, because no policy rule
  triggers them.

*Alternative:* simulate resolutions. That would need invented human decisions, which could look like
random labels.

**ADR-018 Event model.** There are three append-only event tables with a common shape (from, to,
timestamp, actor role and id, reason or rule, policy version):
- `vendor_status_history` (effective-dated);
- `erp_event` (PO, GRN);
- `ap_event` (invoice, exception, approval, payment).

The current status of every entity equals its last event. The state machines are defined once in
`invoice_ap/common/lifecycle.py` and rendered into [schema.md](schema.md).

**ADR-019 Actors.** The five human roles plus a SYSTEM automation actor live in `actor_role`.
`app_user` has role-labelled synthetic users with named responsibilities (cost-centre manager,
finance controller, CFO, vendor-master owner, policy owner and so on). Assignment inside a role is
deterministic.

**ADR-026 The Invoice entity has two representations.** `source/invoice` is the invoice as issued;
it is evaluation-only. `processed/captured_invoice` is the invoice as captured; approvals, payments
and events point to it. They share `invoice_id` 1:1. No FK points from engine tables into
evaluation-only layers, a rule enforced by a test.

**ADR-035 Every declared FK stays valid.** Deliberate defects are business-rule defects with valid
keys. For example, `VENDOR_PO_MISMATCH` quotes a real PO of another vendor. The SQL seed therefore
loads with `PRAGMA foreign_keys=ON`, and the validation suite reports labelled defects apart from
violations.

**ADR-036 Rules exercised only by unit tests.** `VENDOR_NOT_FOUND`, `VENDOR_SENDER_MISMATCH`, `PO_NOT_FOUND`,
`INVOICE_DATE_IN_FUTURE`, `TAX_CODE_INVALID`, `PO_LINE_UNMATCHED` and `VENDOR_NOT_PAYABLE` are
implemented and tested with fixtures but not injected into the dataset. That keeps the mix aligned
with the assignment's categories. Their per-type metrics are reported as "not present".

**ADR-037 Vendor identity comes only from the document (S1-R1-01).** REV found that the intake
manifest handed the engine the true vendor twice: inside `invoice_id`, and in a `sender_vendor_id`
that was set for every channel, including scans. Both of REV's paths are taken.
- **(a) Channel-realistic intake.** The manifest has `doc_id` and `intake_seq` but no `invoice_id`.
  `sender_vendor_id` is set only where the channel authenticates the sender (PORTAL account, EDI
  partner). EMAIL carries only the From address; the forwarding mailbox is drawn at 15% per e-mail
  original, realised 10.3% of e-mail documents (11.1% of originals) at full scale (REV ruling Q1).
  SCAN carries only a mailroom batch ID.
- VEN-01 reads the vendor from the printed tax registration number and is the only source of
  `captured_invoice.vendor_id`. ID-01 then builds the invoice ID from that vendor. An unresolved
  vendor gets the reserved code `VND-00000`.
- **(b) VEN-04 `VENDOR_SENDER_MISMATCH`** (blocking; OPERATIONS_ANALYST, AP_VALIDATION, SLA 2)
  compares the authenticated sender with the VEN-01 vendor. This gives the sender field a legitimate
  use.
- **Guards.**
  - A static test bans, in engine code: reading sender fields outside the VEN-04 module,
    `vendor_of_invoice`, and slicing an `invoice_id`. It is active now.
  - The Stage-3 ID-blind sandbox blanks `sender_vendor_id` and `sender_address` in a temp copy of
    the inbox and requires identical decisions.
  - An engine that took the vendor from the sender would also misidentify the forwarded e-mails,
    and vendor-resolution accuracy would expose it.

*Trade-off:* the invoice ID becomes an engine output. Evaluation therefore joins on `doc_id` and
reports invoice-ID agreement as a metric.

**ADR-038 Snapshot columns are reporting only (S1-R1-02).** The current-status conveniences in
master are evaluated at the as-of date:
- `vendor.snapshot_status`
- `purchase_order.snapshot_status`
- `purchase_order_line.snapshot_received_qty` and `snapshot_open_qty`
- `goods_receipt.snapshot_status`

For an invoice processed earlier, they hold future information. They carry the `snapshot_` prefix
and are flagged `reporting_only` in the spec. The engine uses effective-dated history and receipts
posted before processing time instead.

*Guards:*
- a static ban on `snapshot_` in engine code (active now);
- the Stage-4 time-travel sandbox: for sampled invoices, drop master rows and events recorded after
  the processing time and blank the snapshots; the decision must not change.

*Alternative:* move the snapshots out of master. Rejected: they make the committed CSVs easier to
read, and the guards make any read of them detectable.

**ADR-039 Stage-2 generator mechanics.**
- **Two phases from one plan.** Every random draw is made once, in the planner. `materialize()`
  then builds a baseline (all invoices clean, no duplicates, no injected status changes), which
  must self-validate with 0 violations and 0 labelled defects, and a final phase that adds only
  the labelled injections. A test compares the phases. Master rows are identical except the
  labelled vendors and the over-receipt POs, and clean invoices are identical.
- **Dates.** Each PO's timeline is drawn from an optimistic window and redrawn deterministically,
  up to 11 times, if any invoice would arrive after intake close (2026-10-21). The worst-case
  window is the last resort. Invoices of one PO arrive in billing order, so cumulative labels land
  on the intended invoice.
- **Dedicated vendors.** Closed and blocked vendors are tail vendors whose only 2026 activity is
  their scenario PO. The status change falls strictly between the receipt and the invoice date.
- **Duplicates.** An exact resubmission copies its original's content, defects included. The
  validator reports such a copy under the original's label, never as an unlabelled defect.
- **Intake manifest.** It is written in Stage 2, because the oracle needs intake times and
  `invoice.doc_id` must resolve. Since Stage 3, `file_sha256` and `file_bytes` describe the rendered
  document (ADR-040), so no manifest field is pending any more.

**ADR-040 Documents and extraction (Stage 3).**
- **Four formats, one per channel.** PORTAL_JSON (portal schema v1 with string values, or v2 with
  camelCase keys, numeric amounts and timestamps), EDI_FLAT (segments; the separator, terminator
  and amount mode, decimal or two implied decimals, vary by trading partner), EMAIL_TEXT (an RFC 822
  message, optionally forwarded by an internal mailbox) and OCR_TEXT (the text of a scanned
  invoice: upper-case labels, two label pairs per line, fixed-width tables that break across
  pages). Each vendor has one seeded template per channel: labels, date format, amount style, tax
  code style, PO style and table layout (pipe, columns or item blocks).
- **Recoverable variation only, except CAPTURE_REVIEW.** In the 10 degraded scans one required header
  field (total, date or invoice number) is smudged or printed with OCR look-alike characters.
  Invoice numbers are only smudged, because look-alike letters would be indistinguishable from a
  legitimate alphanumeric number.
- **Engine-side synonyms are independent.** The extractor has its own label and column synonym list
  (`engine/labels.py`) and its own format rules (`engine/normalize.py`); it imports nothing from the
  renderer. An unknown label is not read, so the field is NOT_FOUND and the document is routed.
- **Confidence per method:** STRUCTURED 1.00, SEGMENT 0.99, LABEL_EXACT 0.98, PATTERN 0.97,
  LABEL_SYNONYM 0.95, OCR_REPAIRED 0.60, a conflicting second read 0.50, a quantity with more decimals
  than its unit allows 0.80, NOT_FOUND 0.00. CAP-01 takes the minimum over the required fields, every
  optional field that is printed and the line-item block. The extraction evaluation reports accuracy
  per confidence value, which is the calibration evidence.
- **Layout rules.** Header fields are read above the item section and totals below it; e-mail
  transport headers and forwarded-message header blocks are never invoice content; dates are
  day-first; a value that fails its format is unreadable, never guessed. Nothing is recomputed from
  lines or from the PO.
- **Stage-3 engine scope.** Intake order, CAP-01, VEN-01, ID-01 and VEN-04, with EXT_LOW_CONFIDENCE,
  VENDOR_NOT_FOUND and VENDOR_SENDER_MISMATCH routed by RTE-01 into `processed/ap_exception.csv`, and
  `processed/decision_trace.jsonl`. Stage 4 added the later rules and moved the VEN-04 check behind
  the duplicate gates, as in the rule order (ADR-041). `captured_at` = `received_at` + 1 minute
  (a synthetic processing time, never the wall clock).
- **Not in this stage:** the printed tax code must be one of the five codes, so an unknown code is
  unreadable rather than captured; TAX_CODE_INVALID therefore stays a unit-test-only type (ADR-036).

**ADR-041 Stage-4 decision engine mechanics.**
- **Independent implementation.** The engine (`engine/validate.py`, `engine/decide.py`) applies the
  rule catalogue to *captured* values and master data; it imports nothing from the generator or the
  oracle. Agreement with ground truth is measured, not assumed; a tolerance mutation makes the
  engine and the evaluation disagree, which proves the comparison is not circular (ADR-016 states
  the remaining limitation: one author wrote both).
- **Processing time.** Receipt and PO cutoffs use the intake timestamp (`receipt_cutoff =
  PROCESSING_TIME`), as the oracle does. Vendor status uses the effective-dated history *recorded*
  by the moment of the decision, so a back-dated change entered later cannot leak backwards.
  Events are stamped: RECEIVED at intake, CAPTURED +1 minute, the decision +1 more minute.
- **Gates and order.** CAP-01, VEN-01 and the duplicate gates stop later checks; VEN-04 runs after
  the duplicate gates; everything else is collected. Duplicates never reach matching, so they
  neither consume receipts nor count as prior invoiced quantity. An exact duplicate is REJECTED and
  its exception auto-closes; every other blocking issue puts the invoice ON_HOLD.
- **Match status.** As in business_rules section 4; a line that maps to no PO line makes the match
  status NOT_EVALUATED (the oracle was aligned; no generated invoice has such a line).
- **N:M bridge.** Each invoice line that reached matching is allocated FIFO to the GRN lines of its
  PO line posted before processing, net of earlier allocations: one GRN line can serve several
  invoice lines (partial billing) and one invoice line several GRN lines (consolidated billing).
- **Approvals and payments.** Requested at the decision time; each level decides after its
  turnaround at the same clock time; a level due after the as-of date stays PENDING. The ready
  moment is the last approval; PAY-03 reads the vendor status known then; the payment run releases
  at 10:00 IST on the scheduled date.
- **Assignment.** L1 is the cost-centre manager of the PO's cost centre (non-PO: of the requester);
  REQ is the requester named on the invoice; operations-analyst exceptions round-robin in exception-id
  order; exceptions raised after approval (PAY-03, PAY-06) take the next IDs when they are raised.
- **Metrics.** STP = PAYMENT_READY or PAID with no exception and AUTO approval. Value at risk = full
  gross for duplicate, vendor, PO, date, receipt and capture holds; the excess quantity or price
  difference (with tax) for quantity and price variances; the absolute difference for tax and
  arithmetic. Types with no expected and no predicted instance report "not present", never 0/0.

## Data, determinism and engineering

**ADR-015 Determinism.**
- One master seed, with a sha256-derived `random.Random` sub-stream per concern.
- Only integer draws and Decimal maths. `math.exp`, `random.gauss`/`lognormvariate`, the wall
  clock and `uuid` are banned by test, because transcendental libm results can differ across
  platforms.
- Iteration is sorted, and CSV and JSON are written byte-stable.

**ADR-016 Ground truth by oracle plus intent assertion.** The oracle applies the documented rules to
the true data. Generation asserts that its labels equal the injection intent. The engine reaches its
own decisions from documents. *Limitation:* one author wrote the oracle and the engine, so a shared
misreading of a rule could agree with itself. This is mitigated by hand-computed fixture tests per
rule, the intent assertion and separate code paths.

**ADR-027 Lawful, synthetic data.** No external data is used.
- Vendor names are generated from word lists; any resemblance to a real company is coincidental.
- Tax registration numbers use a synthetic `TRN-` format.
- E-mail addresses use reserved domains (`.example`, `example.com`, RFC 2606).
- Users are role labels, not people.

The source manifest records the provenance.

**ADR-028 Committed datasets and size (REV ruling Q3).** Built data is committed so it can be
inspected without running anything, under these conditions:
- the full CSV layers, inbox documents, reports and manifest are committed, and the layer CSVs are
  the CSV export (no copies);
- JSON and SQL exports are committed for the starter build;
- the full-scale JSON and SQL are committed only if the total committed data stays at or below
  about 25 MB, as measured. Otherwise their SHA-256 checksums are recorded in the manifest and
  `build-all` regenerates them;
- generated data is committed only when Stages 5 and 6 close, to keep history small;
- a parity check proves the committed data equals a fresh build (A-54).

**ADR-029 Calendar.** Sat/Sun weekends plus four fixed national holidays (26 Jan, 15 Aug, 2 Oct,
25 Dec). Timestamps are IST (+05:30).

**ADR-033 Generated documentation.** The data dictionary, key lists, state machines, routing and
approval matrices and allocation tables are rendered from code and config by
`python -m invoice_ap docs`. Tests fail when a document is stale, so docs and implementation cannot
drift.

**ADR-034 Runtime.** Python >= 3.11, standard library only (`tomllib` needs 3.11). `pytest` is the
only development dependency. There is no network access and no hosted services.

## Rulings on the Stage-1 open questions (stage-1-review-1)

1. Q1, clean at 68%: **accepted**. After the Q2 change, clean is 1,350 (67.5%), also accepted
   (ADR-005).
2. Q2, degraded-capture overlay: **its own category** CAPTURE_REVIEW (ADR-017).
3. Q3, committed data size: **accepted under conditions** (ADR-028).
4. Q4, flat layout: **accepted** (ADR-001).
5. Orchestrator point: the as-of date moves to the fixed past date 2026-10-22 (ADR-011).
