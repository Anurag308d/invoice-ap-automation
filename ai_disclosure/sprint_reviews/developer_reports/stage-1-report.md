# Stage 1 report: specification, design and repo skeleton

- Commit: `12f551a` on `main` ("stage-1: specification, design docs, policy config and exact allocation"),
  51 files, author = repo-local identity, both required trailers present.
- Repo: `/home/claude/invoice-ap-automation`.

## 1. What was built

| Stage-1 DoD deliverable | File(s) | Notes |
|---|---|---|
| Architecture, data flow (mermaid), module boundaries, no-leakage design | `docs/architecture.md` | Generator / engine / evaluation / quality / export / report / CLI; engine pipeline with gates; determinism and time model; CLI surface; size budget |
| Schema: ERD (mermaid `erDiagram`), PK/FK list, cardinality, optional relationships, effective dates, state machines | `docs/schema.md` | Two ERDs (core and supporting); C1-C23 cardinality table, including the N:M bridge `match_allocation`. **Generated** key list (29 tables, every FK) and state machines for Vendor, PO, GRN, Invoice, Exception, Approval and Payment from `invoice_ap/common/lifecycle.py` |
| Data dictionary (markdown + machine-readable) | `docs/data_dictionary.md`, `invoice_ap/spec/data_dictionary.json`, source `invoice_ap/spec/tables_*.py` | 29 tables, 336 fields. Each field: type, required/optional/conditional, allowed values or pattern or range, unit, unique, origin (source / derived / assigned / captured / decided), validation rule or derivation formula, FK, description. Markdown and JSON are generated from the Python spec, which later stages use for headers, validation and SQL DDL |
| Business rules + versioned policy config | `docs/business_rules.md`, `config/ap_policy.toml` | 30+ rule IDs; tolerances with justification; match-status derivation; precedence; duplicate normalisation; **generated** routing matrix (23 exception types -> severity, blocking, role, queue, SLA) and approval matrix (7 bands, 5 levels); payment readiness. The policy is validated on load (`invoice_ap/common/policy.py`) |
| Data-generation plan with exact allocation math and mix tables at both scales | `docs/data_generation.md`, `invoice_ap/generator/allocation.py`, `invoice_ap/generator/catalogue.py` | Algorithm with the archetype identities; **generated** Tables G1-G8 (targets, mix, populations, PO archetypes, line histogram, 40 sub-scenarios, edge-case coverage, vendor mix); distributions; injection mechanics; duplicates; ground-truth schema; determinism rules |
| Evaluation plan | `docs/evaluation_plan.md` | R34a-e -> metrics and targets; E1-E15 catalogue; per-invoice acceptance check; Evaluation Focus (a)-(g) -> evidence |
| Requirements traceability | `docs/requirements_traceability.md` | Every R1-R37 (with sub-items) and G1-G11 -> location -> evidence -> stage -> status |
| Assumptions and decisions | `docs/assumptions_and_decisions.md` | ADR-001..036, grouped by topic, plus 4 open questions |
| Repo skeleton | `README.md` (stub), `pyproject.toml`, `requirements-dev.txt`, `.gitignore`, `.gitattributes` (LF forced), `LICENSE` (MIT), `invoice_ap/` (common, spec, generator, engine, evaluation, quality, export, report, `cli.py`, `__main__.py`), `tests/` | CLI: `plan`, `docs [--check]`, `policy` work; later commands are registered and exit 2 with a "planned: Stage N" message |

## 2. Key numbers (both scales, from code)

