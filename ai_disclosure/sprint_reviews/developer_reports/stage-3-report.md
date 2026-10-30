# Stage 3 report: invoice intake and field extraction

Commit: `0a2ca58` on `main`, with both trailers. No generated data is committed; builds go to the
git-ignored `data/<scale>/`.

## 1. What was built

| Module | Role |
|---|---|
| `invoice_ap/generator/documents.py` | Renders every document in its channel format, with one seeded template per vendor and channel. Fills `intake_manifest.file_sha256` and `file_bytes` |
| `invoice_ap/spec/io.py` | Canonical cells, spec-ordered CSV and a spec-checked CSV reader, shared by generator and engine so the engine never imports the generator |
| `invoice_ap/engine/adapters.py` | One adapter per channel (details below) |
| `invoice_ap/engine/textlayout.py` | Layout reader for e-mail and scan text: item section (pipe table, columns with page breaks and repeated headers, item blocks); header fields only above it, totals only below it; two label pairs per line; letterhead vendor name; conflict detection |
| `invoice_ap/engine/labels.py`, `normalize.py`, `read.py`, `fields.py` | The engine's own synonyms and format rules (day-first dates, Indian grouping, tax-code styles, PO and user references, OCR look-alike repair inside digit tokens only), and per-method confidence |
| `invoice_ap/engine/vendor_identity.py` | VEN-01 (vendor from the printed tax registration number only), ID-01 (`INV-<vendor or VND-00000>-2026-<intake_seq>`) and VEN-04 (sender cross-check, PORTAL and EDI only). The only engine module that reads sender fields |
| `invoice_ap/engine/capture.py`, `routing.py`, `pipeline.py` | CAP-01, captured invoice and line rows, `extraction_field` with raw text, normalised value, method and confidence, RTE-01/SLA-01 routing, `decision_trace.jsonl`, `run_engine(master_dir, inbox_dir, out_dir, policy)` |
| `invoice_ap/evaluation/extraction.py` | E1/E2 extraction evaluation against `source/`, written to `reports/extraction_evaluation.{json,md}` |
| CLI | `run --scale/--data` and `evaluate --scale/--data`. `evaluate` exits 1 on any silent error or any non-degraded mismatch |

Channel formats:
- **PORTAL_JSON:** schema v1 (strings) or v2 (camelCase, numeric amounts, timestamps).
- **EDI_FLAT:** the separator (`*`, `|`, `^`, `+`) and the terminator (newline, `~`, or both) vary by
  trading partner, and amounts are decimal or carry two implied decimals.
- **EMAIL_TEXT:** an RFC 822 message whose body follows the vendor template; 35 messages at full
  scale are forwarded by an internal mailbox.
- **OCR_TEXT:** upper-case labels, two label pairs on one line, fixed-width tables that break across
  pages.

Vendor templates vary:
- labels;
- seven date formats;
- plain, western or Indian digit grouping;
- currency style (INR, Rs., the rupee sign, or a separate currency line);
- tax code as a code, a rate or "GST n%";
- three PO number styles;
- tables as pipe, columns or item blocks.

Vendor-side labels and engine-side synonyms are separate lists, and the engine imports nothing from
the renderer (ADR-040).

**Stage-3 engine scope (ADR-040).**
- The engine processes documents in intake order and applies CAP-01 as a gate.
- VEN-01 always runs, because ID-01 needs its vendor. Its exception is raised only when capture did
  not gate the document.
- EXT_LOW_CONFIDENCE, VENDOR_NOT_FOUND and VENDOR_SENDER_MISMATCH are routed into
  `processed/ap_exception.csv`. Operations-analyst exceptions are assigned round-robin.
- Stage 4 adds the remaining rules and moves VEN-04 behind the duplicate gates. Until then the
  analyst round-robin covers only these exceptions.

### Prompt 013 carry-ins

