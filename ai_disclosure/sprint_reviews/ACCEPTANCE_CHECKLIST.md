# REV acceptance checklist: Invoice-to-Pay (AP) automation

Owner: REV (independent reviewer). Version 1, 2026-10-29.
Source of truth: `/home/claude/sprint/ASSIGNMENT.md`. If anything here conflicts with it, the assignment wins.

Method: REV drafted this checklist from ASSIGNMENT.md alone, before opening SPRINT_PLAN.md. The draft is kept at
`reviews/scratch/rev_independent_draft.md`. REV then compared it with SPRINT_PLAN.md §5 and merged the two. Items that the
§5 checklist lacks are marked **REV-added**. Where the plan's §4 stage text or the DEV brief already asks for an item,
that is noted, so DEV's targets do not move.

## How to read an item
- **Source**: the part of ASSIGNMENT.md plus an exact quote. A = problem statement, B = guidelines, C = FAQ.
- **Done when**: the definition of done that REV will test.
- **Verify**: the command, inspection or test that REV runs itself. "REV-IC" means REV's own independent checker
  scripts in `reviews/scratch/`. They use only the standard library, read exported files, and never import repo code.
  `<out>` is a fresh build directory in REV scratch. `<pkg>` is DEV's package name.
- **Stage**: the stage in which the item must be met. "spec 1" means Stage 1 must already specify it.
- **Class** sets the default severity for an unmet item, so targets stay the same across rounds:
  - REQ: required by the assignment. Missing is a BLOCKER; partly met is a MAJOR.
  - REQ\*: REV's reading of what an explicit requirement needs in order to be credible. Missing is a MAJOR.
  - QI: a quality improvement. Missing is a MINOR (or a NIT where stated). A written justification can close it as an
    accepted deviation.
- **Plan**: the SPRINT_PLAN §5 id(s), or REV-added.

---------------------------------------------------------------------------------------------------

## 1. End-to-end workflow (A: Business Context, Objective and Scope, Primary Actors)

### A-01 · End-to-end working solution
Stage 4 (one-command build: 5) · REQ · Plan R1
- Source: A Objective: "Build a working solution for this end-to-end workflow: Automate invoice intake, field extraction, PO/receipt matching, exception routing and payment readiness."
- Done when:
  - One documented command runs every step at starter and full scale: generate, intake, extract, validate, match,
    route, approve, payment readiness, evaluate.
  - The command exits with code 0.
  - Every invoice ends with exactly one final status and a decision trace.
- Verify:
  - Run the README command into `<out>` at both scales and check the exit code.
  - REV-IC: the number of distinct invoice_ids with a final status equals the invoice count (2,000 at full scale).

### A-02 · Invoice intake
Stage 3 · REQ (idempotency: QI) · Plan R1 (plus plan §4 St3)
- Source: A Business Context: "Automate invoice intake"
- Done when:
  - Every invoice exists as a rendered document in an inbox.
  - Each document has an intake-manifest row: document id, channel, received timestamp, sender and content hash.
  - Manifest rows = documents = invoices.
  - Timestamps are generated; nothing reads the wall clock.
  - No label appears in the manifest or in file names.
  - QI: re-running intake on the same inbox gives byte-identical outputs and no extra invoices.
- Verify:
  - REV-IC: the manifest and the inbox hold the same set of files, with SHA-256 recomputed.
  - Run intake twice and diff the outputs.
  - Grep manifest headers and file names for label words.

### A-03 · Field extraction
Stage 3 · REQ (3 or more channels: QI) · Plan R1, R34a (plus plan §4 St3)
- Source: A Business Context: "field extraction"
- Done when:
  - An extractor parses each document format into header fields and line fields. This must be real parsing that can
    fail, not a read of the canonical table.
  - Every field gets a confidence value.
  - The extractor never corrects printed values: a wrong printed total survives extraction.
  - A documented low-confidence rule routes documents to the operations analyst, and the rule is tested.
  - Plan target, beyond the minimum: at least 3 heterogeneous channels, vendor templates, label synonyms, and date and
    number variation. Falling short of 3 channels is a MINOR if at least one non-trivial format exists.
- Verify:
  - Inspect 2 documents per channel.
  - Mutation probe on scratch copies of 3 documents: garble a label, change a date format, alter a printed total. The
    extractor must either still be right or report low confidence or a mismatch. A silent wrong value fails.

### A-04 · PO/receipt (three-way) matching
Stage 4 · REQ · Plan R1, R9g
- Source: A Business Context: "PO/receipt matching"; A Workflow 3: "derive match status from price/quantity/tax tolerances"
- Done when:
  - Each PO-backed invoice line links to its PO line and to the GRN lines it consumes, through the allocation bridge.
  - The match compares against the policy tolerances: unit price; cumulative quantity (invoiced vs received vs
    ordered); tax code and tax amount.
  - Line statuses roll up to an invoice status by the documented precedence.
  - Non-PO invoices take the documented non-PO path.
- Verify:
  - REV-IC recomputes the match status from extracted data plus master data, for all boundary cases and 10 random
    invoices per category, and compares with the engine. Expect 100% agreement.
  - Policy-sensitivity probe: in a scratch copy, change the price tolerance. Only the price-boundary invoices may change
    status.

### A-05 · Exception routing
Stage 4 (spec 1) · REQ · Plan R1, R2, R6
- Source: A Business Context: "exception routing"; A Objective: "at least one exception path"
- Done when:
  - Every exception record carries: type, severity, blocking flag, expected vs actual values, tolerance used, rule id,
    policy version, assigned actor role and queue, SLA due date, status.
  - Each exception type maps to exactly one row of the routing matrix.
  - Every exception is routed to one of the five roles.
  - The exception lifecycle (open → resolved / rejected / held) is recorded as events.
  - At least one exception path runs end to end in the data: raised → routed → outcome.
- Verify:
  - REV-IC groups exceptions by type → role/queue and compares the result with the routing matrix in the policy file.
  - Count exceptions with a null role or queue. Expect 0.
  - Trace one exception per type through the event log.

### A-06 · Payment readiness
Stage 4 · REQ · Plan R1, R9h, R34e
- Source: A Business Context: "payment readiness"
- Done when:
  - payment_ready is derived by the documented rule: all required approval levels approved, no open blocking
    exception, vendor payable on the payment date, and not a duplicate.
  - Payment records exist only for payment-ready invoices.
  - The scheduled date comes from the payment terms, and the amount equals the approved payable amount.
- Verify:
  - REV-IC recomputes readiness from approvals, exceptions and vendor history.
  - Set-compare that result with the engine's payment_ready flag and with the invoices in Payment. Expect equality.
  - Check that payment date ≥ last approval date and payment amount ≤ invoice payable.

### A-07 · Key decisions and exceptions exposed
Stage 4 (dashboard view: 5) · REQ · Plan R2
- Source: A Objective: "The solution should expose key decisions and exceptions"
- Done when:
  - Every invoice has a decision trace (an "explain" view or file).
  - The trace lists each rule evaluated with its inputs, threshold, result, rule id and policy version, plus a
    plain-language reason.
  - Exceptions can be browsed per queue.
- Verify: run explain for one invoice per primary category and per edge case. REV checks each trace against
  business_rules.md.

### A-08 · Traceability
Stage 4 · REQ · Plan R3
- Source: A Objective: "preserve traceability"
- Done when:
  - Using IDs alone, REV can walk document → intake row → extracted invoice and lines → match allocations →
    exceptions → approvals → payment → events.
  - REV can also walk back to the PO, PO line, GRN line and vendor.
  - Every engine output row carries a run or build id and the policy version. Rows that a rule decided also carry the
    rule id.
- Verify: REV-IC walks the chain for 100% of payments and for one exception per type. Expect 0 broken links.

### A-09 · Measurable outputs
Stage 4 (actual numbers in docs: 6) · REQ · Plan R4, R5
- Source: A Objective: "produce measurable outputs"; "meaningful evaluation metrics"
- Done when:
  - A metrics file exists in JSON and in Markdown, with a definition for each metric.
  - Metrics include:
    - precision, recall and F1 per exception type;
    - a confusion matrix on the primary outcome;
    - duplicate pair accuracy;
    - extraction accuracy by field, document and channel;
    - approval-level agreement and payment-ready safety;
    - STP rate, exception rate and value at risk prevented.
  - Values are computed, not hard-coded, and stay the same across reruns.
- Verify:
  - REV recomputes at least 3 metrics (duplicate pair accuracy, STP rate, one precision/recall pair) from engine
    outputs and ground truth. They must match the report exactly.
  - Grep the report code for literal metric values.

### A-10 · Non-circular evaluation and the engine boundary
Stage 4 (design 1, boundary test 3) · REQ\*. The engine reading ground truth or source is a BLOCKER. Decision code
shared between oracle and engine is a MAJOR. · REV-added (plan §4 St2/St3 and DEV brief A cover it)
- Source: A Objective: "meaningful evaluation metrics"; A Step 7: "never leak it into input features"
- Done when:
  - The engine reads only master data and the inbox, and a test enforces this.
  - The engine never imports generator or oracle modules.
  - Ground truth comes from a separate rule-based oracle that runs on the true data and is asserted against the
    injection intent.
  - Engine errors show up in the metrics.
- Verify:
  - Scan the engine modules' imports (AST or grep).
  - Blind run: copy `<out>` to scratch, delete `ground_truth/` and `source/`, rerun the engine, and diff the processed
    outputs. Expect them to be identical.
  - Mutation probe on a scratch copy of the repo, for example a weakened duplicate rule. The metrics must drop.

### A-11 · Medium complexity
Stage 4 · REQ · Plan R5
- Source: A Objective: "Medium complexity means multiple related entities, conditional rules, at least one exception path and meaningful evaluation metrics."
- Done when: A-04 to A-10 and A-23 to A-26 are met together, and the README says how each of the four elements is
  covered.
- Verify: inspect the README and architecture doc against the four elements.

