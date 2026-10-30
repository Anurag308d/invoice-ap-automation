"""Command-line interface: python -m invoice_ap <command>.

Implemented: `plan`, `docs`, `policy` (Stage 1), `generate`, `validate --quick` (Stage 2), `run`,
`evaluate` and `explain` (Stages 3-4). The remaining commands are registered
so the planned surface is visible; they exit with status 2 until their stage lands.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .common.paths import DEFAULT_POLICY, DOCS_DIR, SPEC_JSON

PLANNED = {
    "export": ("Write CSV / JSON / SQL seed exports", 5),
    "repro": ("Regenerate twice with the same seed and compare checksums", 5),
    "build-all": ("Build, run, evaluate, validate, export and report for both scales", 5),
    "queue": ("Show an actor role its work queue", 5),
    "dashboard": ("Write the offline HTML dashboard", 5),
}


def _cmd_plan(args: argparse.Namespace) -> int:
    from .generator.allocation import allocate
    from .generator.allocation_report import render_markdown
    if args.scale in ("full", "starter"):
        print(render_markdown())
        return 0
    alloc = allocate(args.scale)
    print(f"scale {alloc.scale}: {alloc.targets}")
    for key in ("categories", "archetypes", "line_histogram", "subscenarios"):
        print(f"{key}: {getattr(alloc, key)}")
    return 0


def _doc_outputs() -> list[tuple[Path, str]]:
    from .spec.render import to_json, to_markdown
    return [(DOCS_DIR / "data_dictionary.md", to_markdown()), (SPEC_JSON, to_json())]


def doc_blocks() -> list[tuple[Path, str, str]]:
    """Generated blocks inside hand-written docs: (file, block name, content)."""
    from .common.policy_render import approval_markdown, routing_markdown
    from .generator.allocation_report import render_markdown
    from .spec.schema_render import keys_markdown, state_machines_markdown
    return [(DOCS_DIR / "data_generation.md", "allocation-tables", render_markdown()),
            (DOCS_DIR / "schema.md", "keys", keys_markdown()),
            (DOCS_DIR / "schema.md", "state-machines", state_machines_markdown()),
            (DOCS_DIR / "business_rules.md", "routing-matrix", routing_markdown()),
            (DOCS_DIR / "business_rules.md", "approval-matrix", approval_markdown())]


def _cmd_docs(args: argparse.Namespace) -> int:
    from .common.docsync import block_in_sync, write_block
    stale: list[str] = []
    for path, content in _doc_outputs():
        current = path.read_text(encoding="utf-8") if path.exists() else None
        if current != content:
            stale.append(str(path))
            if not args.check:
                path.write_text(content, encoding="utf-8", newline="\n")
    for path, name, content in doc_blocks():
        if not block_in_sync(path, name, content):
            stale.append(f"{path} [{name}]")
            if not args.check:
                write_block(path, name, content)
    verb = "stale" if args.check else "rewritten"
    for item in stale:
        print(f"{verb}: {item}")
    print("docs up to date" if not stale else f"{len(stale)} item(s) {verb}")
    return 1 if (args.check and stale) else 0


def _cmd_policy(args: argparse.Namespace) -> int:
    from .common.policy import PolicyError, load_policy
    try:
        pol = load_policy(args.path)
    except PolicyError as exc:
        print(exc, file=sys.stderr)
        return 1
    print(f"{pol.id} {pol.version} (sha256 {pol.sha256[:16]}...) as-of {pol.as_of_date}: valid")
    print(f"  {len(pol.raw['routing']['types'])} routed exception types, "
          f"{len(pol.raw['approval']['bands'])} approval bands")
    return 0


def _cmd_generate(args: argparse.Namespace) -> int:
    import time
    from .generator.build import generate
    started = time.perf_counter()   # duration for the console only; never written to any output
    result = generate(args.scale, args.seed, args.out)
    seconds = time.perf_counter() - started
    t = result.final.tables
    print(f"{result.alloc.scale}: {len(t['vendor'])} vendors, {len(t['purchase_order'])} POs, "
          f"{len(t['purchase_order_line'])} PO lines, {len(t['goods_receipt'])} GRNs, {len(t['invoice'])} invoices "
          f"-> {result.out} in {seconds:.2f}s")
    print(f"baseline: {result.baseline_report['status']} ({result.baseline_report['violations']} violations); "
          f"final: {result.report['status']} ({result.report['violations']} violations, "
          f"{result.report['labelled']} labelled defects reported as expected); oracle == intent")
    return 0


def _cmd_validate(args: argparse.Namespace) -> int:
    from .common.paths import DEFAULT_DATA_DIR
    from .common.policy import load_policy
    from .generator.allocation import allocate
    from .quality.quick import load, validate
    if not args.quick:
        print("the full validation suite is planned for Stage 5; use --quick", file=sys.stderr)
        return 2
    root = Path(args.data) if args.data else DEFAULT_DATA_DIR / args.scale
    report = validate(load(root), load_policy(), allocate(args.scale))
    for item in report["checks"]:
        print(f"{item['status']:4}  {item['check']}: {item['violations']} violations, {item['labelled']} labelled")
    print(f"{report['status'].upper()}: {report['violations']} violations, {report['labelled']} labelled defects")
    return 0 if report["status"] == "pass" else 1


def _root(args: argparse.Namespace) -> Path:
    from .common.paths import DEFAULT_DATA_DIR
    return Path(args.data) if args.data else DEFAULT_DATA_DIR / args.scale


def _cmd_run(args: argparse.Namespace) -> int:
    import time
    from .common.policy import load_policy
    from .engine import run_engine
    root = _root(args)
    started = time.perf_counter()
    summary = run_engine(root / "master", root / "inbox", root / "processed", load_policy())
    print(f"engine: {summary['documents']} documents -> {root / 'processed'} in {time.perf_counter() - started:.2f}s; "
          f"capture review {summary['low_confidence']}, vendor not found {summary['vendor_not_found']}, "
          f"exceptions {summary['exceptions']}")
    return 0


def _cmd_evaluate(args: argparse.Namespace) -> int:
    import json
    from .common.policy import load_policy
    from .evaluation.decisions import acceptance_csv, evaluate_decisions
    from .evaluation.decisions import to_markdown as decisions_md
    from .evaluation.extraction import evaluate, to_markdown
    root = _root(args)
    reports = root / "reports"
    reports.mkdir(parents=True, exist_ok=True)

    def dump(name: str, obj) -> None:
        (reports / name).write_text(json.dumps(obj, indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    manifest = root / "reports" / "source_manifest.json"
    label = json.loads(manifest.read_text(encoding="utf-8"))["scale"] if manifest.exists() else root.name
    report = evaluate(root)
    dump("extraction_evaluation.json", report)
    (reports / "extraction_evaluation.md").write_text(to_markdown(report, f"Extraction evaluation ({label})"),
                                                      encoding="utf-8")
    decisions, acceptance = evaluate_decisions(root, load_policy().as_of_date)
    dump("evaluation.json", {"extraction_summary": {k: v for k, v in report.items() if k != "mismatches"},
                             "decisions": decisions})
    (reports / "evaluation.md").write_text(decisions_md(decisions, f"Decision evaluation ({label})"), encoding="utf-8")
    (reports / "acceptance_per_invoice.csv").write_bytes(acceptance_csv(acceptance))
    bad = len(report["non_degraded_documents_with_mismatch"])
    acc = decisions["acceptance"]
    print(f"extraction: {report['documents_exact']}/{report['documents']} documents exact, field match "
          f"{report['field_match_rate']}, silent errors {report['silent_errors']}, degraded scans flagged "
          f"{report['degraded_scans_flagged']}/{report['degraded_scans']}, non-degraded mismatches {bad}")
    print(f"decisions: issue types {decisions['agreement']['issue_types']}, primary {decisions['agreement']['primary_issue']}, "
          f"final status {decisions['agreement']['final_status']}, duplicate pairs {decisions['duplicates']['correct_pairs']}/"
          f"{decisions['duplicates']['expected_pairs']}, unsafe payments "
          f"{decisions['payments']['blocked_or_unapproved_with_payment']}, STP {decisions['kpis']['stp_rate']}")
    print(f"acceptance (R34a-e): pass {acc['pass']}/{acc['invoices']}, fail {acc['fail']} "
          f"(capture review flagged {acc['r34a_flagged_capture_review']}) -> {reports}")
    ok = report["silent_errors"] == 0 and bad == 0 and acc["fail"] == 0 \
        and decisions["payments"]["blocked_or_unapproved_with_payment"] == 0
    return 0 if ok else 1


def _cmd_explain(args: argparse.Namespace) -> int:
    from .engine.explain import explain
    try:
        print(explain(_root(args) / "processed", args.invoice_id), end="")
    except KeyError as err:
        print(err.args[0], file=sys.stderr)
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m invoice_ap", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("plan", help="Print the exact volume and scenario allocation")
    p.add_argument("--scale", default="full", help="full | starter | numeric factor (default full)")
    p.set_defaults(func=_cmd_plan)
    p = sub.add_parser("docs", help="Regenerate the data dictionary and generated doc tables")
    p.add_argument("--check", action="store_true", help="Only report stale files (exit 1 if any)")
    p.set_defaults(func=_cmd_docs)
    p = sub.add_parser("policy", help="Validate the policy config and print a summary")
    p.add_argument("--path", type=Path, default=DEFAULT_POLICY)
    p.set_defaults(func=_cmd_policy)
    p = sub.add_parser("generate", help="Generate master data, source invoices and ground truth")
    p.add_argument("--scale", default="starter", help="starter | full | numeric factor (default starter)")
    p.add_argument("--seed", type=int, default=20261022)
    p.add_argument("--out", default=None, help="output folder (default data/<scale>, git-ignored until Stage 5)")
    p.set_defaults(func=_cmd_generate)
    p = sub.add_parser("validate", help="Self-check a built dataset (--quick now; full suite in Stage 5)")
    p.add_argument("--quick", action="store_true")
    p.add_argument("--scale", default="starter")
    p.add_argument("--data", default=None, help="dataset folder (default data/<scale>)")
    p.set_defaults(func=_cmd_validate)
    for name, func, help_text in (("run", _cmd_run, "Run the AP engine on master data and the inbox only"),
                                  ("evaluate", _cmd_evaluate, "Compare engine output with source and ground truth"),
                                  ("explain", _cmd_explain, "Show one invoice's decision, exceptions, events and trace")):
        p = sub.add_parser(name, help=help_text)
        if name == "explain":
            p.add_argument("invoice_id")
        p.add_argument("--scale", default="starter")
        p.add_argument("--data", default=None, help="dataset folder (default data/<scale>)")
        p.set_defaults(func=func)
    for name, (help_text, stage) in PLANNED.items():
        p = sub.add_parser(name, help=f"{help_text} (planned: Stage {stage})")
        p.set_defaults(func=lambda a, n=name, s=stage: _planned(n, s))
    return parser


def _planned(name: str, stage: int) -> int:
    print(f"'{name}' is planned for Stage {stage} and is not implemented yet.", file=sys.stderr)
    return 2


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)
