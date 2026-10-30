"""One-command build (R35, A-71) and the reproducibility check (R35b, A-54).

`build`: generate -> run (engine on master + inbox only) -> evaluate -> validate (full suite) ->
export (CSV / JSON / SQL) -> dashboard -> manifest, for one scale.
`build_all`: both scales into data/<scale>, then a reproducibility check per scale.
`repro`: two more builds with the same seed in separate folders and separate processes
(PYTHONHASHSEED 1 and 2), plus one with a different seed; the report compares every file's SHA-256
and row count. It contains no paths and no times, so it is itself reproducible.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from .common.paths import DEFAULT_DATA_DIR, REPO_ROOT
from .common.policy import Policy, load_policy
from .engine import run_engine
from .evaluation.report import passed, write_reports
from .export.exports import write_exports
from .generator.allocation import allocate
from .generator.build import generate
from .quality.suite import run_suite
from .quality.suite import to_markdown as suite_md
from .report.dashboard import build_dashboard
from .report.manifest import file_table, tree_digest, write_manifest

SCALES = ("starter", "full")
CORE_TABLES = ("master/vendor.csv", "master/purchase_order.csv", "master/purchase_order_line.csv",
               "master/goods_receipt.csv", "source/invoice.csv", "ground_truth/ground_truth.csv")


def build(scale: str, seed: int, out: Path, policy: Policy | None = None, log=print) -> dict:
    policy = policy or load_policy()
    out = Path(out)
    steps, started = {}, time.perf_counter()

    def step(name, fn):
        t = time.perf_counter()
        result = fn()
        steps[name] = round(time.perf_counter() - t, 2)
        return result
    step("generate", lambda: generate(scale, seed, out, policy))
    step("run", lambda: run_engine(out / "master", out / "inbox", out / "processed", policy))
    extraction, decisions = step("evaluate", lambda: write_reports(out, policy))
    suite = step("validate", lambda: run_suite(out, policy, allocate(scale)))
    (out / "reports" / "validation_summary.json").write_text(
        json.dumps(suite, indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    (out / "reports" / "validation_summary.md").write_text(suite_md(suite, f"Validation summary ({scale})"),
                                                           encoding="utf-8")
    step("export", lambda: write_exports(out))
    step("dashboard", lambda: (out / "reports" / "dashboard.html").write_bytes(build_dashboard(out, policy)))
    manifest = step("manifest", lambda: write_manifest(out, policy))
    ok = suite["status"] == "pass" and passed(extraction, decisions)
    log(f"{scale}: built in {time.perf_counter() - started:.1f}s {steps}; validation {suite['status']}, "
        f"evaluation {'pass' if ok else 'FAIL'}; {manifest['totals']['files']} files, "
        f"{manifest['totals']['bytes'] / 1e6:.1f} MB ({manifest['totals']['committed_bytes'] / 1e6:.1f} MB committed)")
    return {"ok": ok, "manifest": manifest}


def _subprocess_build(scale: str, seed: int, out: Path, hash_seed: str) -> None:
    env = dict(os.environ, PYTHONHASHSEED=hash_seed)
    subprocess.run([sys.executable, "-m", "invoice_ap", "build", "--scale", scale, "--seed", str(seed), "--out", str(out)],
                   cwd=REPO_ROOT, env=env, check=True, capture_output=True)


def repro(scale: str, seed: int, target: Path | None = None, log=print) -> dict:
    """Rebuild twice (same seed, different hash seeds) and once with seed + 1; compare with each other
    and with the build at `target` when given. Writes target/reports/reproducibility.{json,md}."""
    with tempfile.TemporaryDirectory(prefix="invoice-ap-repro-") as tmp:
        tmp = Path(tmp)
        for name, s, h in (("a", seed, "1"), ("b", seed, "2"), ("other", seed + 1, "1")):
            _subprocess_build(scale, s, tmp / name, h)
        a, b, other = (file_table(tmp / n) for n in ("a", "b", "other"))
    differing = sorted(k for k in a.keys() | b.keys() if a.get(k, {}).get("sha256") != b.get(k, {}).get("sha256"))
    rows_a = {k: v.get("rows") for k, v in a.items() if "rows" in v}
    report = {
        "scale": scale, "seed": seed,
        "same_seed": {"files": len(a), "identical_files": len(a) - len(differing), "differing_files": differing,
                      "row_counts_identical": rows_a == {k: v.get("rows") for k, v in b.items() if "rows" in v},
                      "tree_sha256": tree_digest(a), "hash_seeds": ["1", "2"]},
        "different_seed": {"seed": seed + 1, "tree_sha256": tree_digest(other),
                           "core_row_counts_equal": all(a[t]["rows"] == other[t]["rows"] for t in CORE_TABLES),
                           "core_tables_differ": all(a[t]["sha256"] != other[t]["sha256"] for t in CORE_TABLES)},
        "core_row_counts": {t: a[t]["rows"] for t in CORE_TABLES},
    }
    if target is not None:
        main = file_table(target)
        report["matches_this_build"] = {"tree_sha256": tree_digest(main), "identical": main == a}
    report["pass"] = (not differing and report["same_seed"]["row_counts_identical"]
                      and report["different_seed"]["core_row_counts_equal"]
                      and report["different_seed"]["core_tables_differ"]
                      and report.get("matches_this_build", {}).get("identical", True))
    if target is not None:
        reports = Path(target) / "reports"
        (reports / "reproducibility.json").write_text(json.dumps(report, indent=1, sort_keys=True) + "\n",
                                                      encoding="utf-8")
        (reports / "reproducibility.md").write_text(_repro_md(report), encoding="utf-8")
    log(f"{scale}: reproducibility {'PASS' if report['pass'] else 'FAIL'}; {report['same_seed']['identical_files']}/"
        f"{report['same_seed']['files']} files identical across two builds; tree {report['same_seed']['tree_sha256'][:16]}")
    return report


def _repro_md(r: dict) -> str:
    s, d = r["same_seed"], r["different_seed"]
    out = [f"# Reproducibility ({r['scale']}, seed {r['seed']})", "", f"Result: **{'PASS' if r['pass'] else 'FAIL'}**", "",
           "| Check | Result |", "|---|---|",
           f"| Two builds, same seed, PYTHONHASHSEED 1 vs 2 | {s['identical_files']} of {s['files']} files byte-identical |",
           f"| Row counts identical | {s['row_counts_identical']} |",
           f"| Tree SHA-256 (sorted path:sha256 list) | `{s['tree_sha256']}` |"]
    if "matches_this_build" in r:
        out.append(f"| Equals the build in this folder | {r['matches_this_build']['identical']} |")
    out += [f"| Seed {d['seed']}: core row counts equal | {d['core_row_counts_equal']} |",
            f"| Seed {d['seed']}: core tables differ | {d['core_tables_differ']} |",
            f"| Seed {d['seed']}: tree SHA-256 | `{d['tree_sha256']}` |", "", "Core row counts:", "",
            "| File | Rows |", "|---|---|"] + [f"| {k} | {v} |" for k, v in r["core_row_counts"].items()]
    return "\n".join(out) + "\n"


def build_all(seed: int, data_dir: Path = DEFAULT_DATA_DIR, check: bool = True, log=print) -> bool:
    ok = True
    for scale in SCALES:
        out = Path(data_dir) / scale
        result = build(scale, seed, out, log=log)
        ok &= result["ok"]
        if check:
            ok &= repro(scale, seed, out, log=log)["pass"]
    return ok