### A-12 · The five actors are represented
Stage 4 (spec 1, data 2; queue views are QI at 5) · REQ (listing them only in docs is a MAJOR) · Plan R6
- Source: A Primary Actors: "Business requester, process owner, approver, operations analyst and system administrator"
- Done when:
  - A role or user reference table holds all five roles.
  - Each role owns real records:
    - requester: POs and receipt confirmations;
    - approver: approval levels;
    - operations analyst: the AP exception queues;
    - process owner: the policy and policy exceptions;
    - system administrator: vendor master, configuration and runs.
  - A RACI is documented.
- Verify: REV-IC counts the records that reference each role (each ≥ 1) and compares them with the RACI.

## 2. Business workflow and generation rules (A: Business Workflow and Rules; Steps 2 and 6)

### A-13 · Master data first; dependents use valid parent IDs
Stage 2 · REQ · Plan R7, R8, R21
- Source:
  - A Workflow 1: "Generate/reference master data first: Vendor, PurchaseOrder, PurchaseOrderLine, GoodsReceipt, GoodsReceiptLine."
  - A Workflow 2: "Generate dependent transaction/event records using valid parent IDs."
  - A Step 2: "Create parent/master tables first, then child and event tables."
- Done when:
  - One orchestrating function builds the tables in this order: master → child → transactional → event.
  - Every FK resolves, apart from labelled defects (A-37).
- Verify: inspect the generator entry point; REV-IC orphan check.

### A-14 · Vendors first; POs reference vendors
Stage 2 · REQ · Plan R9a, R9b
- Source: A Workflow 3: "Create vendors first; create POs referencing vendors"
- Done when:
  - Every PO.vendor_id exists in Vendor.
  - Every PO date falls within its vendor's active window, unless labelled.
- Verify: REV-IC join plus a date-window check.

### A-15 · 1–8 PO lines with SKU, quantity, unit price and tax code
Stage 2 · REQ · Plan R9c
- Source: A Workflow 3: "add 1–8 PO lines with SKU, quantity, unit price and tax code"
- Done when:
  - Every PO has between 1 and 8 lines.
  - Every line has an SKU from the SKU reference, quantity > 0 with a UoM, unit price > 0, and a tax code from the tax
    reference.
  - Line numbers are unique within a PO.
  - Both tails occur: some POs have 1 line and some have 6 to 8.
- Verify: REV-IC line-count histogram plus null and domain checks.

### A-16 · Receipts: full, partial and over-receipt
Stage 2 · REQ · Plan R9d
- Source: A Workflow 3: "generate receipts referencing PO lines with full/partial/over-receipt quantities"
- Done when:
  - Every GRN line references a PO line on a PO for the same vendor.
  - Cumulative received quantity per PO line is classed as full, partial or over, and all three classes occur.
  - Over-receipt beyond tolerance is either labelled or prevented.
  - GRN date ≥ PO date.
- Verify: REV-IC compares cumulative received with ordered per PO line; each class count > 0.

### A-17 · Invoices reference a vendor and, optionally, a PO
Stage 2 (non-PO path: 4) · REQ (a non-nullable PO FK is a MAJOR; no non-PO invoices with a documented reason is a
MINOR) · Plan R9e
- Source: A Workflow 3: "generate invoices referencing vendor and optionally PO"
- Done when:
  - invoice.vendor_id is required and valid; po_id is nullable.
  - A documented, non-zero share of invoices has no PO.
  - Non-PO invoices follow the documented path: vendor, duplicate, arithmetic and tax checks, then requester approval.
  - When an invoice references a PO, the invoice vendor equals the PO vendor unless labelled.
  - No non-PO invoice is labelled missing receipt, price variance or quantity mismatch.
- Verify: REV-IC counts and a label cross-tab for invoices where po_id is null.

### A-18 · Totals are calculated from lines
Stage 2 (engine side: 4) · REQ · Plan R9f
- Source: A Workflow 3: "calculate line totals, tax and grand total from lines"
- Done when:
  - Line amount = qty × unit price; line tax = round(net × rate).
  - Subtotal = Σ line amounts. Tax total and grand total follow the documented rounding rule (Decimal, 0.01,
    ROUND_HALF_UP).
  - Printed (as-issued) header amounts are stored separately from computed ones.
  - For every unlabelled invoice, printed = computed exactly.
  - PO totals are also derived from the PO lines.
- Verify: REV-IC recomputes every invoice and PO in Decimal. Expect 0 unexpected mismatches. The mismatches must be
  exactly the labelled total and tax defects.

### A-19 · Tolerance policy in a versioned config file
Stage 1 (used in 4) · REQ for documented tolerances; versioning and rule ids are QI · Plan R9g (plus plan §4 St1)
- Source: A Workflow 3: "derive match status from price/quantity/tax tolerances"; A Acceptance: "three-way match and approval outcome agree with policy"
- Done when:
  - One versioned policy file (TOML or JSON) holds:
    - price, quantity, over-receipt, tax and rounding tolerances, with explicit boundary semantics (≤ or <);
    - the match-status precedence;
    - duplicate, vendor and date rules;
    - the routing matrix and the approval matrix;
    - the payment-readiness rules;
    - the policy version and its effective date.
  - business_rules.md justifies each value.
  - Engine and oracle read the values from the config. No magic numbers in code.
  - Every decision records the policy version and rule id.
- Verify:
  - Inspection.
  - Grep engine and oracle code for numeric literals that repeat tolerance values.
  - Policy-sensitivity probe (see A-04).

### A-20 · Approval and payment records only for eligible invoices
Stage 4 · REQ · Plan R9h
- Source: A Workflow 3: "create approval/payment records only for eligible invoices"
- Done when:
  - Eligibility rules for approval and for payment are documented (see AMB-13).
  - 0 Approval rows exist for invoices that are not approval-eligible: duplicates, closed vendor, open blocking
    exceptions not routed to an approver.
  - 0 Payment rows exist for invoices missing a required approval level or having an open blocking exception.
  - Approval levels follow the approval matrix (amount bands → levels → roles).
- Verify:
  - REV-IC joins Approval and Payment with exceptions, vendor history, duplicate pairs and the approval matrix.
    Expect 0 violations.
  - A pytest invariant exists.

### A-21 · State changes are append-only events
Stage 2 (generator history) and 4 (engine events) · REQ · Plan R10, R16
- Source: A Workflow 4: "Persist state changes as explicit records/events where relevant; do not overwrite history."; A Entities: "retain event history for state changes"
- Done when:
  - Event tables cover vendor status (effective-dated) and the PO, GRN, invoice, exception, approval and payment
    lifecycles.
  - Each event has an event id, entity id, from-status, to-status, timestamp, actor role and id, and a reason or rule
    id.
  - Events for each entity are strictly ordered.
  - Within a run, events are only appended: none is edited or deleted after it is written.
  - For 100% of records, the current status equals the last event's to-status.
  - Every transition is allowed by the documented state machine.
- Verify: REV-IC replays each entity's events against the state machines in schema.md and compares current statuses
  with the last event.

### A-22 · Outcomes and labels come from documented rules
Stage 2 · REQ · Plan R11
- Source: A Workflow 5: "Generate outcomes and ground-truth labels from documented rules, not independent random assignment."
- Done when:
  - Randomness only chooses which records get which injection, and how large it is.
  - A rule-based oracle then derives the labels and expected outcomes from the true data: match status, exceptions,
    routing, approval levels and outcome, payment readiness.
  - Generation fails loudly if the oracle's label differs from the injection intent.
  - Simulated approver decisions follow rules, not random draws.
  - Boundary cases get the label the rule gives, for example a variance exactly at tolerance.
- Verify:
  - Inspect the oracle: it makes no RNG calls.
  - Probe: tighten a tolerance in a scratch copy of the config and regenerate. Either the assertion fires or the labels
    change exactly as the rule predicts.

## 3. Entities and relationships

### A-23 · Nine core entities
Stage 4 (exports: 5) · REQ · Plan R12
- Source: A Entities: "Core entities: Vendor, PurchaseOrder, PurchaseOrderLine, GoodsReceipt, GoodsReceiptLine, Invoice, InvoiceLine, Approval, Payment."
- Done when:
  - All nine exist as tables, with documented names, in the CSV, JSON and SQL exports at both scales.
  - Approval and Payment are not empty.
- Verify: list the export files; list the SQLite tables through python sqlite3; REV-IC row counts > 0.

### A-24 · Primary and foreign keys
Stage 1 (spec) and 5 (DDL) · REQ · Plan R13
- Source: A Entities: "Define a primary key for every entity and foreign keys for every relationship."
- Done when:
  - schema.md and the machine-readable spec give the PK of every table, core and supporting.
  - Every relationship has an FK.
  - The SQL DDL declares PRIMARY KEY and FOREIGN KEY ... REFERENCES for each one.
  - The spec, the DDL and the ERD agree.
- Verify: REV-IC reads `PRAGMA foreign_key_list` for each table, compares it with the spec and the ERD, and recomputes
  PK uniqueness on all tables.

### A-25 · Cardinality, optional relationships, effective dates and lifecycle states are documented
Stage 1 (checked against the data again at 6) · REQ · Plan R14
- Source: A Entities: "Document cardinality (1:1, 1:N, N:M), optional relationships, effective dates and lifecycle states."
- Done when:
  - schema.md has a mermaid erDiagram.
  - A table gives cardinality and optionality for every relationship, e.g. Invoice→PO 0..1 and InvoiceLine→POLine
    0..1.
  - Effective dates are documented: vendor active window and status history, tax-code validity, policy version.
  - There is a state machine for each stateful entity: Vendor, PO, GRN, Invoice, Approval, Payment, Exception.
  - The observed data agrees with the documented cardinality.
- Verify:
  - Inspection.
  - REV-IC computes the observed maximum cardinality of each relationship. A documented 1:N must really be 1:N, and a
    documented 0..1 must contain nulls.

