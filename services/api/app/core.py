"""``api`` behaviour behind the HTTP routes (§4.2 KICKSTART, §5, §8.1).

The workflow ``coverage-cascade`` owns state: every state change here happens because the workflow
called an internal endpoint, and it is written through ``events.append_in_txn`` (one transaction:
event + gap head). Staff-facing messages are only sent with a covering T2 approval
(``unapproved_outbound`` = 0). Raw reply text stays in ``replies_raw`` (server-only); the workflow
only ever sees ``{offer_id, message_id}`` and typed results (docs/decisions/0013-raw-text-out-of-workflow.md).
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

from baseline.most_reliable_first import ranked_pool
from policy.compile_cpsat import PlanDisagreement, planned_breaks, solve
from policy.timing import Candidate, locked_t_esc, plan_offers
from policy.validate import blocking_violations, cost_breakdown, validate_assignment
from services.agent.app.logic import draft_offer
from services.api.app.deps import (
    AgentClient,
    CallbackSender,
    Clock,
    GuardClient,
    Launcher,
    Messenger,
)
from services.api.app.events import (
    TERMINAL_STATES,
    append_in_txn,
    dedup_message,
    gap_path,
)
from services.common.pii import find_pii, redact, redact_text
from services.common.store import Store, Txn
from services.guard.app.logic import GUARD_IMPL

FALLBACKS = ("borrow", "reduced_service", "lead_covers", "agency", "unfilled")
_AFFIRMATIVE = re.compile(r"^\s*(yes|yes please|yep|approve|approved|confirm|confirmed|go ahead|ok go ahead)\b",
                          re.IGNORECASE)


class ApiError(RuntimeError):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


def _req(reader: Store | Txn, path: str) -> dict[str, Any]:
    doc = reader.get(path)
    if doc is None:
        raise ApiError(404, f"not found: {path}")
    return doc


class UnapprovedOutbound(ApiError):
    def __init__(self, message: str):
        super().__init__(403, message)


SolveFn = Callable[..., Any]


class Api:
    def __init__(self, store: Store, cfg: dict[str, Any], rules: list[dict[str, Any]], clock: Clock,
                 guard: GuardClient, agent: AgentClient, messenger: Messenger,
                 callbacks: CallbackSender, launcher: Launcher, solver: SolveFn = solve,
                 time_scale: float = 1.0, id_prefix: str = "gap"):
        self.store, self.cfg, self.rules, self.clock = store, cfg, rules, clock
        self.guard, self.agent, self.messenger = guard, agent, messenger
        self.callbacks, self.launcher, self.solver = callbacks, launcher, solver
        self.time_scale = time_scale
        self.id_prefix = id_prefix

    # ------------------------------------------------------------------ helpers

    def _now(self) -> str:
        return self.clock.now().isoformat()

    def _gap(self, gap_id: str) -> dict[str, Any]:
        gap = self.store.get(gap_path(gap_id))
        if gap is None:
            raise ApiError(404, f"unknown gap {gap_id}")
        return gap

    def _meta(self, gap_id: str, fields: dict[str, Any]) -> None:
        """Update non-state gap fields (cascade bookkeeping). State changes go through events only."""
        if {"state", "version", "last_seq", "last_hash"} & set(fields):
            raise ValueError("state fields change only through events")
        self.store.transaction(lambda txn: txn.update(gap_path(gap_id), redact(fields)))

    def planner_context(self, gap: dict[str, Any], reader: Store | Txn | None = None) -> dict[str, Any]:
        """Planner view: roster data only. Personas and scenario persona overrides are never read."""
        r = reader or self.store
        ledgers = {k: v for k, v in r.list("ledgers")}
        month = gap["start"][:7].replace("-", "")
        for ov in gap.get("overrides") or []:
            lid = f"{ov['staff']}_{month}"
            if "ledger" in ov and lid in ledgers:
                ledgers[lid] = dict(ledgers[lid], **ov["ledger"])
        travel = r.get("config/travel") or {}
        windows = dict(gap.get("windows") or {})
        for sid, win in (gap.get("accepted") or {}).items():
            windows.setdefault(sid, win)
        return {
            "now": self._now(),
            "seed": int(gap.get("seed", self.cfg["solver_seed"])),
            "gap": self._gap_spec(gap),
            "staff": {k: v for k, v in r.list("staff")},
            "shifts": [v for _, v in r.list("shifts")],
            "ledgers": ledgers,
            "outlets": {k: v for k, v in r.list("outlets")},
            "travel": travel.get("staff_to_outlet_min", {}),
            "company": self.cfg,
            "excluded": list(gap.get("excluded") or []),
            "windows": windows,
        }

    @staticmethod
    def _gap_spec(gap: dict[str, Any]) -> dict[str, Any]:
        return {k: gap[k] for k in ("outlet", "station", "start", "end", "absent_staff_id")}

    def _approval_ok(self, gap: dict[str, Any], reader: Store | Txn | None = None) -> str | None:
        r = reader or self.store
        aid = gap.get("approval_id")
        if not aid:
            return None
        approval = r.get(f"approvals/{aid}")
        if not approval or approval.get("decision") != "approve" or approval.get("gap_id") != gap["gap_id"]:
            return None
        return str(aid)

    def _outbound(self, gap: dict[str, Any], staff_id: str, kind: str, text: str,
                  extra: dict[str, Any] | None = None) -> None:
        """Every staff-facing message goes through here and must carry a covering approval."""
        aid = self._approval_ok(gap)
        if aid is None:
            self.store.set(f"refused_outbound/{gap['gap_id']}-{kind}-{staff_id}-{self._now()}",
                           {"gap_id": gap["gap_id"], "staff_id": staff_id, "kind": kind,
                            "ts": self._now(), "synthetic": True})
            raise UnapprovedOutbound(f"{gap['gap_id']}: no covering T2 approval for a {kind} to {staff_id}")
        staff = self.store.get(f"staff/{staff_id}") or {"staff_id": staff_id}
        msg = dict(extra or {}, kind=kind, gap_id=gap["gap_id"], approval_id=aid, text=text,
                   ts=self._now())
        n = len(self.store.list("outbound")) + 1
        self.store.set(f"outbound/{n:06d}", dict(redact(msg), staff_id=staff_id, synthetic=True))
        self.messenger.send(staff, msg)

    # ------------------------------------------------------------------ public routes

    def create_gap(self, body: dict[str, Any]) -> dict[str, Any]:
        if body.get("scenario_id"):
            scen = self.store.get(f"scenarios/{body['scenario_id']}")
            if scen is None:
                raise ApiError(404, f"unknown scenario {body['scenario_id']}")
            now = datetime.fromisoformat(scen["now"])

            def at(hhmm: str) -> str:
                h, m = (int(x) for x in hhmm.split(":"))
                return now.replace(hour=h, minute=m, second=0, microsecond=0).isoformat()

            spec = {"outlet": scen["gap"]["outlet"], "station": scen["gap"]["station"],
                    "start": at(scen["gap"]["start"]), "end": at(scen["gap"]["end"]),
                    "absent_staff_id": scen["gap"]["absent"], "scenario_id": scen["id"],
                    "seed": int(scen["seed"]), "overrides": scen.get("overrides") or []}
            text = f"Scenario {scen['id']}: {scen['description']}"
        else:
            missing = [k for k in ("outlet", "station", "start", "end", "absent_staff_id") if not body.get(k)]
            if missing:
                raise ApiError(422, f"missing fields: {missing}")
            spec = {k: body[k] for k in ("outlet", "station", "start", "end", "absent_staff_id")}
            spec.update(scenario_id=None, seed=int(body.get("seed", self.cfg["solver_seed"])), overrides=[])
            text = str(body.get("text") or "")
        n = len(self.store.list("gaps")) + 1
        gap_id = f"{self.id_prefix}-{n:04d}"
        self.store.set(f"inputs/{gap_id}", {"gap_id": gap_id, "text": text, "ts": self._now(),
                                            "synthetic": True})
        fields = dict(spec, excluded=[], windows={}, accepted={}, pending_counters=[], plan_id=None,
                      current_plan_id=None, approval_id=None, outcome=None, cost_saved_sgd=None,
                      workflow_execution_id=None, reported_at=self._now(), offer_seq=0,
                      time_scale=self.time_scale)
        self.store.transaction(lambda txn: append_in_txn(
            txn, gap_id, "gap.reported", actor="lead", ts=self._now(),
            payload={"input": text, "scenario_id": spec["scenario_id"]}, gap_fields=fields))
        execution = self.launcher.start(gap_id)
        self._meta(gap_id, {"workflow_execution_id": execution})
        return {"gap_id": gap_id, "workflow_execution_id": execution}

    def record_approval(self, body: dict[str, Any]) -> dict[str, Any]:
        gap = self._gap(body["gap_id"])
        pending = gap.get("pending_approval") or {}
        if not pending or body.get("nonce") != pending.get("nonce"):
            raise ApiError(409, "no pending approval with that nonce")
        channel = body.get("channel", "tap")
        transcript = str(body.get("transcript") or "")
        if channel == "voice":
            decision = "approve" if _AFFIRMATIVE.match(transcript) else "reject"
        else:
            decision = "approve" if body.get("decision") == "approve" else "reject"
        n = len(self.store.list("approvals")) + 1
        approval_id = f"apr-{gap['gap_id']}-{n:03d}"
        doc = {"approval_id": approval_id, "gap_id": gap["gap_id"], "plan_id": pending["plan_id"],
               "tier": "T2", "nonce": pending["nonce"], "readback_text": pending["readback_text"],
               "transcript": redact_text(transcript), "decision": decision, "channel": channel,
               "exclude_staff_ids": list(body.get("exclude_staff_ids") or []), "ts": self._now(),
               "synthetic": True}
        self.store.transaction(lambda txn: txn.create(f"approvals/{approval_id}", doc))
        self._meta(gap["gap_id"], {"pending_approval": None})
        server = self.store.get(f"server/{gap['gap_id']}") or {}
        self.callbacks.send(server["approval_callback"], {"approval_id": approval_id, "decision": decision})
        return doc

    def receive_reply(self, body: dict[str, Any]) -> dict[str, Any]:
        message_id = str(body.get("message_id") or "")
        if not dedup_message(self.store, message_id, self._now()):
            return {"status": "duplicate"}
        offer = self.store.get(f"offers/{body['offer_id']}")
        if offer is None:
            raise ApiError(404, "unknown offer")
        self.store.set(f"replies_raw/{message_id}", {"message_id": message_id, "offer_id": offer["offer_id"],
                                                     "text": str(body.get("text") or ""),
                                                     "channel": body.get("channel", "sim"),
                                                     "ts": self._now(), "synthetic": True})
        if offer["status"] != "open":
            gap = self._gap(offer["gap_id"])
            self._outbound(gap, offer["staff_id"], "courtesy",
                           "Thanks for replying! This shift has already been covered.")
            self.store.transaction(lambda txn: txn.update(f"offers/{offer['offer_id']}",
                                                          {"late_reply": message_id}))
            return {"status": "late"}
        self.store.transaction(lambda txn: txn.update(f"offers/{offer['offer_id']}",
                                                      {"last_message_id": message_id}))
        self.callbacks.send(offer["callback_url"], {"offer_id": offer["offer_id"], "message_id": message_id})
        return {"status": "relayed"}

    def choose_fallback(self, gap_id: str, option: str) -> dict[str, Any]:
        gap = self._gap(gap_id)
        if gap["state"] != "ESCALATED" or option not in (gap.get("fallbacks") or []):
            raise ApiError(409, f"fallback {option!r} not available")
        server = self.store.get(f"server/{gap_id}") or {}
        self.callbacks.send(server["fallback_callback"], {"option": option})
        return {"status": "relayed"}

    def cancel(self, gap_id: str, reason: str = "lead cancelled") -> dict[str, Any]:
        """Ask the workflow to cancel: every open wait receives {cancel: true}. api changes no state."""
        self._gap(gap_id)
        server = self.store.get(f"server/{gap_id}") or {}
        urls = [server.get("approval_callback"), server.get("fallback_callback")]
        urls += [o["callback_url"] for _, o in self.store.list("offers")
                 if o["gap_id"] == gap_id and o["status"] == "open"]
        for url in [u for u in urls if u]:
            self.callbacks.send(url, {"cancel": True, "reason": reason})
        return {"status": "cancel requested", "waits_signalled": len([u for u in urls if u])}

    # ------------------------------------------------------------------ internal routes

    def guard_input(self, gap_id: str) -> dict[str, Any]:
        text = (self.store.get(f"inputs/{gap_id}") or {}).get("text", "")
        try:
            result = self.guard.label(text)
        except Exception as exc:  # fail closed: never retry into a pass
            return {"status": "unavailable", "error": type(exc).__name__, "guard_impl": GUARD_IMPL}
        return {"status": "flagged" if result["flagged"] else "ok", "labels": result["labels"],
                "guard_impl": result.get("guard_impl", GUARD_IMPL)}

    def transition(self, body: dict[str, Any]) -> dict[str, Any]:
        gap_id = body["gap_id"]
        etype = body["type"]
        payload = dict(body.get("payload") or {})

        key = str(body.get("idempotency_key") or "").replace("/", "_")
        lock = None
        if etype == "plan.approved":  # §5.1: approval locks the escalation strategy (t_esc)
            gap0 = self._gap(gap_id)
            approval0 = self.store.get(f"approvals/{payload.get('approval_id')}") or {}
            plan0 = self.store.get(f"plans/{approval0.get('plan_id')}") or {}
            ctx0 = self.planner_context(gap0)
            remaining0 = _remaining(gap0, ctx0, {r["staff_id"] for r in plan0.get("rejected_candidates") or []})
            lock = locked_t_esc(self.clock.now(), remaining0, self.cfg).isoformat()

        def run(txn: Txn) -> dict[str, Any]:
            if key:
                done = txn.get(f"applied/{key}")
                if done is not None:  # a retried call: return the event it already appended
                    return dict(done["event"])
            gap = txn.get(gap_path(gap_id))
            fields: dict[str, Any] = {}
            to_state = body.get("to_state")
            if etype == "plan.approved":
                approval = txn.get(f"approvals/{payload.get('approval_id')}") if gap else None
                if not approval or approval["decision"] != "approve" or approval["gap_id"] != gap_id:
                    raise ApiError(409, "plan.approved needs a recorded T2 approval for this gap")
                fields.update(approval_id=approval["approval_id"], approved_plan_id=approval["plan_id"],
                              t_esc_locked=lock)
                payload["t_esc_locked"] = lock
            if etype == "plan.rejected":
                approval = txn.get(f"approvals/{payload.get('approval_id')}")
                extra = list((approval or {}).get("exclude_staff_ids") or [])
                fields.update(excluded=sorted(set((gap or {}).get("excluded") or []) | set(extra)),
                              approval_id=None)
            target = to_state
            if target is None:
                from services.api.app.events import targets
                options = targets(gap["state"] if gap else None, etype)
                target = options[0] if len(options) == 1 else None
            if target in TERMINAL_STATES:
                outcome = {"HELD": "held", "CANCELLED": "cancelled", "FILLED": "filled"}.get(
                    target, payload.get("option"))
                fields["outcome"] = outcome
            event = append_in_txn(txn, gap_id, etype, actor=body.get("actor", "system"), ts=self._now(),
                                  payload=payload, to_state=to_state,
                                  expected_version=body.get("expected_version"),
                                  model_ids=body.get("model_ids"), rule_ids=body.get("rule_ids"),
                                  trace_id=body.get("trace_id", ""), gap_fields=fields)
            if key:
                txn.create(f"applied/{key}", {"event": event, "synthetic": True})
            return event

        event = self.store.transaction(run)
        return {"event": event, "state": event["to_state"]}

    def solve_gap(self, gap_id: str) -> dict[str, Any]:
        gap = self._gap(gap_id)
        ctx = self.planner_context(gap)
        try:
            result = self.solver(ctx["gap"], ctx, self.rules, self.cfg)
        except PlanDisagreement as exc:
            rule_ids = sorted({r for d in exc.details for r in d.get("validator", []) + d.get("compiler", [])})
            return {"status": "disagreement", "details": redact(exc.details), "rule_ids": rule_ids}
        n = len(self.store.list("plans")) + 1
        plan_id = f"plan-{gap_id}-{n:03d}"
        doc = dict(result.to_dict(), plan_id=plan_id, gap_id=gap_id, created_at=self._now())
        self.store.transaction(lambda txn: txn.create(f"plans/{plan_id}", doc))
        self._meta(gap_id, {"current_plan_id": plan_id})
        top = result.candidates[0] if result.candidates else None
        rule_ids = sorted({r["rule_id"] for s in (top or {}).get("segments", []) for r in s["rules_checked"]})
        return {"status": "solved" if top else "no_plan", "plan_id": plan_id,
                "top": _plan_summary(top), "rule_ids": rule_ids,
                "rejected": [r["staff_id"] for r in result.rejected_candidates]}

    def approval_request(self, gap_id: str, plan_id: str, callback_url: str) -> dict[str, Any]:
        gap = self._gap(gap_id)
        plan = self.store.get(f"plans/{plan_id}") or {}
        nonce = hashlib.sha256(f"{gap_id}:{plan_id}:{self._now()}".encode()).hexdigest()[:12]
        top = (plan.get("candidates") or [None])[0]
        when = datetime.fromisoformat(gap["start"]).strftime("%a %d %b %H:%M")
        if top:
            who = " + ".join(f"{s['display_name']} {s['start'][11:16]}-{s['end'][11:16]}" for s in top["segments"])
            readback = (f"Offer the {gap['outlet']} {gap['station']} shift ({when}) to {who} first, "
                        f"then the next ranked candidates, fanning out and escalating to you on time "
                        f"if nobody accepts. Approve?")
        else:
            readback = (f"No legal cover is available for the {gap['outlet']} {gap['station']} shift "
                        f"({when}). Escalate to you with fallbacks now. Approve?")
        server = self.store.get(f"server/{gap_id}") or {"gap_id": gap_id}
        server["approval_callback"] = callback_url
        self.store.set(f"server/{gap_id}", server)
        self._meta(gap_id, {"pending_approval": {"nonce": nonce, "readback_text": readback, "plan_id": plan_id}})
        return {"status": "awaiting_approval", "readback_text": readback}

    def next_offers(self, gap_id: str) -> dict[str, Any]:
        gap = self._gap(gap_id)
        if gap["state"] != "OUTREACH":
            raise ApiError(409, f"next-offers needs OUTREACH, gap is {gap['state']}")
        ctx = self.planner_context(gap)
        now = self.clock.now()
        try:
            result = self.solver(ctx["gap"], ctx, self.rules, self.cfg)
        except PlanDisagreement as exc:  # P0; fail closed to the lead
            return {"mode": "escalate", "reason": "plan.disagreement", "t_esc": now.isoformat(),
                    "details": redact(exc.details), "offers": [], "window_s": 0, "window_s_real": 0}
        n = len(self.store.list("plans")) + 1
        plan_id = f"plan-{gap_id}-{n:03d}"
        self.store.transaction(lambda txn: txn.create(
            f"plans/{plan_id}", dict(result.to_dict(), plan_id=plan_id, gap_id=gap_id, created_at=self._now())))
        accepted = gap.get("accepted") or {}
        remaining = _remaining(gap, ctx, {r["staff_id"] for r in result.rejected_candidates})
        ranked: list[Candidate] = []
        specs: dict[str, dict[str, Any]] = {}
        for plan in result.candidates:
            for seg in plan["segments"]:
                sid = seg["staff_id"]
                win = accepted.get(sid)
                if win and win[0] <= seg["start"] and seg["end"] <= win[1]:
                    continue
                if sid in specs:
                    continue
                specs[sid] = {"staff_id": sid, "start": seg["start"], "end": seg["end"],
                              "plan_id": plan_id, "rank": plan["rank"]}
                ranked.append(Candidate(sid, datetime.fromisoformat(seg["start"]), seg["travel_min"],
                                        key=f"{plan_id}:{plan['rank']}"))
        locked = datetime.fromisoformat(gap["t_esc_locked"]) if gap.get("t_esc_locked") else None
        decision = plan_offers(now, ranked, remaining, self.cfg, locked=locked)
        self._meta(gap_id, {"t_esc": decision.t_esc.isoformat(), "current_plan_id": plan_id})
        out = decision.to_dict()
        out["offers"] = [specs[c.staff_id] for c in decision.offers]
        out["window_s_real"] = max(1, int(round(out["window_s"] / self.time_scale))) if out["window_s"] else 0
        out["plan_id"] = plan_id
        return out

    def register_offer(self, gap_id: str, offer: dict[str, Any], callback_url: str, window_s: int,
                       fanout_group: str | None = None, key: str | None = None) -> dict[str, Any]:
        if key:
            seen = self.store.get(f"offer_keys/{key.replace('/', '_')}")
            if seen is not None:  # retried call: the offer was already sent once
                return {"offer_id": seen["offer_id"]}
        gap = self._gap(gap_id)
        if gap["state"] != "OUTREACH":
            raise UnapprovedOutbound(f"{gap_id}: offers are only sent in OUTREACH (state {gap['state']})")
        if self._approval_ok(gap) is None:
            self._outbound(gap, offer["staff_id"], "offer", "")  # records the refusal and raises
        seq = int(gap.get("offer_seq", 0)) + 1
        offer_id = f"{gap_id}-o{seq:03d}"
        attempt = sum(1 for _, o in self.store.list("offers")
                      if o["gap_id"] == gap_id and o["staff_id"] == offer["staff_id"])
        doc = {"offer_id": offer_id, "gap_id": gap_id, "staff_id": offer["staff_id"],
               "start": offer["start"], "end": offer["end"], "plan_id": offer["plan_id"],
               "rank": offer["rank"], "sent_at": self._now(), "window_s": window_s, "status": "open",
               "callback_url": callback_url, "approval_id": gap["approval_id"],
               "fanout_group": fanout_group, "attempt": attempt, "synthetic": True}
        self.store.transaction(lambda txn: txn.create(f"offers/{offer_id}", doc))
        self._meta(gap_id, {"offer_seq": seq})
        outlet = self.store.get(f"outlets/{gap['outlet']}") or {}
        staff = self.store.get(f"staff/{offer['staff_id']}") or {}
        pay = ("hourly basic rate, 1.5x beyond 8 h" if staff.get("contract_type") == "part_time"
               else "per your contract; overtime at 1.5x")
        text = draft_offer(outlet.get("name", gap["outlet"]), offer["start"], offer["end"], pay, self.cfg)
        if key:
            self.store.set(f"offer_keys/{key.replace('/', '_')}", {"offer_id": offer_id, "synthetic": True})
        self._outbound(gap, offer["staff_id"], "offer", text,
                       {"offer_id": offer_id, "start": offer["start"], "end": offer["end"],
                        "scenario_id": gap.get("scenario_id"), "attempt": attempt})
        return {"offer_id": offer_id}

    def read_reply(self, offer_id: str, message_id: str) -> dict[str, Any]:
        offer = self.store.get(f"offers/{offer_id}")
        raw = self.store.get(f"replies_raw/{message_id}")
        if offer is None or raw is None or raw["offer_id"] != offer_id:
            raise ApiError(404, "unknown offer/message")
        try:
            g = self.guard.label(raw["text"])
            flagged, labels = bool(g["flagged"]), list(g["labels"])
        except Exception:  # fail closed: hold the reply for the lead
            flagged, labels = True, ["guard_unavailable"]
        if flagged:
            n = len(self.store.list("quarantine")) + 1
            self.store.set(f"quarantine/{n:06d}", {"gap_id": offer["gap_id"], "staff_id": offer["staff_id"],
                                                   "offer_id": offer_id, "guard_labels": labels,
                                                   "redacted_text": redact_text(raw["text"]),
                                                   "guard_impl": GUARD_IMPL, "synthetic": True})
            return {"flagged": True, "guard_labels": labels, "guard_impl": GUARD_IMPL}
        parsed = self.agent.parse_reply(raw["text"], {"start": offer["start"], "end": offer["end"]})
        return {"flagged": False, "guard_labels": labels, "guard_impl": GUARD_IMPL, "parsed": parsed}

    def offer_outcome(self, offer_id: str, outcome: str, info: dict[str, Any] | None = None) -> dict[str, Any]:
        etype = {"timeout": "offer.timeout", "decline": "reply.decline", "flagged": "reply.flagged",
                 "unclear": "reply.decline"}[outcome]

        def run(txn: Txn) -> dict[str, Any]:
            offer = _req(txn, f"offers/{offer_id}")
            gap = _req(txn, gap_path(offer["gap_id"]))
            if gap["state"] != "OUTREACH" or offer["status"] != "open":
                txn.update(f"offers/{offer_id}", {"late_outcome": outcome})
                return {"applied": False, "state": gap["state"]}
            actor = "system" if outcome in ("timeout", "flagged") else f"staff:{offer['staff_id']}"
            accepted = dict(gap.get("accepted") or {})
            accepted.pop(offer["staff_id"], None)
            append_in_txn(txn, offer["gap_id"], etype, actor=actor, ts=self._now(),
                          payload=dict(info or {}, offer_id=offer_id, staff_id=offer["staff_id"],
                                       outcome=outcome),
                          gap_fields={"excluded": sorted(set(gap.get("excluded") or []) | {offer["staff_id"]}),
                                      "accepted": accepted})
            txn.update(f"offers/{offer_id}", {"status": outcome, "closed_at": self._now()})
            return {"applied": True, "state": "OUTREACH"}

        return self.store.transaction(run)

    def accept(self, offer_id: str, info: dict[str, Any] | None = None) -> dict[str, Any]:
        withdrawn: list[dict[str, Any]] = []

        def run(txn: Txn) -> dict[str, Any]:
            offer = _req(txn, f"offers/{offer_id}")
            gap = _req(txn, gap_path(offer["gap_id"]))
            if gap["state"] != "OUTREACH" or offer["status"] != "open":
                txn.update(f"offers/{offer_id}", {"status": "late"})
                return {"won": False, "late": True}
            accepted = dict(gap.get("accepted") or {})
            accepted[offer["staff_id"]] = [offer["start"], offer["end"]]
            plan = _req(txn, f"plans/{offer['plan_id']}")
            chosen = next(p for p in plan["candidates"] if p["rank"] == offer["rank"])
            complete = all(
                s["staff_id"] in accepted and accepted[s["staff_id"]][0] <= s["start"]
                and s["end"] <= accepted[s["staff_id"]][1]
                for s in chosen["segments"]
            )
            txn.update(f"offers/{offer_id}", {"status": "accepted", "closed_at": self._now()})
            if not complete:
                txn.update(gap_path(offer["gap_id"]), {"accepted": accepted})
                return {"won": False, "partial": True}
            for oid, other in txn.list("offers"):
                if other["gap_id"] == offer["gap_id"] and other["status"] == "open" and oid != offer_id:
                    txn.update(f"offers/{oid}", {"status": "withdrawn", "closed_at": self._now()})
                    withdrawn.append(other)
            append_in_txn(txn, offer["gap_id"], "reply.accept", actor=f"staff:{offer['staff_id']}",
                          ts=self._now(), payload=dict(info or {}, offer_id=offer_id, plan_id=offer["plan_id"],
                                                       rank=offer["rank"]),
                          gap_fields={"accepted": accepted,
                                      "committing": {"plan_id": offer["plan_id"], "rank": offer["rank"],
                                                     "segments": [{k: s[k] for k in ("staff_id", "start", "end",
                                                                                     "breaks")}
                                                                  for s in chosen["segments"]],
                                                     "cost_breakdown": chosen["cost_breakdown"]}})
            return {"won": True}

        result = self.store.transaction(run)
        offer = self.store.get(f"offers/{offer_id}") or {}
        gap = self._gap(offer["gap_id"])
        if result.get("late"):
            self._outbound(gap, offer["staff_id"], "courtesy",
                           "Thanks so much! Someone else has already taken this shift.")
        for other in withdrawn:
            self.callbacks.send(other["callback_url"], {"offer_id": other["offer_id"], "withdrawn": True})
            self._outbound(gap, other["staff_id"], "withdrawal",
                           "Thanks! This shift has now been covered, so the offer is withdrawn.")
        return result

    def counter(self, offer_id: str, window: dict[str, str], info: dict[str, Any] | None = None) -> dict[str, Any]:
        def run(txn: Txn) -> dict[str, Any]:
            offer = _req(txn, f"offers/{offer_id}")
            gap = _req(txn, gap_path(offer["gap_id"]))
            if gap["state"] != "OUTREACH" or offer["status"] != "open":
                txn.update(f"offers/{offer_id}", {"status": "late"})
                return {"recorded": False}
            day = datetime.fromisoformat(offer["start"])

            def at(hhmm: str) -> str:
                h, m = (int(x) for x in hhmm.split(":"))
                return day.replace(hour=h, minute=m).isoformat()

            win = [at(window["start"]), at(window["end"])]
            windows = dict(gap.get("windows") or {}, **{offer["staff_id"]: win})
            accepted = dict(gap.get("accepted") or {}, **{offer["staff_id"]: win})
            txn.update(gap_path(offer["gap_id"]), {
                "windows": windows, "accepted": accepted,
                "pending_counters": list(gap.get("pending_counters") or []) + [
                    {"offer_id": offer_id, "staff_id": offer["staff_id"], "window": win, **(info or {})}]})
            txn.update(f"offers/{offer_id}", {"status": "countered", "closed_at": self._now()})
            return {"recorded": True}

        return self.store.transaction(run)

    def resolve_counters(self, gap_id: str) -> dict[str, Any]:
        gap = self._gap(gap_id)
        pending = list(gap.get("pending_counters") or [])
        if not pending or gap["state"] != "OUTREACH":
            return {"to_state": None}
        ctx = self.planner_context(gap)
        try:
            result = self.solver(ctx["gap"], ctx, self.rules, self.cfg)
            new_top = result.candidates[0] if result.candidates else None
        except PlanDisagreement:
            new_top = None
        approved = self.store.get(f"plans/{gap.get('approved_plan_id')}") or {}
        old_top = (approved.get("candidates") or [None])[0]
        material, reason = _material_change(old_top, new_top, self.cfg)
        last = pending[-1]
        to_state = "SOLVED" if material else "OUTREACH"
        plan_id = None
        if new_top is not None:
            n = len(self.store.list("plans")) + 1
            plan_id = f"plan-{gap_id}-{n:03d}"
            self.store.transaction(lambda txn: txn.create(
                f"plans/{plan_id}", dict(result.to_dict(), plan_id=plan_id, gap_id=gap_id,
                                         created_at=self._now())))
        fields: dict[str, Any] = {"pending_counters": []}
        if material:
            fields.update(approval_id=None, current_plan_id=plan_id)
        self.store.transaction(lambda txn: append_in_txn(
            txn, gap_id, "reply.counter", actor=f"staff:{last['staff_id']}", ts=self._now(),
            to_state=to_state,
            payload={"counters": pending, "material_change": material, "reason": reason,
                     "new_plan_id": plan_id, "parser_impl": last.get("parser_impl")},
            gap_fields=fields))
        return {"to_state": to_state, "plan_id": plan_id, "material_change": material}

    def commit(self, gap_id: str) -> dict[str, Any]:
        conflict_staff: list[str] = []

        def run(txn: Txn) -> dict[str, Any]:
            gap = txn.get(gap_path(gap_id))
            if gap is not None and gap["state"] == "FILLED":
                return {"result": "ok", "summary": gap.get("summary"), "repeat": True}
            if gap is None or gap["state"] != "COMMITTING":
                raise ApiError(409, "commit needs COMMITTING")
            plan = gap["committing"]
            ctx = self.planner_context(gap, reader=txn)
            bad: dict[str, list[str]] = {}
            for seg in plan["segments"]:
                violations = [r.rule_id for r in blocking_violations(validate_assignment(seg, ctx, self.rules))]
                if violations:
                    bad[seg["staff_id"]] = violations
            if bad:
                conflict_staff.extend(bad)
                append_in_txn(txn, gap_id, "commit.conflict", actor="system", ts=self._now(),
                              payload={"violations": bad},
                              rule_ids=sorted({r for v in bad.values() for r in v}),
                              gap_fields={"excluded": sorted(set(gap.get("excluded") or []) | set(bad)),
                                          "accepted": {}, "committing": None})
                return {"result": "conflict", "violations": bad}
            for i, seg in enumerate(plan["segments"], start=1):
                txn.create(f"shifts/cover-{gap_id}-{i}", {
                    "shift_id": f"cover-{gap_id}-{i}", "outlet": gap["outlet"], "station": gap["station"],
                    "staff_id": seg["staff_id"], "start": seg["start"], "end": seg["end"],
                    "breaks": seg.get("breaks") or [], "status": "scheduled", "source": f"cover:{gap_id}",
                    "synthetic": True})
            for sid, shift in txn.list("shifts"):
                if (shift["staff_id"] == gap["absent_staff_id"] and shift["status"] == "scheduled"
                        and shift["start"] < gap["end"] and shift["end"] > gap["start"]):
                    txn.update(f"shifts/{sid}", {"status": "absent"})
            saved = self._cost_saved_cents(gap, ctx, plan["cost_breakdown"])
            names = " + ".join(f"{ctx['staff'][s['staff_id']]['display_name']} "
                               f"{s['start'][11:16]}-{s['end'][11:16]}" for s in plan["segments"])
            ot = plan["cost_breakdown"]["overtime_cents"] + plan["cost_breakdown"]["rest_day_cents"]
            summary = (f"Filled: {names} at {gap['outlet']}, overtime cost S${ot / 100:.2f} "
                       f"(synthetic).")
            append_in_txn(txn, gap_id, "commit.ok", actor="system", ts=self._now(),
                          payload={"plan_id": plan["plan_id"], "rank": plan["rank"], "summary": summary,
                                   "cost_breakdown": plan["cost_breakdown"]},
                          rule_ids=[r["id"] for r in self.rules],
                          gap_fields={"outcome": "filled", "plan_id": plan["plan_id"],
                                      "cost_saved_sgd": round(saved / 100, 2), "summary": summary,
                                      "filled_at": self._now()})
            return {"result": "ok", "summary": summary}

        result: dict[str, Any] = self.store.transaction(run)
        gap = self._gap(gap_id)
        if result.get("repeat"):
            return result
        if result["result"] == "ok":
            for seg in gap["committing"]["segments"]:
                self._outbound(gap, seg["staff_id"], "confirm",
                               f"Confirmed: {seg['start'][11:16]}-{seg['end'][11:16]} at {gap['outlet']}. Thank you!")
        else:
            for sid in conflict_staff:
                self._outbound(gap, sid, "courtesy", "Thanks! We could not confirm this shift after all.")
        return result

    def _cost_saved_cents(self, gap: dict[str, Any], ctx: dict[str, Any], cost: dict[str, int]) -> int:
        """vs the naive first pick (most reliable free person), priced by the validator (decision 0014)."""
        pool = ranked_pool(ctx["gap"], ctx)
        if not pool:
            return 0
        start = int(datetime.fromisoformat(gap["start"]).timestamp() // 60)
        end = int(datetime.fromisoformat(gap["end"]).timestamp() // 60)
        tz = datetime.fromisoformat(gap["start"]).tzinfo
        breaks = [{"start": datetime.fromtimestamp(a * 60, tz).isoformat(), "duration_min": b - a}
                  for a, b in planned_breaks(start, end, self.cfg)]
        asg = {"staff_id": pool[0], "start": gap["start"], "end": gap["end"], "breaks": breaks}
        naive = cost_breakdown(validate_assignment(asg, ctx, self.rules))
        return (naive["overtime_cents"] + naive["rest_day_cents"]) - (cost["overtime_cents"] + cost["rest_day_cents"])

    def escalation_request(self, gap_id: str, callback_url: str) -> dict[str, Any]:
        gap = self._gap(gap_id)
        staff = {k: v for k, v in self.store.list("staff")}
        borrow = any(v["home_outlet"] != gap["outlet"] and gap["station"] in v["skills"]
                     and k not in (gap.get("excluded") or []) for k, v in staff.items())
        options = [o for o in FALLBACKS if o != "borrow" or borrow]
        server = self.store.get(f"server/{gap_id}") or {"gap_id": gap_id}
        server["fallback_callback"] = callback_url
        self.store.set(f"server/{gap_id}", server)
        self._meta(gap_id, {"fallbacks": options})
        return {"fallbacks": options}


def _remaining(gap: dict[str, Any], ctx: dict[str, Any], rejected: set[str]) -> list[Candidate]:
    """Every legal candidate still in play, with the start of the segment they could take."""
    out = []
    gap_start = datetime.fromisoformat(gap["start"])
    for sid, rec in ctx["staff"].items():
        if sid in ctx["excluded"] or sid == gap["absent_staff_id"] or rec["employee_class"] == "manager_executive":
            continue
        if sid in ctx["windows"]:
            start = datetime.fromisoformat(ctx["windows"][sid][0])
        elif sid in rejected:
            continue
        else:
            start = gap_start
        out.append(Candidate(sid, start, int(ctx["travel"][sid][gap["outlet"]])))
    return out


def _plan_summary(plan: dict[str, Any] | None) -> dict[str, Any] | None:
    if not plan:
        return None
    return {"rank": plan["rank"], "staff_ids": plan["staff_ids"],
            "segments": [{k: s[k] for k in ("staff_id", "start", "end")} for s in plan["segments"]],
            "cost_breakdown": plan["cost_breakdown"]}


def _material_change(old: dict[str, Any] | None, new: dict[str, Any] | None,
                     cfg: dict[str, Any]) -> tuple[bool, str]:
    """§5.1: back to SOLVED only if the plan changes materially (time shift > 30 min or cost up)."""
    if new is None:
        return False, "no legal plan; outreach continues to escalation"
    if old is None:
        return True, "no approved plan to compare"
    rule = cfg["material_change"]
    if rule["cost_up"] and new["cost_breakdown"]["total_cents"] > old["cost_breakdown"]["total_cents"]:
        return True, "cost up"
    old_marks = [datetime.fromisoformat(x) for s in old["segments"] for x in (s["start"], s["end"])]
    for s in new["segments"]:
        for x in (s["start"], s["end"]):
            t = datetime.fromisoformat(x)
            if min(abs((t - o).total_seconds()) for o in old_marks) > int(rule["time_shift_min"]) * 60:
                return True, "time shift over the threshold"
    return False, "same times, cost not up"


# ---------------------------------------------------------------------- P0 metric scans


def unapproved_outbound(store: Store) -> int:
    count = 0
    for _, msg in store.list("outbound"):
        approval = store.get(f"approvals/{msg.get('approval_id')}") if msg.get("approval_id") else None
        if not approval or approval["decision"] != "approve" or approval["gap_id"] != msg["gap_id"]:
            count += 1
    return count


def pii_leaks(store: Store) -> int:
    leaks = 0
    for gap_id, gap in store.list("gaps"):
        leaks += len(find_pii(gap))
        for _, ev in store.list(f"gaps/{gap_id}/events"):
            leaks += len(find_pii(ev))
    for _, q in store.list("quarantine"):
        leaks += len(find_pii(q.get("redacted_text", "")))
    for _, m in store.list("outbound"):
        leaks += len(find_pii(m))
    return leaks


def escalation_late(store: Store) -> int:
    late = 0
    for gap_id, _ in store.list("gaps"):
        for _, ev in store.list(f"gaps/{gap_id}/events"):
            if ev["type"] == "escalation.due":
                t_esc = ev["payload"].get("t_esc")
                if t_esc is None or datetime.fromisoformat(ev["ts"]) > datetime.fromisoformat(t_esc) + timedelta(seconds=0):
                    late += 1
    return late


def outcome_missing(store: Store) -> int:
    return sum(1 for _, g in store.list("gaps") if g["state"] not in TERMINAL_STATES or not g.get("outcome"))
