"""Command-line interface: python -m invoice_ap <command>.

Stage 1 implements `plan`, `docs` and `policy`. The remaining commands are registered so the planned
surface is visible; they exit with status 2 until their stage lands (see docs/architecture.md).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .common.paths import DEFAULT_POLICY, DOCS_DIR, SPEC_JSON

PLANNED = {
    "run": ("Run the AP engine on master data and the inbox only", 3),
    "evaluate": ("Compare engine output with ground truth and source invoices", 4),
    "export": ("Write CSV / JSON / SQL seed exports", 5),
    "repro": ("Regenerate twice with the same seed and compare checksums", 5),
    "build-all": ("Build, run, evaluate, validate, export and report for both scales", 5),
    "queue": ("Show an actor role its work queue", 5),
    "explain": ("Show the decision trace of one invoice", 4),
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