### A-26 · Bridge tables for N:M relationships
Stage 4 (spec 1) · REQ · Plan R15
- Source: A Entities: "Use bridge tables for many-to-many relationships"
- Done when:
  - Every N:M named in schema.md is a bridge table with its own PK and two FKs. At minimum this is the
    InvoiceLine ↔ GoodsReceiptLine allocation, and Payment ↔ Invoice if payments are batched.
  - The data shows N:M in both directions: at least one invoice line spans 2 or more GRN lines, and at least one GRN
    line serves 2 or more invoice lines.
  - Allocated quantities reconcile with invoice-line and GRN-line quantities.
- Verify: REV-IC counts both directions and sums the allocations.

### A-27 · All joins are validated
Stage 5 · REQ · Plan R17
- Source: A Entities: "validate all joins"
- Done when:
  - The validation suite takes its FK list from the machine-readable spec, not from a hand-picked subset.
  - It checks every relationship, including bridges, events, exceptions, approvals, payments, and ground truth →
    invoice.
  - It reports orphans per FK.
- Verify: set-compare the FKs in validation_summary with the DDL FK list (expect equality); REV-IC runs its own orphan
  check.

### A-28 · Labelled anomalies, no collateral corruption
Stage 2 · REQ · Plan R18
- Source: A Entities: "For deliberate anomaly cases, keep an issue_type/ground_truth label rather than silently corrupting unrelated rows."
- Done when:
  - Ground truth records every injected change: issue type, edge case, target ids, field, and baseline value →
    injected value.
  - Every validation violation falls on a labelled row.
  - Every unlabelled row is what the baseline rules would produce.
- Verify:
  - REV-IC: the set of rows that break any rule is a subset of the labelled rows.
  - Inspect the code: injectors touch only their target rows.
  - If a baseline snapshot exists, diff it with the final data on unlabelled rows only. Expect no difference.

## 4. IDs and naming

### A-29 · Exact ID formats
Stage 2 (spec 1) · REQ · Plan R19
- Source: A ID conventions: `"Vendor VND-00001; PO PO-2026-000001; receipt GRN-2026-000001; invoice INV-<vendor-code>-2026-000001; invoice line INVL-<invoice-id>-01."`
- Done when:
  - Every ID in every file matches its pattern: `^VND-\d{5}$`, `^PO-2026-\d{6}$`, `^GRN-2026-\d{6}$`,
    `^INV-<vendor-code>-2026-\d{6}$` and `^INVL-<invoice_id>-\d{2}$`.
  - The embedded vendor code equals the invoice's own vendor reference.
  - Each INVL prefix equals its parent invoice_id.
  - Counters start at 1 and are zero-padded.
- Verify: REV-IC regex and embedding checks over the CSV, JSON, SQL, inbox, manifest and ground-truth files.

### A-30 · Deterministic, immutable, consistent IDs
Stage 2 (exports: 5) · REQ · Plan R19, R22
- Source: A Step 3: "Keep counters zero-padded, IDs immutable, and referenced IDs exactly consistent across files."
- Done when:
  - The same seed and scale give the same ID sets.
  - No step renumbers or renames an ID after it is assigned. Injection adds records; it never shifts baseline counters.
  - Every referenced ID is byte-equal to its parent's ID in every file and format.
- Verify:
  - Two builds give identical ID lists.
  - REV-IC compares ID sets across CSV, JSON, SQL, inbox, ground truth and processed outputs.
  - Inspect the ID-allocation code.

### A-31 · Conventions for IDs the assignment does not specify
Stage 2 (spec 1) · QI · REV-added (DEV brief B covers it)
- Source: A Step 3: "Apply deterministic IDs and naming"
- Done when: PO line, GRN line, approval, payment, exception, event, document, user and SKU IDs follow a documented,
  analogous pattern, and are unique and regex-validated.
- Verify: REV-IC checks each table against the regex given in the dictionary.

### A-32 · Vendor invoice number kept apart from invoice_id; IDs carry no scenario
Stage 2 (spec 1) · REQ\* (a PK collision or a label-bearing ID is a BLOCKER) · REV-added (DEV brief B covers it)
- Source: A Edge cases: "Duplicate invoice number" and "same invoice submitted twice"
- Done when:
  - The vendor's printed invoice number is its own field.
  - Duplicates collide on (vendor, normalised number), never on a PK.
  - Each submission gets its own internal invoice_id.
  - No ID, file name, sender or note carries a scenario token (DUP, ANOM, VAR, TEST ...).
- Verify: REV-IC PK uniqueness; grep all inputs for scenario tokens.

## 5. Data dictionary, volumes, mix, seed, scale and edge cases

### A-33 · Data dictionary
Stage 1 (match with exports: 5) · REQ · Plan R20
- Source: A Step 1: "Write a data dictionary for: Vendor, PurchaseOrder, PurchaseOrderLine, GoodsReceipt, GoodsReceiptLine, Invoice, InvoiceLine, Approval, Payment. For each field specify type, required/optional, allowed values, units, uniqueness and validation rule."
- Done when:
  - A markdown dictionary and a machine-readable one cover all nine entities and every supporting table.
  - Every field has all six attributes, plus a description and a source/derived flag (per the plan).
  - Units are given for every money, quantity, rate and duration field (currency, UoM, %, days).
  - Natural keys are listed with their documented exceptions, e.g. vendor + invoice number is unique except for
    labelled duplicates.
  - For every table, the dictionary fields equal the exported columns, in both directions.
- Verify: REV-IC compares the dictionary with the CSV headers and DDL columns of each table (expect exact equality), and
  spot-checks 10 validation rules against the data.

### A-34 · Exact full-scale volumes
Stage 2 · REQ · Plan R23
- Source: A Step 4: "Generate 300 vendors, 1,500 POs, 2,200 PO lines, 1,800 receipts and 2,000 invoices."
- Done when:
  - In every export format, the full build has exactly: Vendor 300, PurchaseOrder 1,500, PurchaseOrderLine 2,200,
    GoodsReceipt 1,800, Invoice 2,000.
  - The 2,000 invoices include duplicates and non-PO invoices.
  - The committed full data has the same counts.
- Verify: REV-IC row counts on a fresh build and on the committed data.

### A-35 · Exact allocation algorithm and starter derivation
Stage 1 · REQ\* · REV-added (plan §4 St1 covers it)
- Source: A Step 4: "parameterize scale so starter and full datasets use the same generator"
- Done when:
  - data_generation.md gives an algorithm that hits the full counts exactly:
    - 1 to 8 lines per PO, summing to 2,200;
    - 1,800 GRNs spread over the received POs;
    - 2,000 invoices, including repeat invoicing, duplicates and non-PO invoices.
  - It also gives the starter rounding rule and mix tables with exact counts at both scales.
  - A script or test proves that the counts sum exactly.
- Verify: run DEV's proof script or test; REV re-adds the tables by hand.

### A-36 · Scenario mix
Stage 2 (allocation table: 1) · REQ · Plan R24
- Source: A Step 4: "Make ~70% clean matches, 10% price variance, 8% quantity mismatch, 5% duplicate invoices, 4% missing receipt and 3% tax/vendor errors."
- Done when:
  - The ground-truth primary categories at full scale are: price variance 200, quantity mismatch 160, duplicates 100,
    missing receipt 80, tax/vendor 60, clean 1,400.
  - Alternative: if the two uncategorised edge cases are carved out of clean, clean is at least 1,340 (67%) and the
    carved-out cases appear as their own rows.
  - The starter scale is proportional, using the documented rounding.
  - The reports publish a table of actual vs target.
- Verify: REV-IC counts categories from ground_truth and compares them with the reported table.

### A-37 · FKs valid except labelled defects
Stage 2 · REQ · Plan R25
- Source: A Step 4: "Keep every foreign key valid except deliberately labelled defect cases."
- Done when: the set of FK orphans equals the set of labelled FK defects exactly. Both may be empty.
- Verify: REV-IC compares the orphan set with the ground-truth set of FK defects.

### A-38 · Fixed seed, parameterised scale, one generator
Stage 2 · REQ · Plan R26, R27
- Source: A Step 4: "Use a fixed seed (e.g. 20261022) and parameterize scale so starter and full datasets use the same generator."
- Done when:
  - `--seed` defaults to 20261022.
  - `--scale` accepts starter or full (or a factor).
  - Scale changes only the allocation sizes, never the code path.
  - The manifest records the seed and scale.
- Verify: CLI `--help`; grep for scale-specific branches; inspect the manifest.

### A-39 · Valid baseline first, then all 8 labelled edge cases
Stage 2 (mapping: 1) · REQ · Plan R28
- Source: A Step 5: "Generate valid baseline records first, then inject labelled edge cases: Duplicate invoice number; invoice total differs from line sum; invoice date before PO date; partial delivery; closed vendor; tax mismatch; invoice exceeds PO quantity; same invoice submitted twice."
- Done when:
  - The generator has an explicit baseline phase, and the baseline validates with 0 violations before injection.
  - Each of the 8 edge cases has its own ground-truth tag.
  - Each appears at least 10 times at full scale and at least once at starter scale.
  - The mapping from edge cases to categories is documented (AMB-05).
  - Every labelled case really shows its defect, and no unlabelled record does (A-40 to A-47).
- Verify: inspect the phases in the code; REV-IC tag counts at both scales.

### A-40 · Edge case: duplicate invoice number
Stage 2 (detection: 4) · REQ · Plan R28a
- Source: A Edge cases: "Duplicate invoice number"
- Done when:
  - Each labelled case is a later invoice from the same vendor, with the same normalised vendor invoice number and
    different content (date, amount or lines).
  - Ground truth gives the pair: duplicate → original.
  - The engine holds the later invoice for the operations analyst. The original proceeds on its own merits.
- Verify: REV-IC finds every (vendor, normalised number) collision with differing content; this set must equal the
  labelled set. The engine's pairs must equal the ground-truth pairs.

### A-41 · Edge case: invoice total differs from line sum
Stage 2 (survives extraction: 3; detection: 4) · REQ · Plan R28b
- Source: A Edge cases: "invoice total differs from line sum"
- Done when:
  - Printed header total ≠ Σ line amounts + tax, for exactly the labelled set.
  - The printed value survives extraction unchanged.
  - The engine raises a blocking arithmetic exception and routes it to the operations analyst.