| Item | Done |
|---|---|
| NIT S2-R1-01 | `lst()` fields are `required=False`, with the rule "column always present; empty = empty list (none)". Manifest `file_sha256` and `file_bytes` are filled. `captured_invoice.normalized_invoice_number` is required only when the number was read. A full build plus engine run has **0 empty required values** in any table |
| Q1 | ADR-037 now says "drawn at 15% per e-mail original; realised 10.3% of e-mail documents (11.1% of originals)"; `data_generation.md` reworded too |
| Q3 | Data JSON (exports, `ground_truth.json`) is compact: no indent, `sort_keys`, separators `(",", ":")`. Small reports keep an indent |
| Q4 (S2-R1-02) | README "Known limitations" states business-days-only. `data_generation.md` no longer claims "above 95% weekdays" |
| Q2 | No action (Stage 4) |

Also corrected: `data_generation.md` no longer claims that every category appears in all ten intake
deciles.

## 2. Evidence

### Build, engine and evaluation at `0a2ca58`

```text
full: 300 vendors, 1500 POs, 2200 PO lines, 1800 GRNs, 2000 invoices in 2.44s
engine: 2000 documents in 0.87s; capture review 10, vendor not found 0, exceptions 10
extraction: 1992/2000 documents exact, field match 99.98%, silent errors 0, degraded scans flagged 10/10, non-degraded mismatches 0
starter: ... 200 invoices in 0.23s; engine 0.09s; 200/200 exact, silent errors 0, degraded flagged 1/1
```

`validate --quick --scale full` with the processed tables loaded: PASS, 0 violations, 187 labelled
defects.

### Extraction accuracy, full scale (52,640 fields compared)

| Channel | Documents | Exact | Fields | Accuracy | Silent errors |
|---|---|---|---|---|---|
| EDI | 900 | 900 | 23,706 | 100.00% | 0 |
| EMAIL | 340 | 340 | 8,947 | 100.00% | 0 |
| PORTAL | 656 | 656 | 17,375 | 100.00% | 0 |
| SCAN | 104 | 96 | 2,612 | 99.69% | 0 |

The 8 non-exact documents are degraded scans:
- 3 have an unreadable invoice date;
- 3 have an unreadable gross;
- 2 have a smudged invoice number.

All 8 are flagged LOW_CONFIDENCE. The other 2 degraded scans had look-alike digits that were
repaired correctly but still flagged (OCR_REPAIRED, 0.60).

Per field: 22 fields compared, all at 100.00% except `header_gross_amount` 99.85%, `invoice_date`
99.85% and `vendor_invoice_number` 99.90%. All three gaps are the flagged degraded scans.
- Vendor resolution (VEN-01): 100%.
- Invoice-ID agreement (ID-01): 100%.

Confidence calibration:

| Confidence | Fields | Accuracy |
|---|---|---|
| 1.00 | 16,673 | 100% |
| 0.99 | 22,806 | 100% |
| 0.98 | 3,077 | 100% |
| 0.97 | 930 | 100% |
| 0.95 | 6,979 | 100% |
| 0.60 | 2 | 100% |
| 0.00 | 8 | 0% |
| Not printed | 2,165 | 100% |

Capture routing:
- 10 documents routed, exactly the ground-truth EXT_LOW_CONFIDENCE set;
- recall 100% against documents with any mismatch;
- precision 80%, because the 2 repaired documents had correct values but are still routed by
  design.

All 10 routed exceptions go to OPERATIONS_ANALYST / AP_CAPTURE_REVIEW, rule CAP-01, with a 1-day SLA
and round-robin users.

### Tests: 503 pass

```text
python3 -m pytest -p no:cacheprovider                               -> 503 passed in 13.33s (3.13)
PYTHONPATH=... /usr/bin/python3.11 -m pytest -p no:cacheprovider    -> 503 passed in 14.44s (3.11)
python3 -m invoice_ap docs --check                                  -> docs up to date
```

There are 47 new tests. The session fixtures moved to `tests/conftest.py`, so each scale is built
and run once.

`tests/test_documents.py` (8):
- the manifest SHA-256 and byte count equal each file;
- four formats are used, and every template variant appears at full scale;
- documents carry no scenario codes, categories, exception types or label words, and never the
  engine's `INV-VND-` ID;
- the 10 degraded documents are scans with one unreadable field.

