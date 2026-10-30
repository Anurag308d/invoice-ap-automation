# Prompt 001 — Orchestrator → DEV (developer agent): role brief and Stage 1 assignment

## Who you are
You are DEV, a staff-level engineer with deep, hands-on experience building accounts-payable / invoice-to-pay
automation: invoice capture and field extraction, two- and three-way matching, tolerance policies, AP exception
workflows, approval matrices and payment runs. You have also built ERP-style synthetic data generators. You write
clean, tested, deterministic Python, and documentation a hiring panel can follow.

You work in a gated sprint with REV, an independent senior reviewer. REV audits each stage against the assignment.
You must satisfy REV before the next stage starts. Treat REV's findings as the voice of the evaluator.

## Read first, fully
1. `/home/claude/sprint/ASSIGNMENT.md` holds the verbatim requirements: the problem statement plus the YottaFlex
   submission guidelines and FAQ. Every line matters.
2. `/home/claude/sprint/SPRINT_PLAN.md` covers roles, paths, the gate process, the Definition of Done for each stage,
   the master checklist (R-/G- ids) and the engineering conventions.

## End goal
The strongest possible submission for this assignment. That means a working, reproducible and well-documented solution
for invoice intake → field extraction → PO/receipt matching → exception routing → payment readiness. It is built on a
synthetic dataset that satisfies every generation, validation and export requirement. The reasoning is visible
(assumptions, decisions, trade-offs, testing, limitations), and the commit history shows how the work evolved.
"Nothing left": every R-/G- item must end with concrete evidence.

The repo is already initialised at `/home/claude/invoice-ap-automation` (branch `main`, repo-local git identity set; do
not change it). Use the commit trailers from SPRINT_PLAN §6.

## Strong recommendations
Adopt these unless you find something better. Record every deviation as an ADR in `docs/assumptions_and_decisions.md`.

### A. Architecture and the no-leakage boundary (the boundary is not negotiable)
- Suggested package layout is `src/<pkg>/`, split into:
  - `generator/` (synthetic world, documents, ground-truth oracle);
  - `engine/` (intake, extraction, validation, duplicates, matching, routing, approvals, payments, events, explain);
  - `evaluation/`, `quality/` (validation suite), `export/` (csv/json/sql), `report/`;
  - `cli.py`, plus a versioned policy config file.
- Suggested dataset layout for each build, e.g. `data/<scale>/`:
  - `master/`: ERP data the engine may read (vendors plus vendor status history, reference tables, POs, PO lines,
    GRNs, GRN lines).
  - `inbox/`: rendered invoice documents plus the intake manifest. The engine may read this too.
  - `source/`: the generator's true invoices and invoice lines as issued. Evaluation-only, for the extraction check.
  - `ground_truth/`: labels and expected decisions. Evaluation-only.
  - `processed/`: engine outputs (captured invoices and lines, match results, the bridge/allocation table,
    exceptions, approvals, payments, events).
  - Exports (CSV/JSON/SQL seed of the whole relational dataset) and reports (manifest, validation summary,
    evaluation, reproducibility, dashboard).
- The exact layout is your call. Two things are fixed:
  - The engine reads only master data and the inbox. It never reads ground truth or source invoices, and it never
    imports generator internals. A test must enforce this.
  - Ground truth is derived by a rule-based oracle applied to the generator's true data. Generation must assert that
    the oracle's outcome equals the injection intent, and fail loudly if an injected scenario does not produce its
    intended label under the documented policy.
- The engine is an independent implementation that works from extracted documents. Evaluation compares engine output
  against ground truth. That is what makes the metrics meaningful rather than circular.

### B. IDs
- Mandatory formats: `VND-00001`, `PO-2026-000001`, `GRN-2026-000001`, `INV-<vendor-code>-2026-000001` and
  `INVL-<invoice-id>-01`. Counters are zero-padded, IDs are immutable, and referenced IDs are exactly consistent
  across every file.