- Verify: REV-IC recomputes on the source and on the extracted data. The exception set must equal the labelled set.

### A-42 · Edge case: invoice date before PO date
Stage 2 (detection: 4) · REQ · Plan R28c
- Source: A Edge cases: "invoice date before PO date"
- Done when:
  - invoice_date < PO date for exactly the labelled set.
  - The engine raises the documented date-rule exception (after-the-fact PO) and routes it to the process owner. It is
    blocking or not as the policy says, and ground truth expects the same.
- Verify: REV-IC compares the date-comparison set, the labels and the engine's exceptions.

### A-43 · Edge case: partial delivery
Stage 2 (detection: 4) · REQ (clean variant: QI) · Plan R28d
- Source: A Edge cases: "partial delivery"
- Done when:
  - Labelled PO lines are received below the ordered quantity.
  - Negative variant (billed > received): a quantity exception routed to the business requester.
  - Clean variant (billed ≤ received): the invoice matches and proceeds.
- Verify: REV-IC compares cumulative received with billed for the labelled lines, and checks the engine status of
  each variant.

### A-44 · Edge case: closed vendor
Stage 2 (detection: 4) · REQ · Plan R28e
- Source: A Edge cases: "closed vendor"
- Done when:
  - For exactly the labelled invoices, the vendor status history shows CLOSED, effective on or before the invoice
    date.
  - No unlabelled PO is raised after a vendor's closure.
  - The engine blocks these invoices (no approval, no payment) and routes them to the documented role.
- Verify: REV-IC checks vendor status at the invoice date for every invoice against the labels. Approval and Payment
  rows for labelled invoices must be 0.

### A-45 · Edge case: tax mismatch
Stage 2 (detection: 4) · REQ · Plan R28f
- Source: A Edge cases: "tax mismatch"
- Done when:
  - For exactly the labelled set, either the invoice line's tax code differs from the PO line's, or the printed tax
    differs from round(net × rate(code, date)) by more than the documented tolerance.
  - Tax codes and rates sit in a reference table with validity dates.
  - The engine raises a tax exception, routed per the matrix.
- Verify: REV-IC recomputes in Decimal and checks set equality with the labels and the engine's exceptions.

### A-46 · Edge case: invoice exceeds PO quantity
Stage 2 (detection: 4) · REQ · Plan R28g
- Source: A Edge cases: "invoice exceeds PO quantity"
- Done when:
  - For exactly the labelled set, cumulative invoiced quantity on a PO line (in processing order, across invoices)
    exceeds ordered × (1 + tolerance).
  - This case is kept distinct from billed > received (A-43).
  - The engine flags it and routes it per the matrix.
- Verify: REV-IC computes cumulative quantities per PO line and checks set equality.

### A-47 · Edge case: same invoice submitted twice
Stage 2 (detection: 4) · REQ · Plan R28h
- Source: A Edge cases: "same invoice submitted twice"
- Done when:
  - Each labelled case is an exact resubmission: same vendor, number, date, amounts and lines after normalisation.
    It may arrive through a different channel, with formatting noise and a new internal invoice_id.
  - The engine rejects the later invoice as duplicate_of the original. The original is unaffected.
- Verify: REV-IC checks that the normalised content-hash pairs, the labelled pairs and the engine's pairs are the same.

### A-48 · Boundary and true-negative coverage
Stage 2 (engine agreement: 4) · REQ · Plan R35(e); the details are REV-added (DEV brief C covers them)
- Source: A Evaluation Focus: "(e) normal, boundary, failure and exception coverage"
- Done when:
  - The data contains these cases, each labelled by the rule:
    - price variance just inside, exactly at, and just outside tolerance;
    - quantity at the over-receipt limit;
    - tax differences of ±0.01;
    - legitimate recurring same-amount invoices from one vendor with different numbers (they must not be flagged);
    - the clean variant of partial delivery.
  - Each type appears at least 3 times at full scale.
  - The engine agrees with ground truth on all of them.
- Verify: REV-IC finds the cases by computing variance ratios and pair similarity, then compares labels with engine
  decisions.

### A-49 · Derived values come from source records
Stage 2 (engine-derived: 4) · REQ · Plan R29
- Source: A Step 6: "Calculate derived values (totals, balances, scores, statuses and dates) from source records rather than generating them independently."
- Done when:
  - The dictionary marks every derived field as derived and gives its formula.
  - Each of these recomputes exactly from its sources:
    - totals;
    - balances: received-to-date, invoiced-to-date, open quantity and amount per PO line;
    - scores: extraction confidence, duplicate similarity;
    - statuses: PO status from receipts and invoices, invoice status from events;
    - dates: due date from terms.
- Verify: REV-IC recomputes each derived field listed in the dictionary. Expect 0 unexpected mismatches.

### A-50 · Ground truth is separate and never leaks
Stage 2 (design 1; engine boundary 3–4) · REQ (any leak is a BLOCKER) · Plan R30; the leak vectors are REV-added
- Source: A Step 7: "Produce a separate ground_truth.csv/json for known anomalies, expected decisions or labels; never leak it into input features."
- Done when:
  - ground_truth.csv and ground_truth.json sit in their own folder.
  - They hold one row per invoice: primary category, edge-case tags, expected match status, exceptions, routing role,
    approval levels and outcome, payment readiness, duplicate_of, injected details.
  - No input table, manifest, file name, sender, document text or note carries labels or scenario tokens.
  - The engine does not use the vendor code embedded in invoice_id as its "extracted" vendor.
  - Ground truth is kept out of the SQL seed's input tables: a separate file, or a clearly separate schema that is
    never read.
  - The engine never opens `ground_truth/` or `source/`.
- Verify:
  - REV-IC scans the headers of all input files for label columns.
  - Grep the inputs for label vocabulary.
  - Blind run (A-10).
  - Inspect the vendor-resolution code.

## 6. Validation, exports, manifest and reproducibility (Steps 8 to 10)

### A-51 · Validation suite
Stage 5 · REQ · Plan R31; labelled reconciliation and the negative test are REV-added
- Source: A Step 8: "Run validation: primary-key uniqueness, foreign-key integrity, allowed enums, date ordering, arithmetic reconciliation, lifecycle transitions and duplicate checks."
- Done when:
  - All seven check families run over every table at both scales.
  - validation_summary.json and validation_summary.md give, per check and table: violations, expected (labelled)
    violations and status.
  - Unexpected violations = 0, and the expected violations reconcile 1:1 with ground truth.
  - Lifecycle checks replay the event logs against the state machines.
  - Duplicate checks cover unintended duplicate rows and natural keys as well as the labelled invoice duplicates.
- Verify:
  - Run the validation.
  - Corruption probe on a scratch copy of the data: duplicate a PK, orphan an FK, insert a bad enum, swap two dates,
    alter a total, add an illegal transition, add an unlabelled duplicate. Each one must be caught.

### A-52 · Exports: CSV, JSON and SQL seed
Stage 5 · REQ (two of the three formats is a MINOR; CSV only is a MAJOR) · Plan R32
- Source: A Step 9: "Export CSV/JSON/SQL seed data plus README, schema/data dictionary, generator command, fixed seed, source manifest and validation summary."
- Done when:
  - Both scales have CSV and JSON for every table and a SQL seed (DDL with PK/FK/CHECK plus INSERTs).
  - The SQL loads into SQLite with `PRAGMA foreign_keys=ON`, and `PRAGMA foreign_key_check` returns no rows.
  - Row counts agree across the three formats.
  - The companion items are present and linked: README, schema/dictionary, generator command, seed, manifest,
    validation summary.
- Verify: load the SQL with python sqlite3 in scratch; REV-IC compares counts across formats.

### A-53 · Source manifest
Stage 5 · REQ · Plan R32, R36
- Source: A Step 9: "source manifest"
- Done when:
  - source_manifest.json records the generator version, exact command, seed, scale and policy version.
  - It lists every file with its row count and SHA-256.
  - It records provenance: 100% synthetic, external data none or fully recorded, licences.
  - The checksums match the files on disk.
  - Nothing time-varying sits inside checksummed content.
- Verify: REV-IC recomputes SHA-256 and row counts for every listed file and checks for unlisted output files.

### A-54 · Reproducibility
Stage 5 · REQ · Plan R33; committed-data parity and the hash-seed probe are REV-added
- Source: A Step 10: "Regenerate twice with the same seed and compare row counts/checksums to demonstrate reproducibility."
- Done when:
  - A command regenerates twice with the same seed into separate directories, and reports identical row counts and
    checksums for every file.
  - A different seed gives different output.
  - The report is saved, and a test covers the command.
  - The committed data equals a fresh regeneration.
  - Results do not depend on PYTHONHASHSEED.
- Verify: REV runs two builds itself, one with PYTHONHASHSEED=1 and one with PYTHONHASHSEED=2, and compares SHA-256
  with its own script. It also compares the committed data with a fresh build.

## 7. Per-invoice acceptance criteria (A: Validation Rules / Acceptance Criteria)

### A-55 · Extracted fields match the source
Stage 3 · REQ · Plan R34a
- Source: A Acceptance: "For each invoice: extracted fields match source"
- Done when:
  - For every invoice, every field equals the invoice as issued, after documented normalisation:
    - header: vendor identity, vendor invoice number, invoice date, PO reference, currency, subtotal, tax, grand total,
      and terms if printed;
    - lines: line number, SKU, quantity, UoM, unit price, tax code, line amount.
  - Accuracy is reported by field, document and channel, with a list of mismatches.
  - Every mismatch is caught by confidence or validation and routed. Zero silent errors.
- Verify: REV-IC compares the extracted output with `source/`, independently of DEV's evaluator, and counts silent
  mismatches. Expect 0.

### A-56 · Line arithmetic and tax reconcile
Stage 4 · REQ · Plan R34b
- Source: A Acceptance: "line arithmetic and tax reconcile"
- Done when:
  - For every invoice, the engine recomputes lines, tax and totals from the extracted data.
  - The invoices that do not reconcile are exactly the labelled arithmetic and tax defects, and each one is flagged.
