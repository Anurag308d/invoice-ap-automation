# Walkthrough (10-15 minutes)

A script for presenting the solution live. Commands assume the repository root and Python 3.11+.
Everything works offline, and the committed data means nothing has to be built before starting.

## 0. Before you start (1 minute, off-screen)

```bash
python -m invoice_ap build --scale starter   # warm-up, under a second; checks the environment
```

Open `data/full/reports/dashboard.html` in a browser tab, and `data/full/reports/evaluation.md` in an
editor or Markdown preview.

## 1. The problem and the shape of the answer (2 minutes)

- AP gets invoices by portal, EDI, e-mail and scan. Each must be matched to a PO and receipt, routed
  when wrong, approved by amount, and paid safely.
- Show the "Solution overview" diagram in the README. Two independent halves:
  - a **generator** builds a synthetic ERP world and renders documents, with a rule-based ground
    truth;
  - an **engine** sees only master data and documents.
- The point to make: the engine cannot read the answers. Mention the blind-run and ID-blind tests
  now; they return in step 6.

## 2. The data (2 minutes)

```bash
python -m invoice_ap plan --scale full | head -40
```

- Exact volumes: 300 vendors, 1,500 POs, 2,200 lines, 1,800 receipts, 2,000 invoices. The exact mix
  and the eight edge cases.
- Open one document of each kind under `data/full/inbox/documents/`: a portal JSON, an EDI file, an
  e-mail, a scan. Point out that the vendor is identified only by the printed tax number.
- `data/full/reports/distribution_summary.md`: vendor concentration and realistic prices and lead
  times.

## 3. The policy is configuration (1 minute)

Open `config/ap_policy.toml`. Show the 2% price tolerance, the 5% over-receipt tolerance, the
routing matrix (type -> role -> queue -> SLA) and the approval bands. Every decision records this
policy's version.

## 4. The engine on one invoice (3 minutes)

```bash
python -m invoice_ap explain INV-VND-00279-2026-000032 --scale full
```

Walk through the output:
1. capture confidence;
2. vendor from the tax ID;
3. no duplicate;
4. line match: billed 142 against a maximum of 130.2 (ordered plus 5%), so QTY_EXCEEDS_PO goes to
   the process owner;
5. the receipt allocation (bridge) row;
6. the event log;
7. the decision trace.

Then show a clean invoice in the dashboard's invoice explorer: AUTO approval, a payment scheduled
on the due date, PAID by the payment run.

## 5. The five actors (1-2 minutes)

```bash
python -m invoice_ap queue --role PROCESS_OWNER --scale full
python -m invoice_ap queue --role APPROVER --scale full
```

In the dashboard, click through the queue tabs. Say plainly that no resolutions are simulated, so
the backlog is "open and past SLA at the snapshot", aged in business days.

## 6. How we know it works (3 minutes)

Open `evaluation.md` and show:
- the headline table: STP 46.05%, 0 unsafe payments, 2,000 of 2,000 acceptance;
- agreement with ground truth: 100% on every item;
- per-type precision, recall and F1, with the eight absent types reported as "not present";
- the duplicate pairs: 100 of 100, with no false positives on recurring or same-day invoices.

Then the credibility evidence, from [testing and verification](testing_and_verification.md):
- mutated documents are read as printed or flagged, never silently fixed;
- a tolerance change makes the evaluation report errors, so the comparison is not circular;
- the blind run, the ID-blind run and the time-travel tests.

```bash
python -m pytest tests/test_engine_sandbox.py tests/test_decisions.py -q
```

## 7. Reproducibility and outputs (1 minute)

- `data/full/reports/reproducibility.md`: 2,074 of 2,074 files byte-identical across two rebuilds
  with different hash seeds.
- `data/full/reports/source_manifest.json`: every file with its SHA-256, plus provenance.
- `exports/sql/seed.sql` (starter) loads into SQLite with foreign keys on.
- One command rebuilds everything: `python -m invoice_ap build-all`.

## 8. Limitations and what's next (1 minute)

Cover these from the README:
- no simulated resolutions or rejections;
- business days only;
- text documents, not images;
- one author for engine and oracle.

Next steps: simulated resolutions with their own audit trail, real OCR, multi-entity policy, and a
live queue UI on the event log.

## Likely questions

- **Why should we trust labels the same code base produced?** The oracle and the engine are separate
  computations: the oracle works on true data, the engine on documents. Generation fails if labels
  differ from the injected intent, and the mutation tests show the evaluation catches divergence.
- **Could the engine take the vendor from the sender or the invoice ID?** No. The manifest has no
  invoice ID, the sender exists only for authenticated channels, and the ID-blind run gives
  identical results.
- **What happens at exactly +2.00%?** The tolerance is inclusive, so it passes. +2.00% plus one cent
  fails. Both boundary cases are in the data.