| | Full | Starter |
|---|---|---|
| Vendors / POs / PO lines / GRNs / invoices | 300 / 1,500 / 2,200 / 1,800 / 2,000 | 30 / 150 / 220 / 180 / 200 |
| CLEAN / PRICE / QTY / DUP / MISSING-REC / TAX-VENDOR / ARITH / INV-BEFORE-PO | 1,360 / 200 / 160 / 100 / 80 / 60 / 20 / 20 | 136 / 20 / 16 / 10 / 8 / 6 / 2 / 2 |
| Shares | 68.0 / 10 / 8 / 5 / 4 / 3 / 1 / 1 % | identical |
| Duplicates / non-PO originals / PO-backed originals | 100 / 100 / 1,800 | 10 / 10 / 180 |
| Archetypes A11 / A22 / A33 / A21 / A01 / A10 / A00 | 930 / 300 / 50 / 40 / 80 / 40 / 60 | 93 / 30 / 5 / 4 / 8 / 4 / 6 |
| PO line histogram (1..8 lines) | 1090 / 260 / 80 / 35 / 15 / 10 / 5 / 5 | 112 / 22 / 8 / 4 / 2 / 1 / 0 / 1 |
| Edge cases EC-01..EC-08 | 35 / 15 / 20 / 550 / 15 / 30 / 50 / 65 | 3 / 1 / 2 / 55 / 1 / 3 / 5 / 7 |

Every one of the 40 sub-scenarios has at least one invoice at both scales. Boundary trios:
- price at, inside and outside tolerance: C-PRICE-AT-TOL, C-PRICE-INSIDE, PV-BOUNDARY-OUT;
- quantity at and outside tolerance: C-QTY-AT-TOL, QM-BOUNDARY-OUT;
- tax rounding: C-TAX-ROUNDING.

True negatives:
- C-NPO-RECURRING (same-amount monthly series);
- C-TN-SAME-DAY (same vendor, date and amount on different POs).

## 3. Requirement IDs covered

Status is taken from `docs/requirements_traceability.md`.
- **Done in Stage 1** (with evidence): R12, R14, R20 (data dictionary); R13, R15, R29 (spec level);
  R19 (ID formats); R23, R24, R27, R28a-h (allocation); R9c, R9f helpers; R6 (actors in spec and
  policy); R10 (state machines); G7, G9, G10.
- **Designed** with a planned home and evidence: every other R-/G- item (traceability matrix).
  Nothing is left without a home.

## 4. How it was verified

```text
$ python3 -m pytest
408 passed in 0.45s                          # Python 3.13 (default interpreter)
$ PYTHONPATH=<py3.13 site-packages> /usr/bin/python3.11 -m pytest -q -p no:cacheprovider   -> all pass
$ PYTHONPATH=<py3.13 site-packages> /usr/bin/python3.12 -m pytest -q -p no:cacheprovider   -> all pass
$ python3 -m invoice_ap docs --check
docs up to date
$ python3 -m invoice_ap policy
AP-POLICY 1.0.0 (sha256 ...) as-of 2026-12-31: valid
  23 routed exception types, 7 approval bands
$ python3 -m invoice_ap plan --scale 0.25          # any factor works through the same code path
scale x1/4: Targets(vendors=75, pos=375, po_lines=550, grns=450, invoices=500)
```

Test breakdown:

| File | Tests | What it covers |
|---|---|---|
| `tests/test_allocation.py` | 16 | Exact identities at 5 scales; full mix exact; coverage of every sub-scenario and edge case; determinism; apportion and histogram properties; loud failure at a too-small scale; catalogue vs vocabulary; doc tables current |
| `tests/test_spec.py` | 343 | Every field fully specified; FK targets unique and within allowed layers; acyclic FK graph; no label-like columns in master or inbox; generated markdown and JSON current |
| `tests/test_policy.py` | 14 | Policy loads; precedence and routing cover all 23 types; all five actors have work; exact decimals; 9 mutation tests prove the validator rejects broken edits |
| `tests/test_boundary.py` | 4 | Static import rule for engine, common and spec (no transitive path to generator or evaluation code); engine source never names evaluation-only data |
| `tests/test_repo_hygiene.py` | 6 | stdlib-only imports; banned non-deterministic calls (wall clock, global RNG, libm transcendental maths, uuid); no runtime dependencies; LF attributes; MIT; LF bytes |
| `tests/test_docs.py` | 17 | Every generated block current; every relative link resolves; every referenced ADR is defined; every policy rule ID is documented |
| `tests/test_ids_and_money.py` | 8 | Assignment ID examples; every pattern; embedded references; HALF_UP rounding; float rejection; inclusive tolerance boundary |

