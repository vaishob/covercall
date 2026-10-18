"""Scenario generation in the §8.4 format, with ``expect`` computed by solver + validator.

``S-017`` is written exactly as §8.4 gives it. ``S-002`` is the "Nobody replies" journey (J3).
Every other scenario is an absence taken from a real rostered shift in the generated data.
Held-out scenarios use a separate random stream and are never used for tuning (§8.5).
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import yaml

from datagen.loader import load_data

S017: dict[str, Any] = {
    "id": "S-017",
    "description": "Bugis opener sick; nearest barista is near the overtime cap",
    "now": "2026-11-03T06:02:00+08:00",
    "seed": 17,
    "gap": {"outlet": "bugis", "station": "barista", "start": "07:00", "end": "15:00",
            "absent": "stf_011"},
    "overrides": [{"staff": "stf_004", "ledger": {"ot_hours_used": 70}}],
    "personas": {
        "stf_019": {"will": "decline"},
        "stf_022": {"will": "counter", "window": ["09:00", "15:00"]},
        "stf_008": {"will": "silent"},
    },
}


def _nobody_replies(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": "S-002",
        "description": "Nobody replies: every candidate stays silent (J3 fan-out and escalation)",
        "now": "2026-11-04T06:05:00+08:00",
        "seed": 2,
        "gap": {"outlet": "tampines", "station": "cashier", "start": "07:00", "end": "15:00",
                "absent": _absent_on(data, "tampines", "cashier", "2026-11-04", "07:00")},
        "overrides": [],
        "personas": {sid: {"will": "silent"} for sid in sorted(data["staff"])},
    }


def _absent_on(data: dict[str, Any], outlet: str, station: str, day: str, hhmm: str) -> str:
    start = f"{day}T{hhmm}:00+08:00"
    for s in data["shifts"]:
        if s["outlet"] == outlet and s["station"] == station and s["start"] == start:
            return str(s["staff_id"])
    raise ValueError(f"no {station} shift at {outlet} on {start}")


def _random_scenario(sid: str, rng: random.Random, data: dict[str, Any], seed: int) -> dict[str, Any]:
    days = {f"2026-11-0{d}" for d in range(3, 8)}
    pool = [s for s in data["shifts"] if s["start"][:10] in days
            and data["staff"][s["staff_id"]]["employee_class"] != "manager_executive"]
    shift = rng.choice(pool)
    start = datetime.fromisoformat(shift["start"])
    now = start - timedelta(minutes=rng.randint(35, 120))
    station, outlet = shift["station"], shift["outlet"]
    others = sorted(
        x for x, rec in data["staff"].items()
        if station in rec["skills"] and x != shift["staff_id"]
        and rec["employee_class"] != "manager_executive"
    )
    overrides = []
    if others and rng.random() < 0.4:
        ft = [x for x in others if data["staff"][x]["contract_type"] == "full_time"]
        if ft:
            overrides.append({"staff": rng.choice(ft),
                              "ledger": {"ot_hours_used": rng.randint(66, 71)}})
    personas: dict[str, Any] = {}
    for x in rng.sample(others, k=min(len(others), rng.choice([0, 1, 2, 3]))):
        will = rng.choice(["decline", "silent", "counter"])
        if will == "counter":
            later = (start + timedelta(hours=2)).strftime("%H:%M")
            personas[x] = {"will": "counter", "window": [later, shift["end"][11:16]]}
        else:
            personas[x] = {"will": will}
    return {
        "id": sid,
        "description": f"{data['staff'][shift['staff_id']]['display_name']} absent: {outlet} "
                       f"{station} {shift['start'][11:16]}-{shift['end'][11:16]} on "
                       f"{shift['start'][:10]}",
        "now": now.isoformat(),
        "seed": seed,
        "gap": {"outlet": outlet, "station": station, "start": shift["start"][11:16],
                "end": shift["end"][11:16], "absent": shift["staff_id"]},
        "overrides": overrides,
        "personas": personas,
    }


def label(scenario: dict[str, Any], data: dict[str, Any], cfg: dict[str, Any],
          rules: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute the ``expect`` block offline with the long time limit."""
    from evals.cascade_sim import run_covercall

    res = run_covercall(scenario, data, rules, cfg, time_limit_s=float(cfg["offline_time_limit_s"]))
    return {
        "outcome": res["outcome"],
        "violations": res["violations"],
        "assignment": res["assignment"],
        "overtime_cost_cents": res["overtime_cost_cents"],
        "total_cost_cents": res["cost_breakdown"]["total_cents"],
        "computed_by": f"evals.cascade_sim (solver + validator, time limit "
                       f"{cfg['offline_time_limit_s']} s); never hand-typed",
    }


def write_scenarios(seed: int, data_dir: Path, golden_dir: Path, heldout_dir: Path,
                    golden_count: int, heldout_count: int, cfg: dict[str, Any],
                    rules: list[dict[str, Any]]) -> dict[str, Any]:
    data = load_data(data_dir)
    for d in (golden_dir, heldout_dir):
        d.mkdir(parents=True, exist_ok=True)
        for old in d.glob("*.yaml"):
            old.unlink()

    golden_rng = random.Random(f"{seed}:golden")
    golden = []
    for i in range(1, golden_count + 1):
        sid = f"S-{i:03d}"
        if sid == "S-017":
            scen = dict(S017)
        elif sid == "S-002":
            scen = _nobody_replies(data)
        else:
            scen = _random_scenario(sid, golden_rng, data, seed * 100 + i)
        golden.append(scen)
    heldout_rng = random.Random(f"{seed}:heldout")
    heldout = [_random_scenario(f"H-{i:03d}", heldout_rng, data, seed * 100 + 1000 + i)
               for i in range(1, heldout_count + 1)]

    outcomes: dict[str, int] = {}
    for directory, items in ((golden_dir, golden), (heldout_dir, heldout)):
        for scen in items:
            scen = dict(scen, synthetic=True)
            scen["expect"] = label(scen, data, cfg, rules)
            outcomes[scen["expect"]["outcome"]] = outcomes.get(scen["expect"]["outcome"], 0) + 1
            (directory / f"{scen['id']}.yaml").write_text(
                yaml.safe_dump(scen, sort_keys=False, allow_unicode=True), encoding="utf-8",
                newline="\n")
    return {"golden_scenarios": len(golden), "heldout_scenarios": len(heldout),
            "expect_outcomes": outcomes}
