# Assumptions and decisions (ADRs)

Each entry records a decision, the alternatives considered and the trade-off. Entries marked
**deviation** depart from a sprint recommendation, as the brief requires them to be recorded.

## Structure and identifiers

**ADR-001 Flat package layout (deviation).** The package lives at `invoice_ap/` in the repo root
instead of `src/invoice_ap/`. *Why:* `python -m invoice_ap ...` then works straight after `git clone`
on any OS, with no install step and no `PYTHONPATH`, and the runtime has no dependencies to install
anyway. *Alternative:* src layout plus `pip install -e .`, which prevents accidental imports of
uninstalled code but adds a step that fails offline without build isolation. *Trade-off:* the
no-leakage boundary is enforced by tests (`tests/test_boundary.py`), not by directory layout.
`pip install -e .` still works.

**ADR-002 `<vendor-code>` = `vendor_id`.** `INV-VND-00001-2026-000001` embeds the vendor reference
exactly, so a test can check it. *Alternative:* a short separate vendor code (e.g. `ACME`). That
needs a second unique, immutable key and adds a way for references to disagree.

**ADR-003 Global 6-digit invoice counter in intake order.** One global sequence over all received
documents. The vendor's printed number is a separate field (`vendor_invoice_number`), and duplicates
collide on that field. A resubmission is a new document and gets a new `invoice_id`. The intake
system assigns the ID from the sender's vendor identity: portal account, EDI partner, e-mail sender
or mailroom indexing. The engine still resolves the vendor independently from the printed tax
registration number. *Alternative:* a per-vendor counter (`...-2026-000001` for each vendor's first
invoice). It is equally valid but makes intake order invisible in IDs.

**ADR-004 Year segment fixed to 2026; extra ID formats.** All business dates fall in 2026, the year
the assignment's formats carry. Reference IDs have no year: `VND-00001`, `SKU-00001`, `USR-0001`,
`VSH-000001`. Transactional IDs follow the assignment style: `POL-<po>-01`, `GRNL-<grn>-01`,
`DOC-`, `ERP-`, `EVT-`, `EXC-`, `APR-`, `PAY-`, `ALC-`, `DUP-`, `EXF-` with `-2026-` and 6 digits.
Payments scheduled into 2027 keep `PAY-2026-` because the record is created in 2026.

## Volumes and mix

**ADR-005 Mix accounting: five exact categories, two edge cases carved from CLEAN.** Price variance
200, quantity mismatch 160, duplicates 100, missing receipt 80 and tax/vendor 60 are exact (10/8/5/4/3%).
"Invoice total differs from line sum" (ARITHMETIC, 20) and "invoice date before PO date" (20) are
required edge cases outside the six named categories. They take 1% each from CLEAN, which is
therefore 1,360 (68.0%), reported as such. *Alternative:* fold them into category families (for
example arithmetic into "tax/vendor"), keeping clean at 70% but stretching the category names.
*Trade-off:* honest category semantics against a clean share 2 points under "~70%".

**ADR-006 Partial delivery is both clean and exception.** Clean: an invoice equal to the received
quantity (`C-PARTIAL-OPEN`, every non-final split delivery, consolidated invoices over partial
receipts). Exception: a partial delivery billed in full (`QM-PARTIAL-BILLED-FULL`).

**ADR-021 One code path for every scale.** Targets are `round_half_up(full x factor)`; every split
uses exact Hamilton apportionment with a minimum of 1 per sub-scenario. Starter = factor 1/10. If a
factor is too small to cover every sub-scenario, the run fails instead of silently dropping cases.
Tested at 0.1, 0.25, 0.5, 1 and 2.

**ADR-022 Exact PO-fulfilment archetypes.** 1,500 POs, 1,800 receipts and 2,000 invoices are tied
together by seven archetypes whose counts solve three linear identities exactly
([data_generation §4](data_generation.md)). *Alternative:* random draws followed by a repair loop.
It is harder to document and to prove exact, and the mix is less controllable.

**ADR-023 PO line histogram.** A fixed skewed weight vector (mean 1.47 lines/PO), apportioned and
then repaired one PO at a time to hit 2,200 exactly. At least one 1-line and one 8-line PO are kept
whenever the total allows.

**ADR-008 Non-PO invoices (services).** 5% of invoices are non-PO originals from SERVICES vendors:
recurring monthly fees and one-off jobs. They follow vendor, duplicate, arithmetic and tax checks,
then requester approval plus the amount band. They are never matched (`match_status = NOT_APPLICABLE`).

**ADR-017 Capture-quality overlay sits inside CLEAN.** Ten business-clean invoices (one at starter
scale) are rendered as degraded scans with an unreadable required field. Their true invoice is
clean, so they count in CLEAN. Their expected outcome is a hold in capture review
(`EXT_LOW_CONFIDENCE`), which exercises the low-confidence route end to end. *Alternative:* a separate
category, which would lower CLEAN further. *Trade-off:* "clean" means the business content, not
the document quality, and the report states this split.

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

**ADR-024 Cumulative quantity semantics.** Per PO line, prior invoiced = earlier non-duplicate
invoices in intake order, including those on hold, because they are claims on the receipt. The
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
Non-PO invoices: the requester always, plus L1 above 50,000 and L2 above 5 lakh. STP = invoices that
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

**ADR-011 As-of snapshot semantics.** Everything is evaluated at 2026-12-31:
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

**ADR-036 Rules exercised only by unit tests.** `VENDOR_NOT_FOUND`, `PO_NOT_FOUND`,
`INVOICE_DATE_IN_FUTURE`, `TAX_CODE_INVALID`, `PO_LINE_UNMATCHED` and `VENDOR_NOT_PAYABLE` are
implemented and tested with fixtures but not injected into the dataset. That keeps the mix aligned
with the assignment's categories. Their per-type metrics are reported as "not present".

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

**ADR-028 Committed datasets and size.** Starter and full builds are committed so they can be
inspected without running anything. The layer CSVs are the CSV export (no copies). JSON and SQL are
added once each. The estimated size is about 4 MB for starter and 30-45 MB for full; Stage 5
measures it and slims the files if needed.

**ADR-029 Calendar.** Sat/Sun weekends plus four fixed national holidays (26 Jan, 15 Aug, 2 Oct,
25 Dec). Timestamps are IST (+05:30).

**ADR-033 Generated documentation.** The data dictionary, key lists, state machines, routing and
approval matrices and allocation tables are rendered from code and config by
`python -m invoice_ap docs`. Tests fail when a document is stale, so docs and implementation cannot
drift.

**ADR-034 Runtime.** Python >= 3.11, standard library only (`tomllib` needs 3.11). `pytest` is the
only development dependency. There is no network access and no hosted services.

## Open questions for review

1. ADR-005: is a 68.0% clean share acceptable, given that the two extra edge cases are carved out
   transparently?
2. ADR-017: should the degraded-capture overlay count inside CLEAN (business-clean, held for capture
   review) or be its own category?
3. ADR-028: is committing a full build of about 30-45 MB acceptable, or should the full-scale JSON
   export be compacted?
4. ADR-001: is the flat layout acceptable in place of the recommended `src/` layout?
