# Source requirements — single source of truth for the sprint

This file holds the three source documents verbatim (A) or transcribed word-for-word from PDF (B, C).
Everything the solution must satisfy comes from here. When in doubt, quote this file.

---------------------------------------------------------------------------------------------------

## A. Problem statement (verbatim, from the assignment attachment)

Problem statement
Read it carefully. Your build should cover every point below.

Business Context / Problem
Automate invoice intake, field extraction, PO/receipt matching, exception routing and payment readiness.

Objective and Scope
Build a working solution for this end-to-end workflow: Automate invoice intake, field extraction, PO/receipt matching, exception routing and payment readiness. The solution should expose key decisions and exceptions, preserve traceability, and produce measurable outputs. Medium complexity means multiple related entities, conditional rules, at least one exception path and meaningful evaluation metrics.

Primary Actors / Systems
Business requester, process owner, approver, operations analyst and system administrator

Business Workflow and Rules
1. Generate/reference master data first: Vendor, PurchaseOrder, PurchaseOrderLine, GoodsReceipt, GoodsReceiptLine.
2. Generate dependent transaction/event records using valid parent IDs.
3. Apply business logic: Create vendors first; create POs referencing vendors; add 1–8 PO lines with SKU, quantity, unit price and tax code; generate receipts referencing PO lines with full/partial/over-receipt quantities; generate invoices referencing vendor and optionally PO; calculate line totals, tax and grand total from lines; derive match status from price/quantity/tax tolerances; create approval/payment records only for eligible invoices.
4. Persist state changes as explicit records/events where relevant; do not overwrite history.
5. Generate outcomes and ground-truth labels from documented rules, not independent random assignment.

Entities and Relationships
Core entities: Vendor, PurchaseOrder, PurchaseOrderLine, GoodsReceipt, GoodsReceiptLine, Invoice, InvoiceLine, Approval, Payment. Define a primary key for every entity and foreign keys for every relationship. Document cardinality (1:1, 1:N, N:M), optional relationships, effective dates and lifecycle states. Use bridge tables for many-to-many relationships; retain event history for state changes; validate all joins. For deliberate anomaly cases, keep an issue_type/ground_truth label rather than silently corrupting unrelated rows.

ID / Nomenclature Conventions
Vendor VND-00001; PO PO-2026-000001; receipt GRN-2026-000001; invoice INV-<vendor-code>-2026-000001; invoice line INVL-<invoice-id>-01.

Synthetic Data Generation Instructions (Granular)
Step 1 — Write a data dictionary for: Vendor, PurchaseOrder, PurchaseOrderLine, GoodsReceipt, GoodsReceiptLine, Invoice, InvoiceLine, Approval, Payment. For each field specify type, required/optional, allowed values, units, uniqueness and validation rule.
Step 2 — Create parent/master tables first, then child and event tables. Apply this domain-specific generation logic: Create vendors first; create POs referencing vendors; add 1–8 PO lines with SKU, quantity, unit price and tax code; generate receipts referencing PO lines with full/partial/over-receipt quantities; generate invoices referencing vendor and optionally PO; calculate line totals, tax and grand total from lines; derive match status from price/quantity/tax tolerances; create approval/payment records only for eligible invoices.
Step 3 — Apply deterministic IDs and naming: Vendor VND-00001; PO PO-2026-000001; receipt GRN-2026-000001; invoice INV-<vendor-code>-2026-000001; invoice line INVL-<invoice-id>-01. Keep counters zero-padded, IDs immutable, and referenced IDs exactly consistent across files.
Step 4 — Generate the baseline volume: Generate 300 vendors, 1,500 POs, 2,200 PO lines, 1,800 receipts and 2,000 invoices. Make ~70% clean matches, 10% price variance, 8% quantity mismatch, 5% duplicate invoices, 4% missing receipt and 3% tax/vendor errors. Keep every foreign key valid except deliberately labelled defect cases. Use a fixed seed (e.g. 20261022) and parameterize scale so starter and full datasets use the same generator.
Step 5 — Generate valid baseline records first, then inject labelled edge cases: Duplicate invoice number; invoice total differs from line sum; invoice date before PO date; partial delivery; closed vendor; tax mismatch; invoice exceeds PO quantity; same invoice submitted twice.
Step 6 — Calculate derived values (totals, balances, scores, statuses and dates) from source records rather than generating them independently.
Step 7 — Produce a separate ground_truth.csv/json for known anomalies, expected decisions or labels; never leak it into input features.
Step 8 — Run validation: primary-key uniqueness, foreign-key integrity, allowed enums, date ordering, arithmetic reconciliation, lifecycle transitions and duplicate checks.
Step 9 — Export CSV/JSON/SQL seed data plus README, schema/data dictionary, generator command, fixed seed, source manifest and validation summary.
Step 10 — Regenerate twice with the same seed and compare row counts/checksums to demonstrate reproducibility.

Suggested Volume and Coverage
Generate 300 vendors, 1,500 POs, 2,200 PO lines, 1,800 receipts and 2,000 invoices. Make ~70% clean matches, 10% price variance, 8% quantity mismatch, 5% duplicate invoices, 4% missing receipt and 3% tax/vendor errors. Keep every foreign key valid except deliberately labelled defect cases.