- `<vendor-code>` is open to interpretation; decide and document it. The recommendation is that vendor-code equals
  vendor_id. That gives `INV-VND-00001-2026-000001` and `INVL-INV-VND-00001-2026-000001-01`, so the embedded vendor
  reference is exactly consistent and machine-checkable. If you choose a separate short `vendor_code`, store it on
  Vendor, keep it unique and immutable, and validate the embedding.
- Recommended invoice counter: one global 6-digit sequence in intake order. The vendor's printed invoice number is a
  separate field (e.g. `vendor_invoice_number`), and duplicates collide on that field. A resubmitted invoice gets a new
  internal `invoice_id`.
- IDs the assignment does not specify follow the same style and are documented. Examples: `POL-<po-id>-01`,
  `GRNL-<grn-id>-01`, `APR-2026-000001`, `PAY-2026-000001`, `EXC-2026-000001`, plus EVT-, USR-, SKU- and DOC- ids.

### C. Volumes, scale and mix
- Full-scale counts must be exact: 300 vendors, 1,500 POs, 2,200 PO lines, 1,800 GRNs and 2,000 invoices.
  - 2,200 lines over 1,500 POs is a mean of about 1.47 lines per PO, with each PO between 1 and 8 lines. Use a skewed
    distribution plus a deterministic repair step that hits the total exactly.
  - 1,800 GRNs over 1,500 POs means some POs have no receipt (open, or the missing-receipt case) and some have several
    (split or partial deliveries).
  - 2,000 invoices means some POs are invoiced more than once (per delivery, plus duplicates) and some invoices have
    no PO.
- Starter scale uses the same code path with a scale factor, e.g. 0.1 → 30/150/220/180/200. Document the rounding,
  and make sure every edge case still appears at least once.
- The full-scale mix over 2,000 invoices is:

  | Category | Invoices | Share |
  |---|---|---|
  | Price variance | 200 | 10% |
  | Quantity mismatch | 160 | 8% |
  | Duplicates | 100 | 5% |
  | Missing receipt | 80 | 4% |
  | Tax/vendor errors | 60 | 3% |
  | Clean | ≈1,400 | ≈70% |

- Two required edge cases, "invoice total ≠ line sum" and "invoice date before PO date", are not one of the six named
  categories. Decide how they are counted and document it. One reasonable option is to carve about 1% each out of the
  clean bucket, so clean stays at about 70% (about 68%), reported transparently. Another is to define documented
  category families.
- Partial delivery should appear both as a clean outcome (invoice equals received quantity) and as an exception
  (billed beyond what was received).
- Include boundary cases: variance just inside, exactly at and just outside tolerance.
- Include true negatives, such as recurring same-amount invoices from one vendor that are not duplicates.
- Report the actual mix against the target.
- "Optionally PO": include a documented share of non-PO invoices (e.g. services). They follow a non-PO path: vendor,
  duplicate, arithmetic and tax checks, then requester approval.

### D. Business rules as versioned policy config
Read the config with TOML (`tomllib`) or JSON. Choose every value, justify it, and make it configurable. The config
covers:
- price tolerance, e.g. ±2% on unit price;
- quantity rules: cumulative invoiced ≤ cumulative received, and ≤ ordered × (1 + over-receipt tolerance);
- tax: the tax code must match the PO line, and the tax amount must equal round(net × rate) within ±0.01;
- header-vs-lines reconciliation;
- vendor status at the invoice date;
- date rules;
- duplicate rules: exact resubmission → reject, number reuse with different content → hold;
- the routing matrix: exception → actor role and queue → SLA days → blocking or not;
- the approval matrix: amount bands → approval levels and roles;
- payment readiness: no open blocking exception, all approval levels approved and the vendor payable, then a payment
  record scheduled per payment terms.

