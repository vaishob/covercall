"""``python -m evals.compare --set golden|heldout`` (§3.9, §10.1, §13.2).

Runs every scenario through CoverCall (the coverage-cascade state machine via the local driver:
api routes, solver + validator, simulated clock and personas) and the most-reliable-first baseline
with the same personas and seeds. Prints overtime cost (synthetic SGD), rule violations and
simulated time to fill side by side. Exit code 1 if CoverCall has any rule violation, any
solver/validator disagreement, any other P0 counter above zero, or any result that differs from the
scenario's computed ``expect`` block. All data is synthetic.
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
from evals.runners.local_cascade import LocalRun
from policy.compile_cpsat import load_company_config, load_rules


def _sgd(cents: float) -> str:
    return f"S${cents / 100:,.2f}"


def _mins(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.2f}"


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ot = [r["overtime_cost_cents"] for r in rows]
    total = [r["cost_breakdown"]["total_cents"] for r in rows]
    ttf = [r["time_to_fill_min"] for r in rows if r["outcome"] == "filled" and r["time_to_fill_min"] is not None]
    return {
        "filled": sum(1 for r in rows if r["outcome"] == "filled"),
        "median_time_to_fill_min": statistics.median(ttf) if ttf else None,
        "median_overtime_cents": statistics.median(ot) if ot else 0,
        "total_overtime_cents": sum(ot),
        "median_total_cost_cents": statistics.median(total) if total else 0,
        "total_cost_cents": sum(total),
        "rule_violations": sum(r["violations"] for r in rows),
        "late_arrivals": sum(r.get("late_arrivals", 0) for r in rows),
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
        cc = LocalRun(scen, data, cfg, rules).run()
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
                          held=sum(1 for r in cc_rows if r["state"] == "HELD"),
                          escalated=sum(1 for r in cc_rows if r["state"] == "RESOLVED"),
                          chain_failures=sum(1 for r in cc_rows if not r["verify_chain"]["ok"]),
                          p0={k: sum(r["p0"][k] for r in cc_rows) for k in cc_rows[0]["p0"]}),
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
        ("Median time to fill (simulated min)", _mins(cc["median_time_to_fill_min"]),
         _mins(bl["median_time_to_fill_min"])),
        ("Fills arriving after shift start", str(cc["late_arrivals"]), str(bl["late_arrivals"])),
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
    lines.append(f"CoverCall escalated then resolved: {cc['escalated']}, held: {cc['held']}; "
                 f"baseline unfilled: {bl['unfilled']}")
    lines.append(f"CoverCall P0 counters: {cc['p0']}; event chains failing verify_chain: "
                 f"{cc['chain_failures']}")
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
        or any(cc["p0"].values()) or cc["chain_failures"] > 0 or bool(report["expect_mismatches"])
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
