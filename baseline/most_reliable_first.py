"""Naive baseline: ask the most reliable available person first (§3.9, §10.2).

Models a stressed manager: rank people who are free by past acceptance rate and ask them in order.
No cost or legality reasoning beyond "are they free" (not absent, not already on a shift that
overlaps the gap) and "can they work this station" (decision 0008). A counter-offer is treated as a
no: the manager wants the whole shift. Same scenarios, personas and seeds as CoverCall.
The chosen assignment is then audited by the independent validator, which also prices it.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from datagen.loader import scenario_context
from datagen.personas import decide_reply
from policy.compile_cpsat import planned_breaks
from policy.validate import blocking_violations, cost_breakdown, validate_assignment


def _free(sid: str, gap: dict[str, Any], shifts: list[dict[str, Any]]) -> bool:
    return not any(
        s["staff_id"] == sid and s.get("status", "scheduled") == "scheduled"
        and s["start"] < gap["end"] and s["end"] > gap["start"]
        for s in shifts
    )


def ranked_pool(gap: dict[str, Any], context: dict[str, Any]) -> list[str]:
    people = [
        s for sid, s in context["staff"].items()
        if sid != gap["absent_staff_id"] and s["employee_class"] != "manager_executive"
        and gap["station"] in s["skills"] and _free(sid, gap, context["shifts"])
    ]
    people.sort(key=lambda s: (-float(s["past_acceptance_rate"]), s["staff_id"]))
    return [s["staff_id"] for s in people]


def run_baseline(
    scenario: dict[str, Any],
    data: dict[str, Any],
    rules: list[dict[str, Any]],
    cfg: dict[str, Any],
) -> dict[str, Any]:
    gap, context = scenario_context(scenario, data, cfg)
    offers = []
    for sid in ranked_pool(gap, context):
        offer = {"start": gap["start"], "end": gap["end"]}
        reply = decide_reply(data["personas"][sid], offer, scenario)
        offers.append({"staff_id": sid, "intent": reply["intent"]})
        if reply["intent"] != "accept":
            continue
        tz = datetime.fromisoformat(gap["start"]).tzinfo
        start = int(datetime.fromisoformat(gap["start"]).timestamp() // 60)
        end = int(datetime.fromisoformat(gap["end"]).timestamp() // 60)
        breaks = [{"start": datetime.fromtimestamp(a * 60, tz).isoformat(), "duration_min": b - a}
                  for a, b in planned_breaks(start, end, cfg)]
        asg = {"staff_id": sid, "start": gap["start"], "end": gap["end"], "breaks": breaks}
        results = validate_assignment(asg, context, rules)
        cost = cost_breakdown(results)
        violated = [r.rule_id for r in blocking_violations(results)]
        return {
            "scenario_id": scenario["id"], "outcome": "filled",
            "assignment": [{"staff_id": sid, "start": gap["start"], "end": gap["end"]}],
            "cost_breakdown": cost,
            "overtime_cost_cents": cost["overtime_cents"] + cost["rest_day_cents"],
            "violations": len(violated), "violated_rules": violated, "offers": offers,
            "synthetic": True,
        }
    return {
        "scenario_id": scenario["id"], "outcome": "unfilled", "assignment": [],
        "cost_breakdown": {"base_cents": 0, "overtime_cents": 0, "rest_day_cents": 0,
                           "total_cents": 0},
        "overtime_cost_cents": 0, "violations": 0, "violated_rules": [], "offers": offers,
        "synthetic": True,
    }
