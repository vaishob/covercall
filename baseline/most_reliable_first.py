"""Naive baseline: call the most reliable available person first (§3.9, §10.2).

Models what a stressed manager does at 6:02am: rank available staff by past
acceptance rate (`past_acceptance_rate`) and ask them in order, with no cost or
legality reasoning beyond "are they free" (not the absent staff member and not
currently declining/silent). Uses the exact same scenarios, personas, and seeds
as CoverCall.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from policy.validate import validate_assignment


def _hours_between(start_hhmm: str, end_hhmm: str, base_date: str = "2026-11-03") -> float:
    s = datetime.fromisoformat(f"{base_date}T{start_hhmm}:00+08:00") if "T" not in start_hhmm else datetime.fromisoformat(start_hhmm)
    e = datetime.fromisoformat(f"{base_date}T{end_hhmm}:00+08:00") if "T" not in end_hhmm else datetime.fromisoformat(end_hhmm)
    return max(1.0, (e - s).total_seconds() / 3600.0)


def run_baseline_scenario(
    scenario: dict[str, Any],
    staff_list: list[dict[str, Any]],
    ledgers: dict[str, dict[str, Any]],
    travel_cache: dict[str, Any],
    rules: list[dict[str, Any]],
) -> dict[str, Any]:
    """Run most-reliable-first baseline on a single scenario and audit with validate_assignment."""
    gap = scenario["gap"]
    outlet = str(gap["outlet"])
    station = str(gap["station"])
    absent_id = str(gap.get("absent") or gap.get("absent_staff_id") or "")
    base_date = str(scenario.get("now", "2026-11-03T06:02:00+08:00"))[:10]
    start_iso = f"{base_date}T{gap['start']}:00+08:00" if "T" not in str(gap["start"]) else str(gap["start"])
    end_iso = f"{base_date}T{gap['end']}:00+08:00" if "T" not in str(gap["end"]) else str(gap["end"])
    work_hours = _hours_between(str(gap["start"]), str(gap["end"]), base_date)

    personas = scenario.get("personas") or {}
    # Sort available staff by past_acceptance_rate descending, then staff_id ascending
    ranked_staff = sorted(
        [s for s in staff_list if s["staff_id"] != absent_id],
        key=lambda s: (-float(s.get("past_acceptance_rate", 0.5)), str(s["staff_id"])),
    )

    elapsed_min = 0.0
    chosen_staff: dict[str, Any] | None = None
    for cand in ranked_staff:
        sid = str(cand["staff_id"])
        p_action = (personas.get(sid) or {}).get("will", "accept")
        if p_action == "decline":
            elapsed_min += 4.5
            continue
        if p_action == "silent":
            elapsed_min += 10.0
            continue
        # Accepts (or manager accepts first available person without re-optimizing)
        elapsed_min += 3.5
        chosen_staff = cand
        break

    if chosen_staff is None:
        return {
            "scenario_id": scenario["id"],
            "outcome": "escalated",
            "assigned_staff_id": None,
            "overtime_cost_sgd": 0.0,
            "total_cost_sgd": 0.0,
            "violations": 0,
            "violated_rules": [],
            "time_to_fill_min": round(elapsed_min, 2),
            "synthetic": True,
        }

    sid = str(chosen_staff["staff_id"])
    ledger = dict(ledgers.get(f"{sid}_202611") or {"ot_hours_used": 0, "rest_days": [], "cover_requests_14d": 0})
    shift_ctx: dict[str, Any] = {
        "outlet": outlet,
        "station": station,
        "start": start_iso,
        "end": end_iso,
        "work_hours": work_hours,
        "hours_worked_today_before_shift": 0.0,
        "breaks_min": 45 if work_hours >= 8.0 else 15,
        "is_rest_day": False,
        "is_public_holiday": False,
        "is_extra_cover_shift": chosen_staff.get("contract_type") == "full_time",
        "is_opening_shift": str(gap.get("start", "07:00")).startswith("07:"),
        "other_keyholder_present": True,
        "hours_since_prev_shift_end": 14.0,
        "hours_until_next_shift_start": 14.0,
        "days_since_last_rest_day": int(ledger.get("days_since_last_rest_day", 2)),
        "travel_min": int(
            (travel_cache.get("staff_to_outlet_min", {}).get(sid, {}) or {}).get(outlet, 20)
        ),
    }

    for ov in scenario.get("overrides") or []:
        if ov.get("staff") == sid:
            if "ledger" in ov:
                ledger.update(ov["ledger"])
            if "shift_context" in ov:
                shift_ctx.update(ov["shift_context"])
            if "days_since_last_rest_day" in ledger and "shift_context" not in ov:
                shift_ctx["days_since_last_rest_day"] = int(ledger["days_since_last_rest_day"])

    val_results = validate_assignment(
        {"employee": chosen_staff, "ledger": ledger, "shift": shift_ctx},
        {},
        rules,
    )
    hard_violations = [
        r.rule_id for r in val_results if r.status == "violation" and r.kind in ("hard", "data_gate")
    ]

    ot_cents = 0
    total_cents = 0
    for r in val_results:
        if r.rule_id in ("SG-EA4-OT-RATE", "SG-EA4-REST-DAY-PAY"):
            ot_cents += r.cost_cents
            total_cents += r.cost_cents
        elif r.rule_id == "SG-PT-OT-RATE":
            total_cents += r.cost_cents

    return {
        "scenario_id": scenario["id"],
        "outcome": "filled",
        "assigned_staff_id": sid,
        "overtime_cost_sgd": round(ot_cents / 100.0, 2),
        "total_cost_sgd": round(total_cents / 100.0, 2),
        "violations": len(hard_violations),
        "violated_rules": hard_violations,
        "time_to_fill_min": round(elapsed_min, 2),
        "synthetic": True,
    }