- Verify: REV-IC recomputes on the extracted data. Three sets must be equal: REV's recompute, the engine's flags and
  ground truth.

### A-57 · Duplicate detection flags the correct pair
Stage 4 · REQ · Plan R34c; direction and true negatives are REV-added
- Source: A Acceptance: "duplicate detection flags the correct pair"
- Done when:
  - The engine outputs directed pairs: later → earlier original.
  - The pair set equals the ground-truth pair set: precision = recall = 1.0, or each deviation is explained.
  - Originals are not blocked as duplicates.
  - Legitimate recurring invoices are not flagged.
- Verify: REV-IC compares the pair sets, checks the originals' statuses, and checks the true-negative set.

### A-58 · Three-way match and approval outcome agree with policy
Stage 4 · REQ · Plan R34d
- Source: A Acceptance: "three-way match and approval outcome agree with policy"
- Done when:
  - For every invoice, the engine's match status, exception set, approval levels and approval outcome equal the
    values ground truth expects: 100%, or each deviation is explained.
  - REV's hand-check of one invoice per category against business_rules.md agrees.
- Verify: REV-IC compares invoice by invoice; manual policy walk-through of at least 8 invoices (one per category plus
  boundary cases).

### A-59 · No blocked invoice is marked payment-ready
Stage 4 · REQ · Plan R34e
- Source: A Acceptance: "no blocked invoice is marked payment-ready."
- Done when:
  - 0 blocked invoices are payment_ready or have a Payment row. Blocked means an open blocking exception, a duplicate,
    a closed vendor or a missing approval level.
  - A pytest invariant enforces this at both scales.
- Verify: REV-IC runs the invariant query over the full data; run the test.

### A-60 · Per-invoice acceptance report
Stage 4 · REQ\* · REV-added (plan §4 St4 DoD covers it)
- Source: A Acceptance: "For each invoice:"
- Done when:
  - An automatic check evaluates the five criteria for every invoice.
  - It writes a per-invoice result table (invoice_id × 5 criteria, pass/fail with a reason) plus an aggregate.
  - Every invoice passes, or each failure is explained in the docs.
- Verify: REV-IC checks that the row count equals the invoice count, and spot-checks 10 rows against REV's own
  results.

## 8. Evaluation focus and lawful provenance

### A-61 · Realistic distributions and variation
Stage 2 (summary report: 5) · REQ · Plan R35(a)
- Source: A Evaluation Focus: "(a) realistic distributions and meaningful variation"
- Done when:
  - A distribution summary shows documented skew and variation:
    - vendor activity concentration (Pareto-like);
    - lognormal line values by SKU category;
    - mostly-weekday dates;
    - lead times by category;
    - the mixes of payment terms, channels and approval bands;
    - a histogram of lines per PO.
  - Injected scenarios are spread across the timeline and ID range, not clustered at the end. The exception is where
    the scenario requires it: resubmissions arrive later.
- Verify: REV-IC computes the top-20% vendor share, the weekday share, amount quantiles and the decile positions of
  scenarios.

### A-62 · Evaluation focus (a)–(g) mapped to evidence
Stage 1 (plan) and 6 (actual numbers) · REQ · Plan R35
- Source: A Evaluation Focus: "Review: (a) realistic distributions and meaningful variation; (b) consistent IDs and valid joins; (c) dependency/lifecycle consistency across entities; (d) correct derived values and reconciliation; (e) normal, boundary, failure and exception coverage; (f) separate ground truth; (g) fixed-seed reproducibility, documentation and lawful provenance."
- Done when: evaluation_plan.md (Stage 1) and the final evaluation doc (Stage 6) map each of (a)–(g) to a metric, check
  or file. At Stage 6 the doc gives actual numbers.
- Verify: inspection; the numbers must match REV-IC.

### A-63 · Dependency and lifecycle consistency across entities
Stage 2 (engine side: 4) · REQ · Plan R35(c)
- Source: A Evaluation Focus: "(c) dependency/lifecycle consistency across entities"
- Done when, unless labelled:
  - Each vendor's active window contains its PO dates.
  - PO date ≤ GRN date and PO date ≤ invoice date.
  - invoice date ≤ received date ≤ engine events ≤ approval dates ≤ payment date.
  - due date = base date + terms.
  - Nothing is completed after the fixed as-of date.
  - Each PO's status is consistent with its receipts and invoices.
  - Closed vendors get no new POs.
- Verify: REV-IC checks date order and status consistency across all tables.

### A-64 · Lawful provenance and safe synthetic data
Stage 5 (manifest) and 6 (docs) · REQ · Plan R36, G11
- Source: A Public Data Guidance: "External data is optional. If used, record source URL, dataset/version, retrieval date, license/terms, attribution, transformations and fields discarded." and "do not bypass access controls or collect confidential/personal information."
- Done when:
  - The manifest and README state provenance: 100% synthetic, or a full record for each external source with all
    seven attributes.
  - Vendor names, contacts, emails, tax ids and bank details are obviously synthetic (e.g. example.com or .test domains,
    no realistic valid account numbers).
  - There is no real personal data.
- Verify: inspection; REV-IC regex scan of vendor data for real-looking emails, phone numbers and IBAN-like strings.

## 9. Engineering quality (REV-added, for domain and correctness reasons)

### A-65 · Money is Decimal with a documented rounding rule
Stage 2 · REQ\* (a reconciliation error caused by float is a BLOCKER; otherwise a MINOR) · REV-added (plan §6)
- Source: A Acceptance: "line arithmetic and tax reconcile"
- Done when:
  - All money is Decimal, quantised to 0.01 with ROUND_HALF_UP.
  - No float appears in money paths.
  - The tax rounding level (line or header) is documented, and oracle and engine apply it the same way.
- Verify: grep money modules for `float(`; REV-IC Decimal recompute (A-18).

### A-66 · Determinism hygiene
Stage 2 (checked again at 5) · REQ\* · REV-added (plan §6)
- Source: A Step 4: "Use a fixed seed (e.g. 20261022)"; Step 10 reproducibility
- Done when:
  - src never reads the wall clock (datetime.now/today, time.time, date.today).
  - Every RNG is derived from the master seed; there is no module-level `random`.
  - Iteration is sorted wherever outputs are written.
  - CSV, JSON and SQL formatting is stable.
  - A fixed as-of date defines "current" status.
- Verify: grep src for clock calls and bare `random.` calls; the hash-seed probe in A-54.

### A-67 · Cumulative quantities and processing-time semantics
Stage 4 (spec 1) · REQ\* · REV-added (plan §4 St4 covers part of it)
- Source: A Edge cases: "invoice exceeds PO quantity"; A Workflow 3: "full/partial/over-receipt quantities"
- Done when:
  - Matching uses cumulative invoiced and received quantities per PO line, in the documented processing order.
  - Over-receipt is capped by the tolerance.
  - Receipts posted after the invoice are handled by one documented semantics (event-time replay or batch as-of
    date), used the same way by oracle and engine.
- Verify: REV-IC recomputes every PO line that has 2 or more invoices or 2 or more receipts.

### A-68 · Code quality and portability
Stage 6 (ongoing) · QI · REV-added (plan §6)
- Source: B-01: "Submit working, executable code."; B: "clear communication"
- Done when:
  - Module boundaries are clear and follow architecture.md.
  - Every command has CLI `--help`.
  - Errors are actionable.
  - There are no hard-coded absolute paths.
  - Code uses pathlib, UTF-8 and `newline=''`.
  - There is no dead code, and public functions have docstrings.
- Verify: inspection; run the CLI help; grep for `/home/` and `C:\\`.

### A-69 · Role queue CLI and offline dashboard
Stage 5 · QI (missing is a MINOR) · Plan §4 St5 only; this goes beyond the assignment
- Source: A Objective: "expose key decisions and exceptions" (this supports the item but does not require it)
- Done when:
  - A CLI shows each of the five roles its queue.
  - A self-contained offline HTML page (no CDN, no network) shows KPIs, queues, decision traces, evaluation and
    validation.
  - The page is generated deterministically.
- Verify: open the HTML from file:// with the network off; grep it for http(s) script or link tags.

## 10. Submission, guidelines and FAQ

### A-70 · README explains how to run it
Stage 6 (stub: 1) · REQ · Plan R37, G1
- Source: A Before you submit: "Added a README explaining how to run it"; B-01: "Include clear steps so another person can install dependencies, configure the project, run it, and verify key behavior."
- Done when the README covers:
  - overview and architecture;
  - quickstart for Windows PowerShell and for macOS/Linux;
  - install, configure (policy, seed, scale), run, and verify (tests and reports);
  - a map of outputs;
  - a results snapshot whose numbers equal the generated reports;
  - assumptions, limitations and next steps;
  - a pointer to the AI disclosure.
- Verify: REV follows the README commands verbatim on Linux in a fresh clone (A-71); REV-IC diffs the README numbers
  against the reports.

### A-71 · Fresh-clone run, environment and runtime
Stage 6 · REQ · Plan G1, G7, G8
- Source: C-8: "Use only free or locally runnable services, and avoid unusually large or slow dependencies where possible."; C-9: "Provide clear setup/run instructions and demonstrate how you verified the core functionality. Document environment needs and limitations."
- Done when:
  - `git clone` into an empty scratch directory, then the README steps (venv, install, build, test), all succeed.
  - The only network use is pip installing pytest, and no API key is needed.
  - The Python version is stated.
  - The runtime uses only the standard library (pytest is used only for tests).
  - The full build time is measured and documented.
- Verify: REV does a fresh clone, times the full build, and checks the dependency files.

### A-72 · Tests the problem asks for
Stage 6 (built up from Stage 2) · REQ · Plan R37
- Source: A Before you submit: "Included any tests the problem asks for"
- Done when:
  - `python -m pytest -q` passes on a fresh clone in about a minute or less.
  - The tests cover:
    - the Step 8 validation families;
    - Step 10 reproducibility;
    - the five per-invoice criteria;
    - ID formats, volumes and mix;
    - each edge case;
    - the engine boundary.
  - The tests include negative cases (corrupted inputs must fail).
  - The tests assert against independent expectations, never against values copied from the code under test.
  - A documented command runs the full-scale checks.
