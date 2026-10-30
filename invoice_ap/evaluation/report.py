"""Write the evaluation reports of one built dataset (used by `evaluate` and `build`)."""
from __future__ import annotations

import json
from pathlib import Path

from .decisions import acceptance_csv, evaluate_decisions
from .decisions import to_markdown as decisions_md
from .extraction import evaluate
from .extraction import to_markdown as extraction_md


def _dump(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def write_reports(root: Path, policy) -> tuple[dict, dict]:
    root = Path(root)
    reports = root / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    manifest = reports / "source_manifest.json"
    label = json.loads(manifest.read_text(encoding="utf-8")).get("scale", root.name) if manifest.exists() else root.name
    extraction = evaluate(root)
    _dump(reports / "extraction_evaluation.json", extraction)
    (reports / "extraction_evaluation.md").write_text(extraction_md(extraction, f"Extraction evaluation ({label})"),
                                                      encoding="utf-8")
    decisions, acceptance = evaluate_decisions(root, policy.as_of_date)
    _dump(reports / "evaluation.json", {"extraction_summary": {k: v for k, v in extraction.items() if k != "mismatches"},
                                        "decisions": decisions})
    (reports / "evaluation.md").write_text(decisions_md(decisions, f"Decision evaluation ({label})"), encoding="utf-8")
    (reports / "acceptance_per_invoice.csv").write_bytes(acceptance_csv(acceptance))
    return extraction, decisions


def passed(extraction: dict, decisions: dict) -> bool:
    return (extraction["silent_errors"] == 0 and not extraction["non_degraded_documents_with_mismatch"]
            and decisions["acceptance"]["fail"] == 0 and decisions["payments"]["blocked_or_unapproved_with_payment"] == 0)
