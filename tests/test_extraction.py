"""Stage-3 extraction (REV P-2): accuracy against source, tricky formats, and negative / mutation tests.

The extractor must either read what is printed or flag the field; it must never produce a silent
"correct" value from somewhere else (the PO, the lines, master data or the sender).
"""
from __future__ import annotations

import csv
import random
import re
import shutil
from datetime import date
from decimal import Decimal as D
from pathlib import Path

import pytest

from invoice_ap.common.policy import load_policy
from invoice_ap.engine import run_engine
from invoice_ap.engine.adapters import edi, email, portal, scan
from invoice_ap.engine.capture import confidence_floor
from invoice_ap.engine import normalize as N
from invoice_ap.spec.io import read_table

THRESHOLD = D("0.90")


# ------------------------------------------------------------------ accuracy on the generated data
@pytest.mark.parametrize("scale", ["starter", "full"])
def test_every_non_degraded_document_matches_source_on_every_field(engine_runs, scale):
    root, summary, report = engine_runs[scale]
    assert report["non_degraded_documents_with_mismatch"] == []
    assert report["silent_errors"] == 0
    assert report["vendor_resolution_rate"] == "100.00%" and report["invoice_id_agreement_rate"] == "100.00%"
    assert report["degraded_scans_flagged"] == report["degraded_scans"] == {"starter": 1, "full": 10}[scale]
    assert report["capture_routing"]["routed_equals_ground_truth"]
    assert all(m["flagged"] and m["degraded_scan"] for m in report["mismatches"])


def test_confidence_is_calibrated(engine_runs):
    _, _, report = engine_runs["full"]
    for bucket, c in report["confidence_calibration"].items():
        if bucket != "not printed" and D(bucket) >= THRESHOLD:
            assert c["accuracy"] == "100.00%", bucket


def test_capture_review_routes_to_the_operations_analyst(engine_runs):
    root, _, _ = engine_runs["full"]
    exc = read_table(root / "processed", "ap_exception")
    cap = {c["invoice_id"]: c for c in read_table(root / "processed", "captured_invoice")}
    assert len(exc) == 10
    for e in exc:
        assert (e["exception_type"], e["assigned_role"], e["queue"], e["rule_id"]) == (
            "EXT_LOW_CONFIDENCE", "OPERATIONS_ANALYST", "AP_CAPTURE_REVIEW", "CAP-01")
        assert cap[e["invoice_id"]]["capture_status"] == "LOW_CONFIDENCE"
    assert len({e["assigned_user_id"] for e in exc}) > 1          # round-robin across analysts


def test_arithmetic_defects_survive_extraction(engine_runs):
    """A-41: a wrong printed total is captured as printed, never recomputed from the lines."""
    root, _, _ = engine_runs["full"]
    gt = {g["doc_id"]: g for g in read_table(root / "ground_truth", "ground_truth")}
    src = {s["doc_id"]: s for s in read_table(root / "source", "invoice")}
    cap = {c["doc_id"]: c for c in read_table(root / "processed", "captured_invoice")}
    lines = {}
    for l in read_table(root / "processed", "captured_invoice_line"):
        lines.setdefault(l["invoice_id"], []).append(l)
    hits = 0
    for doc_id, g in gt.items():
        if g["scenario_code"] == "ARITH-HEADER-TOTAL":
            c = cap[doc_id]
            assert c["header_gross_amount"] == src[doc_id]["header_gross_amount"]
            line_sum = sum(D(l["line_net_amount"]) + D(l["tax_amount"]) for l in lines[c["invoice_id"]])
            assert D(c["header_gross_amount"]) != line_sum
            hits += 1
    assert hits == 15


# ------------------------------------------------------------------ tricky formats (unit level)
def _text(*lines: str) -> bytes:
    return ("\n".join(lines) + "\n").encode()


BASE_ITEMS = ("| # | Item Code | Description | UOM | Qty | Rate | Amount | Tax Code | Tax Amt |",
              "|---|---|---|---|---|---|---|---|---|",
              "| 1 | SKU-00001 | Widget - A | KG | 1,250.50 | 1,20,000.00 | 15,00,60,000.00 | 18% | 2,70,10,800.00 |")