Required Edge Cases / Negative Scenarios
Duplicate invoice number; invoice total differs from line sum; invoice date before PO date; partial delivery; closed vendor; tax mismatch; invoice exceeds PO quantity; same invoice submitted twice.

Validation Rules / Acceptance Criteria
For each invoice: extracted fields match source; line arithmetic and tax reconcile; duplicate detection flags the correct pair; three-way match and approval outcome agree with policy; no blocked invoice is marked payment-ready.

Evaluation Focus for Generated Data
Review: (a) realistic distributions and meaningful variation; (b) consistent IDs and valid joins; (c) dependency/lifecycle consistency across entities; (d) correct derived values and reconciliation; (e) normal, boundary, failure and exception coverage; (f) separate ground truth; (g) fixed-seed reproducibility, documentation and lawful provenance.

Public Data Guidance / Lawful Use
External data is optional. If used, record source URL, dataset/version, retrieval date, license/terms, attribution, transformations and fields discarded. Use only data you are legally permitted to access and redistribute; do not bypass access controls or collect confidential/personal information. If licensing or suitability is unclear, use synthetic data and cite public reference data only for schema inspiration.
Before you submit, make sure you have
Pushed your code to a public GitHub repository
Added a README explaining how to run it
Included any tests the problem asks for

---------------------------------------------------------------------------------------------------

## B. YottaFlex AI — Candidate Project Submission Guidelines (transcribed from PDF)

YottaFlex AI — RECRUITMENT DRIVE — Candidate Project Submission Guidelines
"Show us how you think, build, validate, and work with AI."

YOUR CHALLENGE WINDOW — 72 HOURS. Your submission window is 72 hours. Artifact timestamps will be used to verify the window.

01 MAKE IT RUN (EXECUTABLE)
Submit working, executable code. Include clear steps so another person can install dependencies, configure the project, run it, and verify key behavior.

02 SHOW YOUR WORK (PUBLIC REPOSITORY)
Use a public GitHub repository. Make the evolution of your work understandable through the code, meaningful commits, and supporting context.

03 USE LLMs TRANSPARENTLY (PROMPT HISTORY REQUIRED)
LLM tools are allowed. Submit your prompt history and explain where AI accelerated your work, where you relied heavily on it, and what you personally reviewed, changed, or validated.

04 MAKE YOUR REASONING VISIBLE (EXPLAIN THE WHY)
Help reviewers understand the problem, assumptions, key decisions, trade-offs, testing approach, limitations, and how you know the solution works.

BE READY TO WALK US THROUGH YOUR SOLUTION.
We value sound judgment, working software, honest AI disclosure, and clear communication.

---------------------------------------------------------------------------------------------------

## C. YottaFlex AI — Candidate Project FAQ (transcribed from PDF)

72 HOURS • PUBLIC GITHUB • TRANSPARENT AI USE • INDIVIDUAL WORK

1. When does my 72-hour window start?
When YottaFlex AI sends you the project. Your deadline is exactly 72 hours later, using the recorded send timestamp and its time zone.

2. Can I submit early?
Yes. You may submit as soon as you are ready. Keep your public repository available and editable until the 72-hour deadline; the latest version at the deadline is evaluated.

3. How do I submit my repository link?
Create a new, dedicated public GitHub repository. Send the link from the same email address you used during recruitment and follow the submission instructions provided.

4. What belongs in my repository?
Include your code, prompt history, and relevant supporting artifacts in a clearly identifiable directory. There is no fixed list of documents or prescribed format.

5. Which AI tools may I use?
Any LLM or AI coding tool is allowed, including cloud-based and locally hosted tools. AI use is unrestricted; your judgment, understanding, ownership, and validation matter.

6. What prompt history is required?
Include all prompts submitted to every AI tool you used. AI responses are optional. If a tool cannot export prompts, keep a reasonable record and disclose the limitation.

7. Must I write all code myself?
The project must be your individual work. AI and public learning resources are allowed; implementation help from other people is not. Understand the core logic, key design choices, dependencies, and limitations.

8. Can I choose my own technology stack?
Yes. Choose suitable languages, frameworks, and storage. Use only free or locally runnable services, and avoid unusually large or slow dependencies where possible.

9. Must I provide a live demo or automated tests?
No hosted demo or automated test suite is mandatory. Provide clear setup/run instructions and demonstrate how you verified the core functionality. Document environment needs and limitations.

10. Can I reuse existing code?
Standard dependencies and small illustrative snippets are acceptable. Do not import a complete solution or existing code that performs the core project work. Follow licenses and provide attribution where required.

11. What if requirements are unclear or work is incomplete?
Make reasonable assumptions and explain them. Partial solutions are acceptable if you state what works, what remains incomplete, known limitations, and next steps. Explain any requirement deviations.

12. What must I keep out of a public repository?
Never include secrets, credentials, personal or sensitive information, or proprietary code you are not authorized to publish. Use safe sample data and local configuration; explain setup in the README.

BE READY TO EXPLAIN YOUR DECISIONS, VERIFY YOUR WORK, AND OWN YOUR SUBMISSION.