- Verify:
  - Run pytest with timing.
  - Read the tests for negative cases.
  - Mutation probe on a scratch copy: break one rule, and at least one test must fail.

### A-73 · Public dedicated repo, meaningful history, hygiene
Stage 6 (commits at each stage) · REQ · Plan G2, R37
- Source: B-02: "Use a public GitHub repository. Make the evolution of your work understandable through the code, meaningful commits, and supporting context."; C-3: "Create a new, dedicated public GitHub repository."
- Done when:
  - The history shows stage and fix commits with descriptive messages and the required trailers. There is no single
    dump commit.
  - .gitignore excludes caches, venvs and scratch.
  - .gitattributes forces LF.
  - The repo size is reported and reasonable.
  - Pushing to GitHub is a candidate action, listed in A-81.
- Verify: `git log --oneline --stat | head`; `git count-objects -vH`; inspect .gitattributes.

### A-74 · Complete prompt history
Stage 6 · REQ · Plan G3, G6
- Source: B-03: "Submit your prompt history"; C-6: "Include all prompts submitted to every AI tool you used. AI responses are optional. If a tool cannot export prompts, keep a reasonable record and disclose the limitation."; C-4: "Include your code, prompt history, and relevant supporting artifacts in a clearly identifiable directory."
- Done when:
  - A clearly named directory (e.g. `ai_disclosure/prompt_history/`) holds every prompt, verbatim and in order, with
    an index and timestamps. That means:
    - the candidate's prompts to the main session;
    - every orchestrator → DEV/REV message and brief;
    - every review request and fix request.
  - Limitations are disclosed: agent-internal tool calls, the transcription of the PDFs, and the fact that prompts the
    candidate sent to any other AI tool must be added by the candidate.
- Verify: compare the index entries with the files and with the sprint's prompt log; spot-check 3 prompts as verbatim.

### A-75 · Honest AI-usage disclosure
Stage 6 · REQ (a fabricated human claim is a BLOCKER) · Plan G3
- Source: B-03: "explain where AI accelerated your work, where you relied heavily on it, and what you personally reviewed, changed, or validated."; B: "We value sound judgment, working software, honest AI disclosure, and clear communication."
- Done when:
  - AI_USAGE.md says plainly that AI agents built and reviewed the solution under the candidate's direction.
  - It says where AI accelerated the work, where it was relied on heavily, and how results were validated (tests, REV
    gates).
  - The candidate's personal statement is a clearly marked placeholder.
  - No file claims human authorship or review that did not happen.
- Verify: read AI_USAGE.md; grep the docs and README for first-person claims ("I wrote", "I personally", "I
  reviewed").

### A-76 · Reasoning visible
Stage 1 (ADRs) and 6 (final) · REQ · Plan G4
- Source: B-04: "Help reviewers understand the problem, assumptions, key decisions, trade-offs, testing approach, limitations, and how you know the solution works."
- Done when:
  - Each of the seven topics has a findable section with specific content.
  - Every ambiguity in this file's AMB list has an ADR: decision, alternatives, trade-off.
- Verify: inspection; cross-check the ADR list against AMB-01 to AMB-33.

### A-77 · Walkthrough guide
Stage 6 · REQ\* (missing is a MINOR) · Plan G5
- Source: B: "BE READY TO WALK US THROUGH YOUR SOLUTION."; C-7: "Understand the core logic, key design choices, dependencies, and limitations."
- Done when: a short guide gives a 10 to 15 minute demo path:
  - the architecture;
  - one invoice per category, traced end to end;
  - where metrics and validation live;
  - likely questions, with answers.
- Verify: REV follows the guide's commands and checks that every referenced file exists.

### A-78 · Assumptions, deviations and what is incomplete
Stage 6 (ADRs: 1) · REQ · Plan G10
- Source: C-11: "Make reasonable assumptions and explain them. Partial solutions are acceptable if you state what works, what remains incomplete, known limitations, and next steps. Explain any requirement deviations."
- Done when:
  - A deviations list names every place where the build differs from a literal reading, with the reason. Examples: the
    68% clean carve-out, the vendor-code choice.
  - Limitations and next steps are concrete.
- Verify: inspect it against the deviations REV has recorded in its reviews.

### A-79 · No secrets, personal data or proprietary code; licences respected; no imported solution
Stage 6 (checked at every stage) · REQ · Plan G9, G11
- Source: C-12: "Never include secrets, credentials, personal or sensitive information, or proprietary code you are not authorized to publish."; C-10: "Do not import a complete solution or existing code that performs the core project work. Follow licenses and provide attribution where required."
- Done when:
  - A scan of the whole repo, `ai_disclosure/` included, finds no keys, tokens, passwords, private keys, or personal
    emails or phone numbers.
  - Dependencies and any snippets are attributed.
  - A LICENSE is present, and the candidate confirms MIT.
- Verify: `grep -rEn` for key, token, password, `BEGIN .*PRIVATE KEY`, `@gmail.com` and phone patterns; inspect the
  dependency list.

### A-80 · Timeline integrity
Stage 6 · REQ (owned by the candidate) · REV-added
- Source: B: "Your submission window is 72 hours. Artifact timestamps will be used to verify the window."; C-1: "Your deadline is exactly 72 hours later, using the recorded send timestamp and its time zone."; C-2: "Keep your public repository available and editable until the 72-hour deadline; the latest version at the deadline is evaluated."
- Done when:
  - Commit author and committer dates are genuine and monotonic: no `--date` overrides, no rewritten history.
  - All commits fall inside the window that starts at the YottaFlex send time. The candidate confirms that time; the
    sprint log starts at 2026-10-29 18:44 IST.
  - The hand-off states the deadline.
- Verify: `git log --format='%h %ad %cd'`; compare with the prompt index.

### A-81 · Candidate hand-off list
Stage 6 · QI · REV-added
- Source: A Before you submit: "Pushed your code to a public GitHub repository"; C-3: "Send the link from the same email address you used during recruitment and follow the submission instructions provided."
- Done when: the final hand-off lists the actions only the candidate can take:
  - create and push the dedicated public repo;
  - fill in the personal statement in AI_USAGE;
  - add prompts from any other AI tools used;
  - confirm the deadline;
  - send the link from the recruitment email;
  - rehearse the walkthrough.
- Verify: inspect the hand-off note or README section.

### A-82 · Requirements traceability with evidence
Stage 1 (planned) and 6 (evidence) · REQ\* (missing at Stage 6 is a MAJOR: it is the evidence for "every point") ·
REV-added extension (plan §4 St1/St6)
- Source: A Problem statement: "Read it carefully. Your build should cover every point below."
- Done when:
  - requirements_traceability.md maps every R-/G- id, and every A-item in this checklist, to an implementation location
    and to evidence (a test, report or file) with working relative links.
  - At Stage 6, every row has real evidence.
- Verify: REV-IC checks that all links resolve; spot-check 10 rows.

---------------------------------------------------------------------------------------------------

## B. Ambiguities: interpretations REV will accept or reject

ADRs in `docs/assumptions_and_decisions.md` should resolve each of these (A-76). "Preferred" marks REV's first choice.
Any accepted option passes if it is documented and applied consistently.

**AMB-01: What `<vendor-code>` means in `INV-<vendor-code>-2026-000001`, and the counter's scope.**
- Accept:
  - Preferred: vendor_id verbatim, giving `INV-VND-00001-2026-000001`, with the embedded code checked against the
    vendor FK.
  - A separate, unique, immutable `vendor_code` attribute on Vendor with a documented format, also checked.
  - Counter: preferred, one global 6-digit sequence in intake order. A per-vendor sequence is also acceptable if it is
    documented and the IDs stay unique.
- Reject:
  - the vendor name, or any other mutable or non-unique text;
  - the vendor's printed invoice number used as the counter;
  - suffixes that mark scenarios (`-DUP`, `-R2`);
  - unpadded counters;
  - an embedded code that disagrees with the FK;
  - the engine taking the embedded code as its extracted vendor (see AMB-24).

**AMB-02: How `INVL-<invoice-id>-01` expands.**
- Accept:
  - Preferred: the full invoice_id embedded, giving `INVL-INV-VND-00001-2026-000001-01`, with a 2-digit per-invoice
    sequence that starts at 01 and has no gaps.
  - A shortened invoice reference, only through an ADR, with a lossless and validated mapping. That is a MINOR
    deviation.
- Reject: a global line counter; line IDs that do not embed their parent's ID exactly.

**AMB-03: The "2026" segment of the IDs.**
- Accept: a constant 2026 with every document dated inside a documented 2026 window that ends at the fixed as-of date.
  The year may also be derived from the document date, provided all dates fall in 2026.
- Reject: a year segment that contradicts the record's own date with no fiscal-year note; completed events dated after
  the as-of date.

**AMB-04: What the volume numbers count.**
- Accept:
  - receipts = GoodsReceipt headers (1,800);
  - invoices = all Invoice records, including duplicates and non-PO invoices (2,000);
  - PO lines = the total across all POs (2,200);
  - GRN lines, invoice lines, approvals, payments and events are unconstrained but reported.
- Reject: 1,800 GRN lines in place of headers; 2,000 "unique" invoices with duplicates added on top; approximate
  counts at full scale.

**AMB-05: How the eight edge cases relate to the 70/10/8/5/4/3 mix.**
- Denominator: invoices (2,000). The "~" applies to the mix. At full scale REV expects 1,400/200/160/100/80/60, or a
  documented carve-out.
- Natural family mapping:

  | Edge case | Natural family | Expected handling |
  |---|---|---|
  | Duplicate invoice number | Duplicates 5% | number reused with different content → hold |
  | Same invoice submitted twice | Duplicates 5% | exact resubmission → reject |
  | Invoice exceeds PO quantity | Quantity mismatch 8% | cumulative invoiced exceeds the PO, beyond tolerance |
  | Partial delivery | Quantity mismatch 8% (billed > received) and clean (billed ≤ received) | both variants |
  | Tax mismatch | Tax/vendor 3% | wrong code or wrong amount |
  | Closed vendor | Tax/vendor 3% | vendor closed by the invoice date |
  | Invoice total differs from line sum | no named family | family choice or carve-out |
  | Invoice date before PO date | no named family | family choice or carve-out |

  Price variance (10%) and missing receipt (4%) are categories with no named edge case. They must still appear at
  their shares.
- Accept any of these:
  1. The two unfamilied cases go into documented families (e.g. "vendor/document errors" inside the 3%), and the six
     counts stay exact.
  2. About 1% each is carved out of clean (clean ≈ 68%, still "~70%"), and the carve-outs are reported as their own
     rows.
  3. Multi-label ground truth: the primary category drives the mix, and secondary edge-case tags may overlay it.
     Metrics are given per primary category and per tag.
  - Boundary cases within tolerance and the clean variant of partial delivery count as clean.
  - Duplicates: the 5% are the later duplicate records. Each points to an original, which is counted in its own
    category.
- Reject:
  - any edge case missing at either scale;
  - edge cases that exist only in a side dataset;
  - clean below 67%, or any exception category more than 1 percentage point off at full scale;
  - labels that do not name the edge case;
  - co-occurring injected defects with no precedence rule;
  - both members of a pair labelled or blocked as duplicates.

**AMB-06: "Duplicate invoice number" vs "same invoice submitted twice".**
- Accept:
  - Number reuse: same vendor and same normalised number, but different content (date, amount or lines). The later
    invoice is held for the operations analyst.
  - Exact resubmission: same vendor, number, date, amounts and lines. It may come through another channel, carry
    formatting noise and get a new internal ID. The later invoice is rejected.
  - Both output the directed pair.
  - A third, fuzzy variant (same content, slightly altered number) is accepted if documented.
- Reject: one shared label for both; detection by internal ID only; detecting only one of the two; blocking the
  original.

**AMB-07: Partial delivery.**
- Accept:
  - Receipts for a PO line sum to less than the ordered quantity.
  - Billed ≤ received: clean, matched on the received quantity.
  - Billed > received: a quantity exception routed to the business requester.
  - Minimum: the negative variant is present and labelled. The clean variant is QI.
- Reject: partial delivery that exists only as a GRN pattern with no consequence for the invoice; partial delivery
  counted as missing receipt.

**AMB-08: "Invoice exceeds PO quantity" vs billed > received vs over-receipt.**
- Accept:
  - Exceeds PO quantity: cumulative invoiced quantity on a PO line, across invoices in processing order, exceeds
    ordered × (1 + tolerance). It is routed to the process owner.
  - Billed > received: a receipt-side issue, routed to the requester.
  - Over-receipt within tolerance is normal. Beyond tolerance, it is flagged on the GRN side, and matching caps the
    quantity at min(received, ordered × (1 + tolerance)).
- Reject: a single-invoice check that misses cumulative overruns; treating over-receipt as justifying over-billing
  beyond tolerance.

**AMB-09: Closed vendor.**
- Accept:
  - The vendor's effective-dated status history shows CLOSED or INACTIVE on or before the invoice date.
  - The invoice is blocked (no approval, no payment) and routed to the system administrator (vendor master) or the
    process owner.
  - Earlier POs predate the closure. A PO raised to an already-closed vendor is a separate labelled defect, if it is
    modelled.
- Reject: a status flag with no effective date; unlabelled new POs after closure; closed-vendor invoices with
  approvals or payments.

**AMB-10: Tax mismatch.**
- Accept: the line's tax code differs from the PO line's, or the printed tax differs from
  round_half_up(net × rate(code, date), 2) by more than ±0.01. Rates sit in a reference table with validity dates.
  Both variants are preferred.
- Reject: a header-only comparison with no line-level code check; an undocumented rounding tolerance; mismatches that
  arise accidentally from float error.

**AMB-11: What makes up the 3% "tax/vendor errors".**
- Accept: tax mismatch plus closed vendor. Optionally also: invoice vendor different from the PO vendor, or an unknown
  vendor reference (a labelled FK defect). Sub-counts are documented.
- Reject: an undocumented composition.

**AMB-12: Missing receipt, and "as of when" the match runs.**
- Accept:
  - Zero GRN quantity is posted for the invoiced PO line(s), as of either the invoice's processing time (event-time
    replay) or the fixed as-of date (batch).
  - One semantics is documented and used by both oracle and engine.
  - Late receipts are allowed if the semantics say how they are handled (e.g. a re-match event).
