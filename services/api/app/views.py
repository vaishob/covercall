"""Client-safe read projections (docs/decisions/0015-reads-through-api.md).

Every read route returns a view built here, field by field (allow-list, not deny-list). No view
contains an approval nonce (only ``GET /gaps/{id}/approval`` returns it, while pending), a callback
URL, raw staff or lead text, or unredacted PII. Money is in integer cents. All data is synthetic.
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from services.agent.app.logic import PARSER_IMPL
from services.api.app.core import Api, ApiError
from services.api.app.events import TERMINAL_STATES, verify_chain
from services.common.pii import redact
from services.guard.app.logic import GUARD_IMPL
from services.persona_sim.app.logic import TEXT_IMPL

# Journeys with a scenario in the data (§3, §11.3). J4 "Adversarial" has none yet (OPEN_ITEMS).
PLAYABLE = {
    "S-017": {"label": "6:02am sick call", "journey": "J1 and J2 (cascade)"},
    "S-002": {"label": "Nobody replies", "journey": "J3 (escalation)"},
}
GAP_FIELDS = ("gap_id", "scenario_id", "outlet", "station", "start", "end", "absent_staff_id",
              "state", "version", "outcome", "summary", "cost_saved_cents", "reported_at", "filled_at",
              "t_esc_locked", "workflow_execution_id", "approval_pending", "fallbacks", "time_scale")
OFFER_FIELDS = ("offer_id", "staff_id", "start", "end", "sent_at", "window_s", "status",
                "fanout_group", "rank", "late_reply")


def _rule_meta(api: Api) -> dict[str, dict[str, Any]]:
    return {r["id"]: {"title": r["title"], "kind": r["kind"],
                      "source": {k: r["source"][k] for k in ("publisher", "title", "section", "url")}}
            for r in api.rules}


def status_view(api: Api, environment: str) -> dict[str, Any]:
    roles = yaml.safe_load(Path("config/models.yaml").read_text(encoding="utf-8"))["roles"]
    return {
        "status": "ok",
        "environment": environment,
        "guard_impl": GUARD_IMPL,
        "parser_impl": getattr(api.agent, "model_id", PARSER_IMPL),
        "persona_text_impl": (roles["persona_sim"]["model_id"] if os.environ.get("PERSONA_TEXT_IMPL") == "gemini"
                              else TEXT_IMPL),
        "models": {name: {"model_id": r["model_id"], "api_version": r["api_version"],
                          "provider": r["provider"]} for name, r in roles.items()},
        "time_scale": api.time_scale,
        "synthetic": True,
    }


def scenarios_view(api: Api) -> list[dict[str, Any]]:
    out = []
    for sid, meta in PLAYABLE.items():
        scen = api.store.get(f"scenarios/{sid}")
        if scen is None:
            continue
        out.append({"scenario_id": sid, "label": meta["label"], "journey": meta["journey"],
                    "description": scen["description"], "now": scen["now"],
                    "gap": {k: scen["gap"][k] for k in ("outlet", "station", "start", "end")},
                    "synthetic": True})
    return out


def _segment(seg: dict[str, Any], meta: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "staff_id": seg["staff_id"], "display_name": seg["display_name"],
        "home_outlet": seg["home_outlet"], "start": seg["start"], "end": seg["end"],
        "breaks": [{"start": b["start"], "duration_min": b["duration_min"]} for b in seg["breaks"]],
        "travel_min": seg["travel_min"], "arrival": seg["arrival"],
        "cost_breakdown": dict(seg["cost_breakdown"]),
        "rules_checked": [{"rule_id": r["rule_id"], "status": r["status"], "kind": r["kind"],
                           "title": meta[r["rule_id"]]["title"], "message": r["message"],
                           "source_url": r["source_url"]} for r in seg["rules_checked"]],
    }


def _plan(plan: dict[str, Any], meta: dict[str, dict[str, Any]],
          staff: dict[str, dict[str, Any]]) -> dict[str, Any]:
    naive = plan.get("naive_first_pick")
    return {
        "plan_id": plan["plan_id"], "created_at": plan["created_at"],
        "naive_first_pick": None if naive is None else {
            k: naive[k] for k in ("staff_id", "display_name", "overtime_cents", "blocking_rule_ids")},
        "options": [{
            "rank": c["rank"], "staff_ids": list(c["staff_ids"]),
            "segments": [_segment(s, meta) for s in c["segments"]],
            "cost_breakdown": dict(c["cost_breakdown"]),
            "overtime_cost_cents": c["overtime_cost_cents"],
            "saves_vs_naive_cents": c.get("saves_vs_naive_cents"),
            "travel_min": c["travel_min"], "arrival": c["arrival"],
            "is_cross_outlet_borrow": c["is_cross_outlet_borrow"],
        } for c in plan["candidates"]],
        "rejected": [{
            "staff_id": r["staff_id"], "display_name": r["display_name"],
            "home_outlet": staff.get(r["staff_id"], {}).get("home_outlet"),
            "rules": [{"rule_id": x["rule_id"], "kind": meta[x["rule_id"]]["kind"],
                       "title": meta[x["rule_id"]]["title"], "message": x["message"],
                       "source_url": x["source_url"],
                       "publisher": meta[x["rule_id"]]["source"]["publisher"],
                       "section": meta[x["rule_id"]]["source"]["section"]} for x in r["rejected_rules"]],
        } for r in plan["rejected_candidates"]],
    }


def gap_view(api: Api, gap_id: str) -> dict[str, Any]:
    """Everything the lead screen needs for one gap, in one response."""
    gap = api._gap(gap_id)
    staff = {k: v for k, v in api.store.list("staff")}
    outlet = api.store.get(f"outlets/{gap['outlet']}") or {}
    meta = _rule_meta(api)
    now = api.clock.now()
    view_gap = {k: gap.get(k) for k in GAP_FIELDS}
    view_gap["outlet_name"] = outlet.get("name", gap["outlet"])
    view_gap["absent_staff_name"] = staff.get(gap["absent_staff_id"], {}).get("display_name")
    seconds = None
    if gap.get("t_esc_locked") and gap["state"] not in TERMINAL_STATES and gap["state"] != "ESCALATED":
        seconds = max(0, int((datetime.fromisoformat(gap["t_esc_locked"]) - now).total_seconds()))
    plan_id = (gap.get("committing") or {}).get("plan_id") if gap["state"] == "FILLED" else None
    plan_id = plan_id or gap.get("current_plan_id")
    plan_doc = api.store.get(f"plans/{plan_id}") if plan_id else None
    committed = None
    if gap["state"] == "FILLED" and gap.get("committing"):
        c = gap["committing"]
        committed = {"plan_id": c["plan_id"], "rank": c["rank"],
                     "segments": [{"staff_id": s["staff_id"],
                                   "display_name": staff[s["staff_id"]]["display_name"],
                                   "start": s["start"], "end": s["end"]} for s in c["segments"]],
                     "cost_breakdown": dict(c["cost_breakdown"])}
    offers = sorted((o for _, o in api.store.list("offers") if o["gap_id"] == gap_id),
                    key=lambda o: o["offer_id"])
    return {
        "gap": view_gap,
        "clock": {"now": now.isoformat(), "seconds_to_escalation": seconds},
        "plan": _plan(plan_doc, meta, staff) if plan_doc else None,
        "committed": committed,
        "offers": [dict({k: o.get(k) for k in OFFER_FIELDS},
                        display_name=staff.get(o["staff_id"], {}).get("display_name"),
                        late_reply=bool(o.get("late_reply"))) for o in offers],
        "synthetic": True,
    }


def events_view(api: Api, gap_id: str) -> dict[str, Any]:
    api._gap(gap_id)
    events = [ev for _, ev in api.store.list(f"gaps/{gap_id}/events")]
    return {"gap_id": gap_id, "events": redact(events), "chain": verify_chain(api.store, gap_id).to_dict(),
            "synthetic": True}


def quarantine_view(api: Api, gap_id: str) -> list[dict[str, Any]]:
    api._gap(gap_id)
    staff = {k: v for k, v in api.store.list("staff")}
    return [{"quarantine_id": qid, "gap_id": q["gap_id"], "offer_id": q.get("offer_id"),
             "staff_id": q["staff_id"], "display_name": staff.get(q["staff_id"], {}).get("display_name"),
             "guard_labels": list(q["guard_labels"]), "guard_impl": q.get("guard_impl"),
             "redacted_text": redact(q["redacted_text"]), "synthetic": True}
            for qid, q in api.store.list("quarantine") if q["gap_id"] == gap_id]


def evals_view() -> dict[str, Any]:
    # Slice 6: results come from BigQuery covercall_evals. Until then there is nothing to serve, and
    # numbers from anywhere else (CLI runs, fixtures) are deliberately not served here.
    return {"status": "no_eval_run", "message": "No eval run yet. The release gate writes results to "
            "BigQuery covercall_evals in Slice 6.", "latest_run": None, "metrics": [],
            "synthetic": True}


def require_gap(api: Api, gap_id: str) -> None:
    if api.store.get(f"gaps/{gap_id}") is None:
        raise ApiError(404, f"unknown gap {gap_id}")
