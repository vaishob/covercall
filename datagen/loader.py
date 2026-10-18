"""Load synthetic data and build engine contexts for scenarios (§8.1, §8.4).

``load_staff`` is the data gate: it rejects any record under 16 (CO-AGE-SCOPE), any record without
``synthetic: true``, and any record that stores ``part4_covered`` by hand.
"""

from __future__ import annotations

import copy
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from policy.validate import check_staff_age


class DataGateError(ValueError):
    """A record failed a data gate (CO-AGE-SCOPE, synthetic flag, hand-stored derived field)."""


def load_staff(records: list[dict[str, Any]], rules: list[dict[str, Any]],
               company: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for rec in records:
        sid = rec.get("staff_id")
        if rec.get("synthetic") is not True:
            raise DataGateError(f"staff {sid}: missing synthetic: true")
        if "part4_covered" in rec:
            raise DataGateError(f"staff {sid}: part4_covered must be computed by SG-EA4-COVERAGE")
        result = check_staff_age(rec, rules, company)
        if result.status == "violation":
            raise DataGateError(f"CO-AGE-SCOPE: {result.message}")
        out.append(rec)
    return out


def load_data(data_dir: str | Path = "data") -> dict[str, Any]:
    d = Path(data_dir)

    def read(name: str) -> Any:
        return json.loads((d / name).read_text(encoding="utf-8"))

    travel = read("travel_cache.json")
    return {
        "outlets": {o["outlet_id"]: o for o in read("outlets.json")},
        "staff": {s["staff_id"]: s for s in read("staff.json")},
        "shifts": read("shifts.json"),
        "ledgers": read("ledgers.json"),
        "travel": travel["staff_to_outlet_min"],
        "travel_meta": {k: v for k, v in travel.items() if k != "staff_to_outlet_min"},
        "personas": read("sim_personas.json"),
    }


def gap_from_scenario(scenario: dict[str, Any]) -> dict[str, Any]:
    now = datetime.fromisoformat(scenario["now"])
    g = scenario["gap"]

    def at(hhmm: str) -> str:
        h, m = (int(x) for x in str(hhmm).split(":"))
        return now.replace(hour=h, minute=m, second=0, microsecond=0).isoformat()

    return {"outlet": g["outlet"], "station": g["station"], "start": at(g["start"]),
            "end": at(g["end"]), "absent_staff_id": g["absent"]}


def scenario_context(scenario: dict[str, Any], data: dict[str, Any],
                     company: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return ``(gap, context)`` for the planner. Personas are deliberately NOT included."""
    gap = gap_from_scenario(scenario)
    month = scenario["now"][:7].replace("-", "")
    ledgers = copy.deepcopy(data["ledgers"])
    for ov in scenario.get("overrides") or []:
        lid = f"{ov['staff']}_{month}"
        if "ledger" in ov:
            ledgers[lid].update(ov["ledger"])
    shifts = []
    for s in data["shifts"]:
        if (s["staff_id"] == gap["absent_staff_id"] and s["start"] < gap["end"]
                and s["end"] > gap["start"]):
            s = dict(s, status="absent")
        shifts.append(s)
    context = {
        "now": scenario["now"],
        "seed": int(scenario["seed"]),
        "gap": gap,
        "staff": data["staff"],
        "shifts": shifts,
        "ledgers": ledgers,
        "outlets": data["outlets"],
        "travel": data["travel"],
        "company": company,
    }
    return gap, context
