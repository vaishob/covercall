"""Evaluation comparison runner: `python -m evals.compare --set golden|heldout` (§3.9, §10.1, §13.2).

Runs every scenario in the target dataset (`golden` or `heldout`) through both
CoverCall (`policy.compile_cpsat.solve` + `policy.validate.validate_assignment`)
and the naive baseline (`baseline.most_reliable_first.run_baseline_scenario`),
prints a comparison table of median/total overtime cost (SGD, synthetic),
rule violations, and simulated time to fill (minutes), and exits nonzero if
CoverCall has any rule violation or solver/validator disagreement.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Any

import yaml

from baseline.most_reliable_first import run_baseline_scenario
from datagen import build_synthetic_dataset
from policy.compile_cpsat import PlanDisagreement, load_company_config, load_rules, solve


def run_covercall_scenario(
    scenario: dict[str, Any],
    staff_list: list[dict[str, Any]],
    ledgers: dict[str, dict[str, Any]],
    travel_cache: dict[str, Any],
    rules: list[dict[str, Any]],
    cfg: dict[str, Any],
) -> dict[str, Any]:
    gap = scenario["gap"]
    outlet = str(gap["outlet"])
    personas = scenario.get("personas") or {}

    cands: list[dict[str, Any]] = []
    for s in staff_list:
        c = dict(s)
        sid = str(c["staff_id"])
        c["ledger"] = dict(ledgers.get(f"{sid}_202611") or {})
        c["travel_min"] = int(
            (travel_cache.get("staff_to_outlet_min", {}).get(sid, {}) or {}).get(outlet, 20)
        )
        c["shift_context"] = {
            "days_since_last_rest_day": int(c["ledger"].get("days_since_last_rest_day", 2)),
            "hours_since_prev_shift_end": 14.0,
            "hours_until_next_shift_start": 14.0,
            "other_keyholder_present": True,
        }
        for ov in scenario.get("overrides") or []:
            if ov.get("staff") == sid:
                if "ledger" in ov:
                    c["ledger"].update(ov["ledger"])
                if "shift_context" in ov:
                    c["shift_context"].update(ov["shift_context"])
        cands.append(c)

    unavailable: set[str] = set()
    counter_split_at: str | None = None
    elapsed_min = 0.0

    # Cascade loop: solve -> offer top candidate -> handle persona response -> re-solve if needed
    while True:
        ctx = {
            "candidates": cands,
            "now": scenario["now"],
            "seed": scenario["seed"],
            "unavailable_staff_ids": sorted(unavailable),
            "counter_split_at": counter_split_at,
        }
        plan_res = solve(gap, ctx, rules, cfg)
        if not plan_res.candidates:
            return {
                "scenario_id": scenario["id"],
                "outcome": "escalated",
                "assigned_staff_id": None,
                "overtime_cost_sgd": 0.0,
                "total_cost_sgd": 0.0,
                "violations": 0,
                "disagreements": 0,
                "time_to_fill_min": round(elapsed_min, 2),
                "synthetic": True,
            }

        top = plan_res.candidates[0]
        primary_sid = top.segments[0]["staff_id"]
        p_info = personas.get(primary_sid) or {}
        will = p_info.get("will", "accept")

        if will == "decline":
            elapsed_min += 1.2
            unavailable.add(primary_sid)
            continue
        if will == "silent":
            elapsed_min += 3.0
            unavailable.add(primary_sid)
            continue
        if will == "counter" and counter_split_at is None:
            elapsed_min += 1.5
            win = p_info.get("window") or ["09:00", "15:00"]
            for c in cands:
                if c["staff_id"] == primary_sid:
                    c["available_window"] = win
            if win[0] > gap["start"]:
                counter_split_at = win[0]
            else:
                unavailable.add(primary_sid)
            continue

        # Accepted! Verify zero hard violations across all segments
        elapsed_min += 1.1
        viol_count = sum(
            1
            for r in top.rules_checked
            if r.get("status") == "violation" and r.get("kind") in ("hard", "data_gate")
        )
        return {
            "scenario_id": scenario["id"],
            "outcome": "filled",
            "assigned_staff_id": top.staff_id,
            "overtime_cost_sgd": top.overtime_cost_sgd,
            "total_cost_sgd": top.total_cost_sgd,
            "violations": viol_count,
            "disagreements": 1 if plan_res.disagreement else 0,
            "time_to_fill_min": round(elapsed_min, 2),
            "synthetic": True,
        }


def compare_dataset(dataset_name: str = "golden") -> dict[str, Any]:
    data_dir = Path("data")
    if not (data_dir / "staff.json").exists():
        build_synthetic_dataset(seed=42)

    scen_dir = Path("evals/datasets") / dataset_name
    scen_files = sorted(scen_dir.glob("*.yaml"))
    if not scen_files:
        build_synthetic_dataset(seed=42)
        scen_files = sorted(scen_dir.glob("*.yaml"))

    staff_list = json.loads((data_dir / "staff.json").read_text(encoding="utf-8"))
    ledgers = json.loads((data_dir / "ledgers.json").read_text(encoding="utf-8"))
    travel_cache = json.loads((data_dir / "travel_cache.json").read_text(encoding="utf-8"))
    rules = load_rules()
    cfg = load_company_config()

    cc_ot_costs: list[float] = []
    bl_ot_costs: list[float] = []
    cc_times: list[float] = []
    bl_times: list[float] = []
    cc_violations = 0
    bl_violations = 0
    cc_disagreements = 0

    for sf in scen_files:
        scen = yaml.safe_load(sf.read_text(encoding="utf-8"))
        try:
            cc_res = run_covercall_scenario(scen, staff_list, ledgers, travel_cache, rules, cfg)
        except PlanDisagreement:
            cc_disagreements += 1
            cc_res = {
                "overtime_cost_sgd": 0.0,
                "violations": 1,
                "disagreements": 1,
                "time_to_fill_min": 0.0,
            }
        bl_res = run_baseline_scenario(scen, staff_list, ledgers, travel_cache, rules)

        cc_ot_costs.append(float(cc_res["overtime_cost_sgd"]))
        bl_ot_costs.append(float(bl_res["overtime_cost_sgd"]))
        cc_times.append(float(cc_res["time_to_fill_min"]))
        bl_times.append(float(bl_res["time_to_fill_min"]))
        cc_violations += int(cc_res["violations"])
        bl_violations += int(bl_res["violations"])
        cc_disagreements += int(cc_res.get("disagreements", 0))

    cc_median_ot = round(statistics.median(cc_ot_costs), 2) if cc_ot_costs else 0.0
    bl_median_ot = round(statistics.median(bl_ot_costs), 2) if bl_ot_costs else 0.0
    cc_total_ot = round(sum(cc_ot_costs), 2)
    bl_total_ot = round(sum(bl_ot_costs), 2)
    cc_median_t = round(statistics.median(cc_times), 2) if cc_times else 0.0
    bl_median_t = round(statistics.median(bl_times), 2) if bl_times else 0.0

    return {
        "dataset": dataset_name,
        "scenarios": len(scen_files),
        "synthetic": True,
        "covercall": {
            "median_overtime_cost_sgd": cc_median_ot,
            "total_overtime_cost_sgd": cc_total_ot,
            "rule_violations": cc_violations,
            "solver_validator_disagreements": cc_disagreements,
            "median_time_to_fill_min": cc_median_t,
        },
        "baseline": {
            "median_overtime_cost_sgd": bl_median_ot,
            "total_overtime_cost_sgd": bl_total_ot,
            "rule_violations": bl_violations,
            "median_time_to_fill_min": bl_median_t,
        },
        "overtime_saved_sgd": {
            "median_saved_sgd": round(bl_median_ot - cc_median_ot, 2),
            "total_saved_sgd": round(bl_total_ot - cc_total_ot, 2),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compare CoverCall against most-reliable-first baseline")
    parser.add_argument("--set", dest="dataset", choices=["golden", "heldout"], default="golden")
    parser.add_argument("--json", action="store_true", help="Output JSON report")
    args = parser.parse_args(argv)

    report = compare_dataset(args.dataset)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        cc = report["covercall"]
        bl = report["baseline"]
        sv = report["overtime_saved_sgd"]
        cc_med_ot = f"S${cc['median_overtime_cost_sgd']:.2f}"
        bl_med_ot = f"S${bl['median_overtime_cost_sgd']:.2f}"
        sv_med_ot = f"S${sv['median_saved_sgd']:.2f}"
        cc_tot_ot = f"S${cc['total_overtime_cost_sgd']:.2f}"
        bl_tot_ot = f"S${bl['total_overtime_cost_sgd']:.2f}"
        sv_tot_ot = f"S${sv['total_saved_sgd']:.2f}"
        cc_ttf = f"{cc['median_time_to_fill_min']:.2f} min"
        bl_ttf = f"{bl['median_time_to_fill_min']:.2f} min"
        sv_ttf = f"{bl['median_time_to_fill_min'] - cc['median_time_to_fill_min']:.2f} min"

        print(f"=== CoverCall vs. Baseline ({report['dataset']} set, n={report['scenarios']} — All data is synthetic) ===")
        print(f"{'Metric (Synthetic SGD)':<38} | {'CoverCall':>14} | {'Baseline (Reliable-1st)':>24} | {'Delta / Saved':>15}")
        print("-" * 100)
        print(f"{'Median overtime cost per decision':<38} | {cc_med_ot:>14} | {bl_med_ot:>24} | {sv_med_ot:>15}")
        print(f"{'Total overtime cost across set':<38} | {cc_tot_ot:>14} | {bl_tot_ot:>24} | {sv_tot_ot:>15}")
        print(
            f"{'Rule violations (P0 pass = 0)':<38} | "
            f"{cc['rule_violations']:>14} | "
            f"{bl['rule_violations']:>24} | "
            f"{bl['rule_violations'] - cc['rule_violations']:>15}"
        )
        print(
            f"{'Solver/validator disagreements (P0)':<38} | "
            f"{cc['solver_validator_disagreements']:>14} | "
            f"{'N/A':>24} | "
            f"{'0':>15}"
        )
        print(f"{'Median simulated time to fill (min)':<38} | {cc_ttf:>14} | {bl_ttf:>24} | {sv_ttf:>15}")
        print("-" * 100)
        print("All data is synthetic.")

    if report["covercall"]["rule_violations"] > 0 or report["covercall"]["solver_validator_disagreements"] > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