def test_indian_grouping_day_first_dates_and_rate_style_tax_codes():
    raw = scan(_text("Supplier: Acme Pvt Ltd", "TRN: TRN-123456789", "Invoice No: SI/26-27/007",
                     "Invoice Date: 03/04/2026", *BASE_ITEMS, "", "Subtotal: Rs. 15,00,60,000.00",
                     "Tax: Rs. 2,70,10,800.00", "Grand Total: Rs. 17,70,70,800.00"))
    h, line = raw.header, raw.lines[0]
    assert h["invoice_date"].value == date(2026, 4, 3)                     # day first, never 4 March
    assert h["header_gross_amount"].value == D("177070800.00")
    assert h["currency"].value == "INR" and h["currency"].method == "PATTERN"
    assert line["quantity"].value == D("1250.50") and line["tax_code"].value == "GST18"
    assert h["vendor_invoice_number"].value == "SI/26-27/007"
    assert confidence_floor(raw) >= THRESHOLD


@pytest.mark.parametrize("text,expected", [("2026-03-05", date(2026, 3, 5)), ("05.03.2026", date(2026, 3, 5)),
                                           ("05 Mar 2026", date(2026, 3, 5)), ("05-Mar-2026", date(2026, 3, 5)),
                                           ("March 05, 2026", date(2026, 3, 5)), ("31/02/2026", None),
                                           ("Mar 2026", None), ("Tue, 20 Jan 2026 17:23:00 +0530", None)])
def test_date_formats(text, expected):
    assert N.invoice_date(text) == expected


@pytest.mark.parametrize("text,expected", [("GST18", "GST18"), ("18%", "GST18"), ("GST 5%", "GST5"), ("0%", "GST0"),
                                           ("Exempt", "EXEMPT"), ("18", None), ("GST28", None)])
def test_tax_code_styles(text, expected):
    assert N.tax_code(text) == expected


def test_forwarded_email_header_is_not_invoice_content():
    raw = email(_text("From: someone@buyer.example", "Date: Tue, 20 Jan 2026 17:23:00 +0530", "Subject: Invoice 9", "",
                      "FYI", "", "---------- Forwarded message ---------", "From: Acme <ap@acme.example>",
                      "Date: Tue, 20 Jan 2026 17:23:00 +0530", "Subject: Invoice 9", "",
                      "Vendor: Acme", "Tax Reg No: TRN-123456789", "Bill No: 9", "Dated: 19-Jan-2026", *BASE_ITEMS, "",
                      "Net Amount: INR 15,00,60,000.00", "GST: INR 2,70,10,800.00", "Total: INR 17,70,70,800.00"))
    assert raw.header["invoice_date"].value == date(2026, 1, 19)
    assert raw.header["invoice_date"].confidence >= THRESHOLD           # no conflict with the e-mail Date header


def test_multi_page_scan_table_and_two_pairs_per_line():
    raw = scan(_text("ACME PVT LTD", "TRN  TRN-123456789", "TAX INVOICE",
                     "INVOICE NO: A-1      DATE: 05.03.2026", "PO NO: PO/2026/000123      ATTN: USR-0007", "CURRENCY  INR",
                     "LINE   PO LN   SKU         DESCRIPTION   UNIT   QTY   PRICE    AMOUNT    TAX CODE   TAX",
                     "1      1       SKU-00001   Bolt - A      EA     10    100.00   1000.00   GST18      180.00",
                     "2      2       SKU-00002   Nut - B       EA     20    10.00    200.00    GST18      36.00",
                     "-- Page 1 of 2 --", "",
                     "LINE   PO LN   SKU         DESCRIPTION   UNIT   QTY   PRICE    AMOUNT    TAX CODE   TAX",
                     "3      3       -           Freight       JOB    1     50.00    50.00     GST18      9.00", "",
                     "SUBTOTAL  1250.00", "TAX  225.00", "TOTAL  1475.00", "-- end of document --"))
    assert [l["line_number"].value for l in raw.lines] == [1, 2, 3]
    assert raw.lines[2]["sku_id"].value is None and raw.lines[2]["uom"].value == "JOB"
    assert raw.header["vendor_name"].value == "ACME PVT LTD" and raw.header["vendor_name"].method == "PATTERN"
    assert raw.header["po_number"].value == "PO-2026-000123" and raw.header["attention_user_id"].value == "USR-0007"
    assert raw.header["header_tax_amount"].value == D("225.00")        # totals "TAX" never read as a column
    assert confidence_floor(raw) >= THRESHOLD