- Reject: undefined semantics; oracle and engine using different semantics; "missing receipt" on non-PO invoices.

**AMB-13: What "eligible" means for approvals and payments.**
- Accept, approval-eligible:
  - The invoice passed all blocking checks: matched, or within tolerance, or a non-PO invoice that passed the vendor,
    duplicate, arithmetic and tax checks.
  - Or the exception type's documented resolution is an approver decision, e.g. a price variance above tolerance but
    within an approval cap.
  - Approval records follow the approval matrix. Simulated decisions are deterministic rules. Outcomes are APPROVED,
    REJECTED or PENDING at the as-of date.
- Accept, payment-eligible: every required approval level APPROVED, no open blocking exception, vendor payable on the
  payment date, not a duplicate. The payment is scheduled per the terms, for the approved payable amount.
- Reject:
  - approvals for blocked, duplicate or closed-vendor invoices;
  - payments with only some levels approved;
  - random approval outcomes;
  - Payment rows that exist for blocked invoices but carry a "blocked" flag. Those rows must not exist at all.

**AMB-14: What "extracted fields match source" requires.**
- Accept:
  - "Source" is the invoice as issued by the vendor: the generator's true document data, deliberately wrong printed
    values included.
  - Every header field and every line field (see A-55) equals the source after documented normalisation.
  - Results are given per invoice and per field.
  - Every mismatch is caught by confidence or validation and routed.
- Reject:
  - comparing against PO or ERP values (that is matching, not extraction);
  - an extractor that corrects printed values;
  - "extraction" that reads the canonical source table;
  - a header-only comparison;
  - a 100% claim with no negative test showing that mismatches would be caught.

**AMB-15: Tolerance values.**
- Accept: any documented, justified values (e.g. price ±2% or an absolute cap, quantity 0 or a small %, tax ±0.01),
  with explicit ≤/< semantics, kept in config and tested at the boundaries.
- Reject: magic numbers in code; undocumented boundary semantics.

**AMB-16: "Export CSV/JSON/SQL" and "ground_truth.csv/json".**
- Accept:
  - Target: CSV, JSON and SQL seed for all relational tables.
  - Ground truth as CSV and/or JSON (both preferred).
  - Two of the three export formats is partial (MINOR).
- Reject: CSV only (MAJOR); a SQL seed that fails to load with FKs enforced; ground truth inside the seed's input
  tables.

**AMB-17: Where the Approval and Payment records come from.**
- Accept: either option below, as long as ground truth holds the expected approvals and payments for comparison.
  - The engine produces them from the inbox, and they are exported as part of the relational dataset.
  - The generator produces "historical" approvals and payments, and the engine reproduces them.
- Reject: Approval or Payment missing from the exported data; records created without regard to eligibility; expected
  decisions copied from engine output.

**AMB-18: Starter scale.**
- Accept: a documented factor (e.g. 0.1, giving 30/150/220/180/200) on the same code path, with all 8 edge cases
  present at least once and the mix proportional by the documented rounding.
- Reject: a separate script, or hand-made starter data; a starter set missing edge cases.

**AMB-19: The seed.**
- Accept: default 20261022 (preferred) or another fixed, documented seed, overridable by CLI and recorded in the
  manifest.
- Reject: unseeded randomness anywhere; a seed taken from the clock.

**AMB-20: Representing the actors.**
- Accept: a role/user reference in which each of the five roles has real responsibilities in the data (see A-12),
  plus a documented RACI.
- Reject: actors listed only in the README; one generic "user" role.

**AMB-21: Which events and history are needed.**
- Accept: append-only events for the invoice, exception, approval and payment lifecycles, plus vendor status history
  and the PO/GRN lifecycle. Current status = the last event.
- Reject: current-status columns only; events with no actor or timestamp; history rewritten within a run.

**AMB-22: Which effective dates are needed.**
- Accept: the vendor active window and status history; tax-rate validity; the policy version's effective date. PO
  validity is optional.
- Reject: no effective dates documented.

**AMB-23: Which N:M relationships exist.**
- Accept, each with a bridge table and data that really is N:M:
  - InvoiceLine ↔ GoodsReceiptLine allocation: one line matched against several receipts, one receipt line consumed by
    several invoices.
  - Payment ↔ Invoice allocation: runs that pay many invoices, invoices paid in instalments.
- Reject: claiming no N:M exists; a bridge table whose data is effectively 1:1.

**AMB-24: What "never leak it into input features" covers in a rule-based system.**
- Accept: the engine's inputs are master data plus the inbox (documents and an intake manifest without labels). Ground
  truth and source invoices are for evaluation only. A test and the blind run (A-10) enforce this.
- Reject:
  - label columns in any input table;
  - scenario tokens in IDs, file names, senders, document text or notes;
  - engine code that reads `ground_truth/` or `source/`;
  - the engine taking its vendor from the vendor code inside invoice_id (the vendor must be resolved from the document
    or the authenticated sender, and cross-checked);
  - ground truth inside the main SQL seed's input tables.

**AMB-25: What "realistic distributions" means.**
- Accept: documented skew (see A-61) with a distribution summary.
- Reject: uniform random draws everywhere; anomalies clustered at the end of the timeline or ID range for no reason.

**AMB-26: "Included any tests the problem asks for" vs FAQ 9 ("No hosted demo or automated test suite is mandatory").**
- Accept:
  - Target: a pytest suite covering Step 8, Step 10 and the five per-invoice criteria, plus documented verification
    commands.
  - Scripted, reproducible checks with saved outputs are the floor. The plan keeps pytest, so REV holds DEV to pytest.
