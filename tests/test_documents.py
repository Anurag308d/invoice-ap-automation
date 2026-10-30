"""Documents: four heterogeneous channel formats, vendor templates with recoverable variation,
the manifest describes each file exactly, and documents carry no labels or vendor shortcuts."""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter

import pytest

from invoice_ap.common import enums
from invoice_ap.common.enums import EXCEPTION_TYPES, SCENARIO_CATEGORIES, SCENARIO_CODES


@pytest.fixture(params=["starter", "full"])
def built(request, builds):
    return builds[request.param]


def _docs(result):
    root = result.out / "inbox"
    return {m["doc_id"]: (m, (root / m["file_path"]).read_bytes()) for m in result.final.tables["intake_manifest"]}


def test_manifest_describes_every_rendered_file(built):
    result, t = built
    files = sorted(p.relative_to(result.out / "inbox").as_posix() for p in (result.out / "inbox" / "documents").rglob("*")
                   if p.is_file())
    assert files == sorted(m["file_path"] for m in t["intake_manifest"])
    for m in t["intake_manifest"]:
        data = (result.out / "inbox" / m["file_path"]).read_bytes()
        assert m["file_sha256"] == hashlib.sha256(data).hexdigest() and int(m["file_bytes"]) == len(data)
        assert m["file_format"] == enums.FILE_FORMATS[m["channel"]]
        assert m["file_path"].startswith(f"documents/{m['channel'].lower()}/{m['doc_id']}.")


def test_four_heterogeneous_formats_are_used(built):
    result, _ = built
    seen = Counter()
    for m, data in _docs(result).values():
        text = data.decode("utf-8")
        if m["channel"] == "PORTAL":
            obj = json.loads(text)
            seen["portal " + ("v1" if "schema" in obj else "v2")] += 1
        elif m["channel"] == "EDI":
            assert text.startswith("UNB")
            seen[f"edi sep {text[3]}"] += 1
            seen["edi implied" if "IMP2" in text.split("\n")[0][:12] else "edi decimal"] += 1
        elif m["channel"] == "EMAIL":
            assert text.startswith("From: ") and "\n\n" in text
            seen["email forwarded" if "Forwarded message" in text else "email direct"] += 1
        else:
            seen["scan"] += 1
    assert {"portal v1", "portal v2", "email direct", "scan"} <= set(seen)
    assert {"edi decimal", "edi implied"} & set(seen)


def test_full_scale_shows_every_template_variant(builds):
    result, _ = builds["full"]
    texts = [(m["channel"], d.decode("utf-8")) for m, d in _docs(result).values()]
    edi = {t[3] for ch, t in texts if ch == "EDI"}
    assert edi == {"*", "|", "^", "+"}
    assert any(ch == "EDI" and "~" in t and t.count("\n") == 1 for ch, t in texts)       # one-line EDI
    assert {"IMP2" in t.split("\n")[0][:12] for ch, t in texts if ch == "EDI"} == {True, False}
    email = [t for ch, t in texts if ch == "EMAIL"]
    assert any("| ---" in t or "|---|" in t for t in email) and any(re.search(r"^Item 1$", t, re.M) for t in email)
    assert sum("Forwarded message" in t for t in email) == 35
    scans = [t for ch, t in texts if ch == "SCAN"]
    assert any("-- Page 1 of" in t for t in scans), "a multi-page scan table"
    assert any(re.search(r"\S: \S.*\s{3,}\S+: ", t) for t in scans), "two label pairs on one line"
    dates = Counter()
    for _, t in texts:
        for pattern, name in ((r"\d{2}/\d{2}/2026", "dmy/"), (r"\d{2}\.\d{2}\.2026", "dmy."), (r"\d{2} [A-Z][a-z]{2} 2026", "d mon"),
                              (r"[A-Z][a-z]+ \d{2}, 2026", "month d"), (r"\d{1,2},\d{2},\d{3}\.\d{2}", "indian grouping")):
            dates[name] += bool(re.search(pattern, t))
    assert all(dates[k] for k in ("dmy/", "dmy.", "d mon", "month d", "indian grouping"))


def test_documents_carry_no_labels_or_engine_shortcuts(built):
    result, t = built
    words = set(SCENARIO_CODES) | set(SCENARIO_CATEGORIES) | set(EXCEPTION_TYPES) | {"resubmission", "duplicate",
                                                                                      "degraded", "ground truth"}
    for m, data in _docs(result).values():
        text = data.decode("utf-8")
        low = text.lower()
        for w in words:
            assert w.lower() not in low, f"{m['doc_id']} contains {w}"
        assert "INV-VND-" not in text, "documents never print the engine's invoice_id"


def test_degraded_scans_are_scans_with_one_unreadable_field(builds):
    result, t = builds["full"]
    gt = {g["doc_id"]: g for g in t["ground_truth"]}
    degraded = [m for m in t["intake_manifest"] if gt[m["doc_id"]]["scenario_category"] == "CAPTURE_REVIEW"]
    assert len(degraded) == 10 and {m["channel"] for m in degraded} == {"SCAN"}
    for m in degraded:
        text = (result.out / "inbox" / m["file_path"]).read_text(encoding="utf-8")
        assert re.search(r"[?#~]|\d[OlSBZ]|[OlSBZ]\d", text), m["doc_id"]