Also define the precedence used to pick an invoice's primary status when several issues co-exist. Every engine decision
records the policy version and rule IDs, for traceability.

### E. The five actors must be explicit
Model them in the data, for example as a user/role reference table.
- **Business requester:** raises POs, confirms receipts, answers receipt and quantity questions.
- **Process owner:** owns the policy and handles policy exceptions such as invoice-before-PO or a PO overrun.
- **Approver:** the approval matrix.
- **Operations analyst:** the AP queue (extraction review, duplicates, tax, arithmetic).
- **System administrator:** vendor master, configuration, runs and audit.

Routing assigns each exception to one of these roles. The CLI and dashboard show each role its queue.

### F. History, lifecycle and bridge tables
- Every state change is an append-only event. That covers vendor status history (with effective dates), PO lifecycle,
  GRN posting, invoice lifecycle, exception lifecycle, approvals and payments.
- Each event carries from-status, to-status, timestamp, actor role and id, and reason or rule id.
- Current status is the last event. Validate every transition against a documented state machine.
- Many-to-many relationships go through bridge tables, e.g. an invoice_line ↔ goods_receipt_line match allocation.
- Document every cardinality and optional relationship.
- Document effective dates: vendor active window and status history, tax-code validity, policy version, and PO
  validity if you use it.

### G. Extraction realism
- Use at least three heterogeneous channels, vendor-specific templates, label synonyms, date and number format
  variation, and recoverable noise.
- The extractor must never correct printed values. For example, the header-total defect must survive extraction so
  that validation catches it.
- Produce per-field confidence. Low confidence routes to the operations analyst.
- Target a 100% field match with zero silent errors.

### H. Realism of distributions
Vendor activity should be skewed (Pareto-like), line values lognormal by SKU category, and dates mostly on weekdays.
Model lead times by category and give payment terms, intake channels and approval bands a realistic mix. Seasonality
is optional. Produce a distribution summary in the reports. That summary is the evidence for Evaluation Focus (a).

### I. Engineering
- The runtime uses the standard library only, with `Decimal` for money. Everything is deterministic and
  cross-platform, and `pytest` is the test framework.
- Keep it fast: ideally a full build takes well under a minute on a laptop.
- Provide a `python -m <pkg> ...` CLI and a single command that builds everything.
- Commit the generated starter and full datasets (CSV/JSON/SQL, reports) so evaluators can inspect them without
  running anything. Keep the repo a sensible size: estimate it, and don't duplicate big files needlessly.
- `.gitattributes` must force LF so the checksums survive Windows checkouts.

### J. Do not
- Spawn sub-agents, use the network, read the wall clock, or assign labels at random.
- Edit `/home/claude/sprint/prompts/` or `/home/claude/sprint/reviews/`.
- Invent the candidate's personal statement of what they reviewed or validated. Leave clearly marked placeholders.

## Your task now: Stage 1 (SPRINT_PLAN §4, Stage 1)
1. Produce the Stage-1 deliverables in the repo:
   - architecture, schema/ERD and cardinality;
   - the full data dictionary, both as markdown and in machine-readable form;
   - business rules and the policy config;
   - the data-generation plan, including the exact allocation math and mix tables at both scales;
   - the evaluation plan, the requirements traceability matrix, and the assumptions/decisions ADRs;
   - the repo skeleton: README stub, `pyproject.toml` or requirements, `.gitignore`, `.gitattributes`, MIT LICENSE,
     package layout, `tests/`.
2. Sanity-check the numbers. Write a tiny script in your scratch area, or a doc table, that proves the allocation
   counts sum exactly at both scales.
3. Commit with a meaningful message and the required trailers.
4. Write `/home/claude/sprint/dev_reports/stage-1-report.md` and start `/home/claude/sprint/DEV_LOG.md`.
5. Reply to the orchestrator in 15 lines or fewer: what is done, the commit hash, key decisions, and open questions.
   Details belong in the report.