- Reject: manual-only claims of verification.

**AMB-27: "All prompts submitted to every AI tool" in an agent-orchestrated build.**
- Accept:
  - The candidate's prompts and every orchestrator → agent message and brief, verbatim, indexed and timestamped.
  - Responses are optional; reviews and reports are included as evidence.
  - Limitations are disclosed (see A-74).
- Reject: summaries in place of verbatim prompts; missing candidate prompts; missing relay messages.

**AMB-28: Non-PO invoices ("optionally PO").**
- Accept: a documented share (e.g. 3 to 10%) on the non-PO path. These invoices may carry duplicate, tax, vendor or
  arithmetic labels, but never price, quantity or missing-receipt labels.
- Reject: a schema without a nullable PO FK (MAJOR); no non-PO invoices and no reason given (MINOR).

**AMB-29: What happens to an invoice dated before its PO.**
- Accept: a date-rule exception (after-the-fact PO) routed to the process owner. It may be blocking or non-blocking per
  documented policy, as long as ground truth expects the same.
- Reject: silent acceptance; treating it as an extraction error.

**AMB-30: Which member of a duplicate pair is "the duplicate".**
- Accept: the later-received record (in intake order) is flagged as duplicate_of the earlier one. The pair is still
  reported if the earlier record is blocked for some other reason.
- Reject: flagging the original; undirected pairs; pairs that point to a record that does not exist or is not a
  duplicate.

**AMB-31: How far "validate all joins" and "duplicate checks" (Step 8) reach.**
- Accept: every FK in the machine-readable spec is checked, spec-driven (see A-27). Duplicate checks cover unintended
  duplicate rows and natural keys as well as labelled invoice duplicates reconciled with ground truth.
- Reject: a hand-picked subset of joins; duplicate checks on PKs only.

**AMB-32: "Units" and currency.**
- Accept: one documented currency, or several with explicit currency fields. A UoM on every quantity. Rates in % or
  as a decimal fraction, stated.
- Reject: money or quantity fields with no unit.

**AMB-33: What form "expose key decisions" and "measurable outputs" take.**
- Accept: a per-invoice decision trace (explain CLI or report) plus an exceptions table; metrics in JSON and Markdown
  with definitions.
- Reject: decisions visible only in log lines; qualitative claims with no numbers.

---------------------------------------------------------------------------------------------------

## C. Comparison with SPRINT_PLAN.md

**C.1 Coverage.** Every plan §5 id (R1 to R37, G1 to G11) maps to at least one A-item (see the Plan field). None was
dropped.

**C.2 REV-added items.**
- Already asked for in plan §4/§6 or the DEV brief, so DEV's targets are unchanged:
  - A-10 engine boundary and non-circular evaluation;
  - A-31 conventions for unspecified IDs;
  - A-32 vendor invoice number kept apart from invoice_id;
  - A-35 exact allocation proof;
  - A-60 per-invoice acceptance report;
  - A-65 Decimal money;
  - A-66 determinism hygiene;
  - A-68 code quality and portability.
- New with REV, which DEV should plan for:
  - A-80 timeline integrity and A-81 the candidate hand-off;
  - A-82: the traceability matrix also covers the A-items;
  - A-67: one processing-time semantics, shared by oracle and engine;
  - in A-50: no vendor shortcut through invoice_id, ground truth kept out of the SQL seed's input tables, and the blind
    run;
  - in A-54: committed data equals a fresh build, and results do not depend on PYTHONHASHSEED;
  - in A-36 and A-39: numeric mix tolerances and minimum edge-case counts (≥ 10 at full scale, ≥ 1 at starter);
  - in A-26: N:M exercised in both directions;
  - in A-61: scenarios spread across the timeline;
  - in A-03 and A-72: negative tests and mutation sensitivity;
  - in A-64: contact and bank fields that are obviously synthetic;
  - in A-74: relay messages and prompts sent to other tools.

**C.3 Plan items REV sees as over-reaching or needing a guard.**
- **P-1. Role queue CLI and offline HTML dashboard (plan §4 St5).** These go beyond the assignment, which asks to
  "expose key decisions and exceptions", not for a UI. REV treats them as QI (A-69), with MINOR as the maximum severity
  if missing. They should be scheduled after every REQ item. If built, they must work offline (no CDN), be
  deterministic and stay small.
- **P-2. "At least 3 heterogeneous formats" and "Target a 100% field match" (plan §4 St3, DEV brief G).**
  - Three formats is more than the minimum. It is QI; a shortfall is a MINOR as long as at least one non-trivial format
    exists.
  - When one author builds both the renderer and the parser, a 100% match is close to a tautology. It is credible only
    with negative or mutation tests (A-03, A-72). Preferably, a few genuinely degraded documents should also exercise
    the low-confidence route in the real data.
- **P-3. The intake manifest carries "invoice id" (plan §4 St3).** That ID embeds the vendor code, so the engine could
  skip vendor extraction. Guard: the engine resolves the vendor from the document content or sender and cross-checks it
  against the ID. Vendor extraction accuracy is computed from the extracted field, not from the ID (A-50, A-55).
- **P-4. A SQL seed "of the whole relational dataset" (DEV brief A).** Ground truth must not go into the seed's input
  tables. Ship it separately, or in a clearly separate schema the engine never reads, and record this in the manifest.
- **P-5. Committing the full generated datasets (DEV brief I).** This is fine, but committed data counts as evidence
  only if it equals a fresh build (A-54) and the repo size stays sensible. Otherwise, commit the starter data and the
  manifest only.
- **P-6. Carving clean down to about 68% (DEV brief C).** Acceptable under "~70%". REV prefers documented families that
  keep clean at 1,400. Either passes if reported (A-36).
- **P-7. Plan constraints that are not assignment rules.** R26 fixes the seed at 20261022, but the assignment says
  "e.g.": harmless, and REV will not treat another documented fixed seed as a defect. §6 "standard library only" is a
  plan constraint too; a small, justified dependency would be a MINOR at most.
- **P-8. Missing from plan §5.** The 72-hour / artifact-timestamp rule and the submission steps only the candidate can
  take (C-1 to C-3). Added as A-80 and A-81.
- **P-9. Stage order.** Step 8 validation sits in Stage 5, but Stage 2 data needs validation evidence too. DEV should
  ship at least baseline self-checks in Stage 2: PK, FK, enum and arithmetic checks, plus the oracle assertions. REV
  checks Stage 2 with its own checker either way.
- **P-10. MIT LICENSE (plan §4 St1).** Not required, and licensing is the candidate's decision. Keep it, but list it
  for the candidate to confirm (A-79, A-81).
- **P-11. Final DoD "REV PASS on all items".** REV reads this as: every REQ and REQ\* item is met with evidence; each QI
  item is met or closed as an accepted deviation with a written justification (SPRINT_PLAN §3 step 3).

## D. REV verification toolkit (applies to all stages)
- **REV-IC scripts** live in `/home/claude/sprint/reviews/scratch/`. They use only the standard library, read exported
  files and never import repo code. They cover:
  - counts, ID regexes and embeddings, FK orphan sets;
  - Decimal arithmetic;
  - mix, and edge-case conditions vs labels;
  - cardinality, date order, state-machine replay, distribution statistics;
  - extraction vs source, duplicate pairs, the payment-ready invariant, SHA-256.
- **Blind run.** Copy a build to scratch, delete `ground_truth/` and `source/`, rerun the engine, and diff the outputs.
- **Mutation and corruption probes.** These run only on scratch copies of the repo or the data, never on the repo
  itself.
- **Reproducibility.** Two builds with different PYTHONHASHSEED values, compared with REV's own SHA-256 check; then the
  committed data compared with a fresh build.
- **Fresh clone (Stage 6).** `git clone /home/claude/invoice-ap-automation <scratch>/clone`, then the README steps only.

## E. Stage gate map (the A-items each review checks)

| Stage | A-items |
|---|---|
| 1 (spec level) | 05, 10, 12, 17, 19, 21, 22, 24, 25, 26, 29, 31, 32, 33, 35, 36, 39 (incl. the mapping for 40–47), 48, 49, 50, 62, 65, 66, 67, 70 (stub), 73 (skeleton), 76, 79, 82 (planned) |
| 2 | 13–18, 21 (generator), 22, 28–32, 34, 36–50 (data side), 61, 63, 65, 66, 72 (generator tests) |
| 3 | 02, 03, 10 (boundary test), 41 (survives extraction), 50 (engine boundary), 55 |
| 4 | 01, 04–12, 20, 21 (engine), 23, 26, 40–48 (detection), 56–60, 63, 67 |
| 5 | 01 (one command), 23 (exports), 27, 33 (match with exports), 51–54, 61 (report), 64 (manifest), 69 |
| 6 | 62, 64, 68, 70–82, then a final re-check of every item, with evidence in FINAL_ACCEPTANCE.md |

## F. Findings tracker conventions (for FINDINGS_TRACKER.md)
- The file holds only this table, header exactly as specified:
  `ID | Stage | Severity | Requirement | Summary | Status (open/fixed/verified/accepted-deviation) | Notes`
- **ID** is `S<N>-R<K>-<nn>`, matching `stage-<N>-review-<K>.md`. **Severity** follows SPRINT_PLAN §3; the default for
  each item is set by its Class above. **Requirement** gives the A-item and/or R-/G- id, or the concrete correctness
  reason.
- **Status:**
  - `open`: raised by REV.
  - `fixed`: DEV claims a fix, with evidence in `stage-<N>-response-<K>.md`.
  - `verified`: REV re-checked the fix with its own evidence.
  - `accepted-deviation`: REV accepts DEV's written justification. Notes give the reason.
- Carry-forward items stay open until their owning stage. All must be closed by the final audit.

## G. Change log
- v1, 2026-10-29: initial version. Drafted independently, then merged with SPRINT_PLAN §5.
  FINDINGS_TRACKER.md could not be created by REV: the subagent harness blocks it as a "report file". The orchestrator
  creates it from the header above.