def test_edi_single_line_with_implied_decimals():
    raw = edi(b"UNB+2+IMP2~NAD+SU+TRN-123456789+A & B Traders~BGM+380+INV-2026-0001+20260305~CUX+INR~"
              b"RFF+ON+PO-2026-000001~LIN+1+SKU-00001+1+KG+12.50+11717+146463+GST5+7323~IMD+1+Sheet - A~"
              b"MOA+125+146463~MOA+124+7323~MOA+77+153786~CNT+2+1~UNZ+1\n")
    assert raw.header["vendor_name"].value == "A & B Traders"
    assert raw.lines[0]["unit_price"].value == D("117.17") and raw.lines[0]["quantity"].value == D("12.50")
    assert raw.header["header_gross_amount"].value == D("1537.86") and confidence_floor(raw) >= THRESHOLD


def test_edi_line_count_disagreement_is_flagged():
    raw = edi(b"UNB*2*DEC\nNAD*SU*TRN-123456789*Acme\nBGM*380*7*20260305\nCUX*INR\n"
              b"LIN*1*SKU-00001**EA*1*10.00*10.00*GST18*1.80\nIMD*1*X\nMOA*125*10.00\nMOA*124*1.80\nMOA*77*11.80\n"
              b"CNT*2*2\nUNZ*1\n")
    assert confidence_floor(raw) < THRESHOLD


def test_portal_v2_numbers_are_taken_as_printed():
    raw = portal(b'{"schemaVersion":"2.0","vendor":{"legalName":"Acme","taxId":"TRN-123456789"},'
                 b'"header":{"invoiceNo":"7","invoiceDate":"2026-03-05T00:00:00+05:30","purchaseOrder":null,'
                 b'"requesterId":"USR-0009","currencyCode":"INR"},"totals":{"taxable":100.00,"tax":18.00,"payable":118},'
                 b'"items":[{"seq":1,"orderLine":null,"itemCode":null,"text":"Audit","unit":"JOB","qty":1,'
                 b'"rate":100.00,"value":100.00,"taxCode":"GST18","taxValue":18.00}]}')
    assert raw.header["header_gross_amount"].value == D("118.00") and "po_number" not in raw.header
    assert "sku_id" not in raw.lines[0] and "po_line_number" not in raw.lines[0]     # null = not printed
    assert confidence_floor(raw) == D("1.00")


def test_conflicting_and_unknown_labels_are_flagged():
    base = ["Vendor: Acme", "TRN: TRN-123456789", "Invoice No: 1", "Invoice Date: 05-03-2026"]
    tail = ["", "Subtotal: 15,00,60,000.00", "Tax: 2,70,10,800.00", "Total: 17,70,70,800.00"]
    conflict = scan(_text(*base, "Date: 06-03-2026", *BASE_ITEMS, *tail))
    assert conflict.header["invoice_date"].confidence < THRESHOLD
    unknown = scan(_text(*base, *BASE_ITEMS, "", "Subtotal: 15,00,60,000.00", "Tax: 2,70,10,800.00",
                         "Sum Due Now: 17,70,70,800.00"))
    assert "header_gross_amount" not in unknown.header and confidence_floor(unknown) == D("0.00")


# ------------------------------------------------------------------ mutation tests on rendered documents
def _copy(root: Path, tmp: Path) -> Path:
    dst = tmp / "ds"
    for layer in ("master", "inbox"):
        shutil.copytree(root / layer, dst / layer)
    return dst


def _run(ds: Path) -> dict:
    run_engine(ds / "master", ds / "inbox", ds / "processed", load_policy())
    cap = {c["doc_id"]: c for c in read_table(ds / "processed", "captured_invoice")}
    fields = {}
    for f in read_table(ds / "processed", "extraction_field"):
        fields[(f["doc_id"], f["invoice_line_id"], f["field_name"])] = f
    return {"cap": cap, "fields": fields, "exc": read_table(ds / "processed", "ap_exception")}


MUTABLE = ("header_gross_amount", "header_net_amount", "header_tax_amount", "invoice_date", "vendor_invoice_number",
           "quantity", "unit_price", "line_net_amount", "tax_amount")