`tests/test_extraction.py` (33):
- accuracy at both scales;
- calibration;
- routing to the operations analyst;
- A-41: all 15 wrong printed totals are captured as printed, never recomputed;
- tricky formats:
  - Indian grouping, day-first dates (03/04/2026 is 3 April), date formats including invalid ones,
    and tax-code styles;
  - a forwarded e-mail whose Date header is not taken;
  - a multi-page scan with repeated headers and two pairs per line;
  - a one-line EDI file with implied decimals, and an EDI line-count disagreement;
  - portal v2 numbers;
  - conflicting and unknown labels.

`tests/test_extraction.py` mutation and negative tests (REV P-2):
- **120 single-digit mutations** across all four channels. Each changes one digit inside a printed
  value, located through its captured raw text in a temp copy. Every mutated field is either read
  as printed (the new raw text and a value different from the original) or flagged; the original
  value is never silently restored.
- **5 damage modes**: smudge, look-alike, deleted total, unknown TRN and truncation. Each damaged
  document goes to capture review. For an unknown TRN the vendor is empty, the ID is
  `INV-VND-00000-…` and VENDOR_NOT_FOUND is raised; the sender never fills the gap.

`tests/test_engine_sandbox.py` (6):
- **blind run** at both scales: a copy with only `master/` and `inbox/` gives byte-identical output;
- **ID-blind run** at both scales: `sender_vendor_id` and `sender_address` are blanked;
  `captured_invoice`, `captured_invoice_line`, `extraction_field` and `ap_exception` are
  byte-identical, and the trace is identical apart from the VEN-04 entries;
- a forged PORTAL sender raises VENDOR_SENDER_MISMATCH (OPERATIONS_ANALYST, AP_VALIDATION, VEN-04)
  without changing the vendor;
- engine output is identical under PYTHONHASHSEED 1 and 2 (CLI subprocess).

### Determinism

Both scales were generated and run under PYTHONHASHSEED=1 and =2 into fresh folders. Every file is
byte-identical, including the documents and the processed output.

| Scale | Files | Source manifest | captured_invoice | extraction_field |
|---|---|---|---|---|
| Starter | 245 | `d38da4caf4cab939` | `e23956c9f8c29b80` | `0cfa03f93695e101` |
| Full | 2,045 | `3e30e948cc250d33` | `a94cf6edf6e7be27` | `70bbb9a298ae8fa1` |

The source manifest now records the documents as a count, a byte total and an aggregate SHA-256. The
Stage-2 hashes changed as expected (filled manifest columns, compact JSON).

### Size (REV ruling Q3: measured with documents)

Full build, in MB:

| Part | MB |
|---|---|
| Inbox documents | 1.23 |
| Manifest | 0.38 |
| Master | 1.67 |
| Source | 0.88 |
| Ground truth | 3.59 |
| Processed (Stage 3 tables) | 8.90 |
| JSON exports | 9.80 |
| Reports | 0.02 |
| **Total** | **26.5** |

The starter build totals 2.7 MB.

Without the full-scale JSON exports, both scales together come to about 19.4 MB. Following the
ruling, Stage 5 will keep the full JSON out of the commit and record its checksums. Processed output
grows in Stage 4. Most of it is `extraction_field.csv` (about 52,600 rows at full scale), so Stage 5
may need to revisit this.

## 3. Requirements and A-items

- **R34a** (extracted fields match source): done.
- **R4**: the extraction part is done.
- **R30**: runtime sandboxes done.
- **Stage-3 gate:**
  - A-02 intake (four channels, manifest without `invoice_id`, sender only for PORTAL/EDI);
  - A-03 extraction, with negative and mutation tests;
  - A-10 boundary test (blind run);
  - A-41 survives extraction;
  - A-50 engine boundary (ID-blind run, VEN-04);
  - A-55 extracted fields match source.

`docs/requirements_traceability.md` is updated with this evidence.

## 4. Known gaps

- `extraction_field.csv` is large. The printed tax code must be one of the five codes, so
  TAX_CODE_INVALID stays unit-test-only (ADR-036/040).
- Template breakdown in E1 is by channel and format, not by vendor template: the template is
  generator-side information that the engine and the evaluation never see.
- The `ap_event` invoice lifecycle (RECEIVED -> CAPTURED -> ON_HOLD) and the remaining processed
  tables come in Stage 4.
- None of this needs the candidate. S1-R1-09 is untouched.
