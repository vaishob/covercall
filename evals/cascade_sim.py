"""Untimed CoverCall cascade for Slice 1 evals and scenario labels (§3.8 step 8, §3.9).

Solve -> offer the top plan's open segments in order -> apply the persona's reply -> re-solve on a
decline, silence (treated as timeout) or counter-offer, until every segment of the top plan is
accepted ("filled") or no legal plan remains ("escalated"). Personas come from the ``sim`` data and
scenario overrides, never from the planner's context. The timed cascade with reply windows,
fan-out and escalation deadlines is Slice 2 (``evals/runners/local_cascade.py``).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from datagen.loader import scenario_context
from datagen.personas import decide_reply
from policy.compile_cpsat import PlanDisagreement, solve
from policy.validate import blocking_violations, validate_assignment

MAX_ROUNDS = 60


def _covers(window: tuple[str, str] | None, seg: dict[str, Any]) -> bool:
    if window is None:
        return False
    w0, w1 = (datetime.fromisoformat(x) for x in window)
    return w0 <= datetime.fromisoformat(seg["start"]) and datetime.fromisoformat(seg["end"]) <= w1


def run_covercall(
    scenario: dict[str, Any],
    data: dict[str, Any],
    rules: list[dict[str, Any]],
    cfg: dict[str, Any],
    time_limit_s: float | None = None,
) -> dict[str, Any]:
    gap, context = scenario_context(scenario, data, cfg)
    excluded: list[str] = []
    windows: dict[str, list[str]] = {}
    accepted: dict[str, tuple[str, str]] = {}
    offers: list[dict[str, Any]] = []
    attempts: dict[str, int] = {}

    for _ in range(MAX_ROUNDS):
        ctx = dict(context, excluded=list(excluded), windows=dict(windows))
        try:
            result = solve(gap, ctx, rules, cfg, time_limit_s=time_limit_s)
        except PlanDisagreement as exc:
            return _outcome(scenario, "held", None, offers, ctx, rules, disagreement=exc.details)
        if not result.candidates:
            return _outcome(scenario, "escalated", None, offers, ctx, rules)
        plan = result.candidates[0]
        replanned = False
        for seg in plan["segments"]:
            sid = seg["staff_id"]
            if _covers(accepted.get(sid), seg):
                continue
            n = attempts.get(sid, 0)
            attempts[sid] = n + 1
            reply = decide_reply(data["personas"][sid], seg, scenario, attempt=n)
            offers.append({"staff_id": sid, "start": seg["start"], "end": seg["end"],
                           "intent": reply["intent"], "source": reply["source"]})
            if reply["intent"] == "accept":
                accepted[sid] = (seg["start"], seg["end"])
                continue
            if reply["intent"] == "counter" and reply["window"] and sid not in windows:
                windows[sid] = reply["window"]
                accepted[sid] = (reply["window"][0], reply["window"][1])
            else:
                excluded.append(sid)
                accepted.pop(sid, None)
            replanned = True
            break
        if not replanned:
            return _outcome(scenario, "filled", plan, offers, ctx, rules)
    return _outcome(scenario, "escalated", None, offers, context, rules)


def _outcome(scenario: dict[str, Any], outcome: str, plan: dict[str, Any] | None,
             offers: list[dict[str, Any]], ctx: dict[str, Any], rules: list[dict[str, Any]],
             disagreement: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    violations: list[str] = []
    if plan is not None:
        for seg in plan["segments"]:
            violations += [r.rule_id for r in
                           blocking_violations(validate_assignment(seg, ctx, rules))]
    cost = (plan or {}).get("cost_breakdown") or {"base_cents": 0, "overtime_cents": 0,
                                                  "rest_day_cents": 0, "total_cents": 0}
    return {
        "scenario_id": scenario["id"],
        "outcome": outcome,
        "assignment": [{"staff_id": s["staff_id"], "start": s["start"], "end": s["end"]}
                       for s in (plan or {}).get("segments", [])],
        "cost_breakdown": cost,
        "overtime_cost_cents": cost["overtime_cents"] + cost["rest_day_cents"],
        "violations": len(violations),
        "violated_rules": violations,
        "disagreements": len(disagreement or []),
        "offers": offers,
        "synthetic": True,
    }