def test_single_digit_mutations_are_read_as_printed_or_flagged(engine_runs, tmp_path):
    """Change one digit inside a printed value (located by its captured raw text, occurring exactly
    once in the file). The engine must then either flag that field (or the document) or capture a
    value different from the original: it must never silently restore the original value."""
    root, _, _ = engine_runs["full"]
    ds = _copy(root, tmp_path)
    before = _run(ds)
    manifest = {m["doc_id"]: m for m in read_table(ds / "inbox", "intake_manifest")}
    rng = random.Random(20261022)
    targets, used = [], set()
    candidates = sorted(k for k, f in before["fields"].items() if k[2] in MUTABLE and f["raw_text"]
                        and re.search(r"\d", f["raw_text"]) and before["cap"][k[0]]["capture_status"] == "OK")
    rng.shuffle(candidates)
    for key in candidates:
        doc_id = key[0]
        if doc_id in used:
            continue
        path = ds / "inbox" / manifest[doc_id]["file_path"]
        text = path.read_text(encoding="utf-8")
        raw = before["fields"][key]["raw_text"]
        if text.count(raw) != 1:
            continue
        span = raw.split("T")[0] if re.match(r"\d{4}-\d{2}-\d{2}T", raw) else raw   # not the time of day
        digits = [i for i, ch in enumerate(span) if ch.isdigit()]
        i = digits[rng.randrange(len(digits))]
        mutated = raw[:i] + str((int(raw[i]) + rng.randrange(1, 10)) % 10) + raw[i + 1:]
        path.write_text(text.replace(raw, mutated), encoding="utf-8")
        targets.append((key, raw, mutated, manifest[doc_id]["channel"]))
        used.add(doc_id)
        if len(targets) == 120:
            break
    assert {t[3] for t in targets} == {"PORTAL", "EDI", "EMAIL", "SCAN"}
    after = _run(ds)
    read_as_printed = flagged = 0
    for (doc_id, line_id, name), raw, mutated, _ in targets:
        old = before["fields"][(doc_id, line_id, name)]
        new = after["fields"].get((doc_id, line_id, name))
        gated = after["cap"][doc_id]["capture_status"] == "LOW_CONFIDENCE"
        if gated or new is None or new["is_low_confidence"] == "true":
            flagged += 1
            continue
        assert new["raw_text"] == mutated, (doc_id, name)
        assert new["normalized_value"] != old["normalized_value"], f"{doc_id} {name}: original value restored"
        read_as_printed += 1
    assert read_as_printed > 80 and read_as_printed + flagged == len(targets)


@pytest.mark.parametrize("damage", ["smudge", "lookalike", "delete_total", "unknown_trn", "truncate"])
def test_damaged_documents_are_flagged_never_silently_fixed(engine_runs, tmp_path, damage):
    root, _, _ = engine_runs["starter"]
    ds = _copy(root, tmp_path)
    before = _run(ds)
    manifest = read_table(ds / "inbox", "intake_manifest")
    hits = 0
    for m in manifest:
        if m["channel"] not in ("EMAIL", "SCAN") and damage in ("smudge", "lookalike", "delete_total"):
            continue
        path = ds / "inbox" / m["file_path"]
        text = path.read_text(encoding="utf-8")
        gross = before["fields"][(m["doc_id"], "", "header_gross_amount")]["raw_text"]
        trn = before["fields"][(m["doc_id"], "", "vendor_tax_id")]["raw_text"]
        if damage == "smudge" and text.count(gross) == 1:
            text = text.replace(gross, gross[:-1] + "?")
        elif damage == "lookalike" and text.count(gross) == 1 and "0" in gross[-2:]:
            text = text.replace(gross, gross[:-2] + gross[-2:].replace("0", "O"))
        elif damage == "delete_total":
            text = "\n".join(ln for ln in text.split("\n") if gross not in ln) + "\n"
        elif damage == "unknown_trn":
            text = text.replace(trn, "TRN-000000001")
        elif damage == "truncate":
            text = text[: len(text) // 2]
        else:
            continue
        path.write_text(text, encoding="utf-8")
        hits += 1
        if hits == 12:
            break
    assert hits >= 5
    after = _run(ds)
    changed = [d for d, c in after["cap"].items() if c != before["cap"][d]]
    assert changed, "the damage must be visible in the capture"
    exc = {e["invoice_id"]: e["exception_type"] for e in after["exc"]}
    for doc_id in changed:
        c = after["cap"][doc_id]
        if damage == "unknown_trn":
            assert c["vendor_id"] == "" and c["invoice_id"].startswith("INV-VND-00000-")
            assert exc[c["invoice_id"]] == "VENDOR_NOT_FOUND"          # the sender never fills the gap
        else:
            assert c["capture_status"] == "LOW_CONFIDENCE", (damage, doc_id)
            assert exc[c["invoice_id"]] == "EXT_LOW_CONFIDENCE"
        if damage == "lookalike":
            assert after["fields"][(doc_id, "", "header_gross_amount")]["method"] == "OCR_REPAIRED"
