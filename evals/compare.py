"""``python -m evals.compare --set golden|heldout`` (§3.9, §10.1, §13.2).

Runs every scenario through CoverCall (solver + validator cascade) and the most-reliable-first
baseline with the same personas and seeds, then prints overtime cost (synthetic SGD) and rule
violations side by side. Exit code 1 if CoverCall has any rule violation, any solver/validator
disagreement, or any result that differs from the scenario's computed ``expect`` block.
All data is synthetic.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Any

import yaml

from baseline.most_reliable_first import run_baseline
from datagen.loader import load_data
from evals.cascade_sim import run_covercall
from policy.compile_cpsat import load_company_config, load_rules


def _sgd(cents: float) -> str:
    return f"S${cents / 100:,.2f}"


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ot = [r["overtime_cost_cents"] for r in rows]
    total = [r["cost_breakdown"]["total_cents"] for r in rows]
    return {
        "filled": sum(1 for r in rows if r["outcome"] == "filled"),
        "median_overtime_cents": statistics.median(ot) if ot else 0,
        "total_overtime_cents": sum(ot),
        "median_total_cost_cents": statistics.median(total) if total else 0,
        "total_cost_cents": sum(total),
        "rule_violations": sum(r["violations"] for r in rows),
        "scenarios_with_violations": sum(1 for r in rows if r["violations"]),
    }


def compare_dataset(name: str, data_dir: str | Path = "data") -> dict[str, Any]:
    scen_dir = Path("evals/datasets") / name
    files = sorted(scen_dir.glob("*.yaml"))
    if not files:
        raise SystemExit(f"no scenarios in {scen_dir}; run `python -m datagen build --seed 42`")
    data = load_data(data_dir)
    rules = load_rules()
    cfg = load_company_config()
    cc_rows, bl_rows, mismatches = [], [], []
    for f in files:
        scen = yaml.safe_load(f.read_text(encoding="utf-8"))
        cc = run_covercall(scen, data, rules, cfg)
        bl = run_baseline(scen, data, rules, cfg)
        cc_rows.append(cc)
        bl_rows.append(bl)
        exp = scen.get("expect") or {}
        if (cc["outcome"], cc["assignment"], cc["overtime_cost_cents"]) != (
                exp.get("outcome"), exp.get("assignment"), exp.get("overtime_cost_cents")):
            mismatches.append(scen["id"])
    return {
        "dataset": name,
        "scenarios": len(files),
        "synthetic": True,
        "covercall": dict(_summary(cc_rows),
                          solver_validator_disagreements=sum(r["disagreements"] for r in cc_rows),
                          held=sum(1 for r in cc_rows if r["outcome"] == "held"),
                          escalated=sum(1 for r in cc_rows if r["outcome"] == "escalated")),
        "baseline": dict(_summary(bl_rows),
                         unfilled=sum(1 for r in bl_rows if r["outcome"] == "unfilled")),
        "expect_mismatches": mismatches,
        "cases": [{"id": c["scenario_id"], "covercall": {k: c[k] for k in (
            "outcome", "assignment", "overtime_cost_cents", "violated_rules")},
            "baseline": {k: b[k] for k in ("outcome", "assignment", "overtime_cost_cents",
                                           "violated_rules")}}
            for c, b in zip(cc_rows, bl_rows, strict=True)],
    }


def render(report: dict[str, Any]) -> str:
    cc, bl = report["covercall"], report["baseline"]
    rows = [
        ("Gaps filled", f"{cc['filled']}/{report['scenarios']}", f"{bl['filled']}/{report['scenarios']}"),
        ("Median overtime cost per gap", _sgd(cc["median_overtime_cents"]),
         _sgd(bl["median_overtime_cents"])),
        ("Total overtime cost", _sgd(cc["total_overtime_cents"]), _sgd(bl["total_overtime_cents"])),
        ("Total incremental labour cost", _sgd(cc["total_cost_cents"]), _sgd(bl["total_cost_cents"])),
        ("Rule violations (hard rules)", str(cc["rule_violations"]), str(bl["rule_violations"])),
        ("Scenarios with a violation", str(cc["scenarios_with_violations"]),
         str(bl["scenarios_with_violations"])),
        ("Solver/validator disagreements", str(cc["solver_validator_disagreements"]), "n/a"),
    ]
    width = max(len(r[0]) for r in rows)
    lines = [
        f"CoverCall vs most-reliable-first baseline: {report['dataset']} set, "
        f"n={report['scenarios']} (all data is synthetic; costs in synthetic SGD)",
        f"{'Metric':<{width}} | {'CoverCall':>14} | {'Baseline':>14}",
        "-" * (width + 36),
    ]
    lines += [f"{a:<{width}} | {b:>14} | {c:>14}" for a, b, c in rows]
    lines.append("-" * (width + 36))
    lines.append(f"CoverCall escalated: {cc['escalated']}, held: {cc['held']}; "
                 f"baseline unfilled: {bl['unfilled']}")
    lines.append(f"Results differing from scenario expect blocks: {len(report['expect_mismatches'])}"
                 + (f" {report['expect_mismatches']}" if report["expect_mismatches"] else ""))
    lines.append("All data is synthetic.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--set", dest="dataset", choices=["golden", "heldout"], default="golden")
    parser.add_argument("--json", action="store_true", help="print the full JSON report")
    args = parser.parse_args(argv)
    report = compare_dataset(args.dataset)
    print(json.dumps(report, indent=2) if args.json else render(report))
    cc = report["covercall"]
    failed = cc["rule_violations"] > 0 or cc["solver_validator_disagreements"] > 0 \
        or bool(report["expect_mismatches"])
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