**Independent sanity check (brief task 2).**
`/tmp/claude-0/-home-claude/16a00384-541a-5240-9176-a462a41d7e89/scratchpad/check_allocation_tables.py`
re-derives every total from the rendered tables in `docs/data_generation.md`, without importing the
allocation code. It checks, at both scales:
- categories and sub-scenarios each sum to the invoice count, and per category;
- archetype POs, GRNs (n x GRNs/PO) and invoices;
- populations;
- line-histogram POs and lines (k x POs);
- every sub-scenario >= 1 and EC-01..08 >= 1.

Result: `ALL CHECKS PASSED`.

**Packaging check.** `pyproject.toml` builds a wheel that contains the package and the JSON spec but
not tests or docs. One environment quirk: the image's Debian-patched setuptools 68.1.2 fails with
`AttributeError: install_layout` unless `SETUPTOOLS_USE_DISTUTILS=stdlib` is set. This is unrelated to
the project, and the run path never needs an install (ADR-001).

## 5. Key decisions (details in ADRs)

- **ADR-002/003**: `<vendor-code>` = `vendor_id`, giving `INV-VND-00001-2026-000001`. The invoice
  counter is global in intake order. The vendor's printed number is separate, and resubmissions get
  a new `invoice_id`.
- **ADR-005**: the five named categories are exact (10/8/5/4/3%). The two extra edge cases (header
  total vs lines, invoice before PO) take 1% each from CLEAN, so CLEAN is 68.0%.
- **ADR-022/023**: exact PO-fulfilment archetypes solve the PO, GRN and invoice identities, plus an
  exact line histogram. The RNG only places slots and never decides counts or labels.
- **ADR-010/011**: the engine, not the generator, creates approvals and payments, and the expected
  ones are in ground truth. As-of snapshot (2026-12-31): exceptions are routed but not resolved;
  simulated approvers approve after a fixed turnaround.
- **ADR-020/024/009**: three gates (capture, duplicate, invalid PO), otherwise every issue is
  collected. The cumulative quantity rule counts held prior invoices but never duplicates. There are
  three duplicate rules, with normalisation and true negatives.
- **ADR-015**: determinism without libm. Integer draws plus `Decimal.exp`; a test bans
  `math.exp`, `random.gauss`, the wall clock and `uuid`.
- **ADR-033**: docs that can drift (dictionary, keys, state machines, routing and approval
  matrices, allocation tables) are generated from code and config, and tests fail when they are stale.
- **ADR-001 (deviation)**: flat `invoice_ap/` layout instead of `src/`, so `python -m invoice_ap`
  works straight after cloning. The boundary is enforced by tests.

## 6. Known gaps (by design, later stages)

- Generator, oracle and ground truth (Stage 2); rendering and extraction (Stage 3); engine, approvals,
  payments and evaluation (Stage 4); validation suite, exports, manifest, reproducibility, queue CLI
  and dashboard (Stage 5); final README and `ai_disclosure/` (Stage 6).
- The runtime no-leakage sandbox test arrives with the engine (Stage 3). The static import boundary
  test is active now.
- The distribution parameters in `data_generation.md §5` are planned values. Realised values will be
  reported in Stage 2.
- The repo-size estimate (about 4 MB starter, 30-45 MB full) is unmeasured until Stage 5.

## 7. Open questions for REV and the orchestrator

1. Is CLEAN at 68.0% (ADR-005) acceptable, given the transparent carve-out for EC-02 and EC-03?
2. Should the degraded-capture overlay (10 / 1 invoices) count inside CLEAN, or be its own
   category (ADR-017)?
3. Is committing a full build of about 30-45 MB acceptable, or should the full-scale JSON be
   compacted (ADR-028)?
4. Is the flat layout deviation acceptable (ADR-001)?
