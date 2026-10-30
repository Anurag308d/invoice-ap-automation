# Testing and verification

The suite has 544 tests (`python -m pytest`, about 45 seconds, Python 3.11 to 3.13, no network). It
builds both scales once per session in temporary folders and checks the generated data, the
engine, the evaluation and the outputs against each other. It also checks the committed data in
`data/` against a fresh build.

## Approach

1. **Exactness before realism.** Volumes, scenario mix, edge cases and tolerance boundaries are
   exact by construction and asserted, so every metric has a known denominator.
2. **Labels from rules, checked against intent.** The oracle derives ground truth from the true data
   and the policy. Generation fails loudly if any label differs from the scenario that was
   injected, so a label can never be "whatever the code happened to produce".
3. **An engine that cannot cheat.** The engine reads only `master/` and `inbox/`. Tests prove it at
   runtime, not only by reading the code: blind runs, ID-blind runs, time travel, and import and
   name bans.
4. **Evidence that the evaluation is not circular.** Mutating a document or a tolerance must change
   the outcome, and the evaluation must notice.
5. **Reproducibility as a test.** Byte-identical rebuilds under different hash seeds, and committed
   data equal to a fresh build.

## What each test group proves

| File | Tests | What it proves |
|---|---|---|
| `test_allocation.py` | 20 | The volume and mix arithmetic is exact and feasible at both scales: archetype identities, line histogram, edge-case counts, the N:M bridge exercised both ways |
| `test_spec.py` | 346 | Every table and field of the data dictionary is well-formed: keys, FKs, enums, units, derivations; inputs carry no label-like columns; the manifest never hands over a vendor |
| `test_policy.py` | 15 | The policy file is valid and complete: routing for all 24 types, the approval matrix, tolerances, all five actors have work |
| `test_ids_and_money.py`, `test_lifecycle.py` | 12 | ID formats, Decimal half-up money, the state machines |
| `test_generator.py` | 35 | Exact volumes and mix; IDs, FKs and totals; boundary prices exactly at, inside and outside 2%; nothing completed after the as-of date; only labelled duplicates collide; closures after activity; injections touch nothing else; oracle == intent and loud failure; identical bytes for the same seed and across PYTHONHASHSEED |
| `test_documents.py` | 8 | Four formats and every template variant appear; each manifest hash matches its file; documents contain no labels or engine IDs; degraded scans have exactly one unreadable field |
| `test_extraction.py` | 33 | Every non-degraded document matches the source on every field at both scales; confidence is calibrated; tricky formats parse (Indian grouping, day-first dates, forwarded e-mails, multi-page scans, one-line EDI with implied decimals, portal v2 numbers); conflicting or unknown labels are flagged |
| `test_engine_sandbox.py` | 6 | Blind run and ID-blind run (details below); a forged sender is caught and never changes the vendor; engine output is identical across hash seeds |
| `test_decisions.py` | 18 | 100% agreement with ground truth at both scales; absent types report "not present"; the event log validates; the receipt bridge works both ways; payments only when ready; `explain`; a fixture for each type absent from the data; duplicate precedence over VEN-04; retired GST12; time travel; tolerance mutation |
| `test_outputs.py` | 20 | Validation suite passes and catches injected faults; SQL seeds load with FKs on; JSON for every table; manifest checksums; queues for all five actors; offline deterministic dashboard; readable `evaluation.md`; `repro`; committed data equals a fresh build |
| `test_boundary.py`, `test_docs.py`, `test_repo_hygiene.py` | 30 | Import and name bans for the engine; generated docs in sync; ADR references resolve; standard library only; no clock or unseeded randomness; LF endings; MIT licence; no secrets or real e-mail addresses |

## Mutation and negative evidence

- **120 single-digit document mutations** (`test_single_digit_mutations_are_read_as_printed_or_flagged`).
  Across all four channels, one digit inside a printed value is changed. The extractor either
  reads the new printed value or flags the field. It never silently restores the original from
  the PO, the lines or master data.
- **Five damage modes** (`test_damaged_documents_are_flagged_never_silently_fixed`): smudged
  digits, OCR look-alike characters, a deleted total, an unknown tax ID, a truncated file. Each
  ends in capture review or VENDOR_NOT_FOUND, never in a confident wrong value.
- **Wrong printed totals survive extraction** (`test_arithmetic_defects_survive_extraction`). All 15
  are captured as printed, so the arithmetic rule can catch them.
- **Tolerance mutation**
  (`test_changing_a_tolerance_changes_the_engine_and_the_evaluation_sees_it`). Raising the price
  tolerance to 2.5% makes the engine pass the +2% plus one cent invoices, and the evaluation
  reports false negatives and acceptance failures. The engine and the ground truth are therefore
  not the same computation.
- **Fixtures for the eight types absent from the data**: an unknown tax ID, a missing PO, a future
  invoice date, an unknown PO line, GST12 on a 2026 invoice, a vendor blocked before payment,
  zero-day terms (due date passed) and a forged sender. Each is checked for type, routing, blocking
  flag and status effect.
- **Validation-suite fault injection**: a payment for a blocked invoice, a dangling event, an
  over-allocated receipt, an orphan FK and an illegal state transition. Each one makes the suite
  fail.

## Blind-run and time-travel evidence

- **Blind run.** The engine runs on a copy that holds only `master/` and `inbox/`; all twelve output
  tables and the decision trace are byte-identical to the normal run.
- **ID-blind run.** `sender_vendor_id` and `sender_address` are blanked; extraction, vendor
  resolution, invoice IDs, exceptions and decisions are identical. Only the trace of the sender
  cross-check changes.
- **Time travel.** Blanking every as-of snapshot column and adding a vendor status change and a
  receipt dated after the as-of date leaves every output byte-identical. For 25 sampled invoices,
  removing every master row recorded after the invoice arrived, and every later document, leaves
  the processing-time decision unchanged.

## How we know it works

- Extraction: 1,990 of 1,990 non-degraded documents match the source on every field, all 10 degraded
  scans are flagged, and there are 0 silent errors (`reports/extraction_evaluation.md`).
- Decisions: 2,000 of 2,000 invoices and 2,960 of 2,960 lines agree with ground truth; every type
  present has F1 = 1.0; duplicate pairs are 100% correct with no false positives
  (`reports/evaluation.md`).
- Safety: no invoice has a payment while blocked or unapproved, checked per invoice
  (`reports/acceptance_per_invoice.csv`) and by the validation suite.
- Data quality: 16 validation checks, 0 violations; labelled defects are reported separately
  (`reports/validation_summary.md`). Both SQL seeds load into SQLite with foreign keys enforced.
- Reproducibility: rebuilds are byte-identical file for file (`reports/reproducibility.md`), and
  `test_committed_data_equals_a_fresh_build` proves the committed data is what the code produces.

The remaining limitation is that the engine and the oracle were written by the same author. The
mutation tests show the evaluation can detect divergence, but they cannot show independent
judgement (ADR-016).
