"""Deterministic local driver for ``workflows/coverage_cascade.yaml`` (docs/decisions/0010).

Cloud Workflows has no local emulator. This driver executes the same state machine, step for step
(``step("<yaml step name>")``), through the same ``api`` routes (FastAPI ``TestClient``), with:

- a simulated clock (nothing sleeps; time jumps to the next reply or timeout),
- ``MemoryStore`` in place of Firestore (default and ``sim`` databases kept separate),
- simulated personas from the ``sim`` store and scenario overrides (persona-sim logic),
- a lead who is either simulated ("auto": approves by tap and picks the first ranked fallback at
  once) or real ("external": the local dev server waits for the browser's tap).

``python -m evals.runners.local_cascade`` runs J2 (S-017) and J3 (S-002, nobody replies) and exits
non-zero unless both end in the expected terminal outcome with ``verify_chain`` OK, zero violations
and zero P0 counters. All data is synthetic.
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from functools import partial
from pathlib import Path
from typing import Any

import yaml
from fastapi.testclient import TestClient

from datagen.loader import load_data
from policy.compile_cpsat import load_company_config, load_rules, solve
from policy.validate import blocking_violations, validate_assignment
from services.api.app.core import (
    Api,
    escalation_late,
    outcome_missing,
    pii_leaks,
    unapproved_outbound,
)
from services.api.app.deps import (
    LocalAgent,
    LocalGuard,
    QueueCallbacks,
    RecordingLauncher,
    RecordingMessenger,
    SimClock,
)
from services.api.app.events import verify_chain
from services.api.app.main import create_app
from services.common.store import MemoryStore
from services.persona_sim.app import logic as persona_sim

MAX_ROUNDS = 80
Observer = Callable[[str, str], None]  # (gap_id, yaml step name) after each step


@dataclass
class _Branch:
    offer: dict[str, Any]
    url: str
    offer_id: str
    deadline: datetime
    done: bool = False


class _LeadTimeout(Exception):
    """An external lead did not answer before the wait expired (the YAML's TimeoutError path)."""


class LocalRun:
    """A local environment (stores, clock, api, persona-sim) plus the workflow driver."""

    def __init__(self, scenario: dict[str, Any] | None, data: dict[str, Any], cfg: dict[str, Any],
                 rules: list[dict[str, Any]], time_limit_s: float | None = None,
                 guard_fails: bool = False, scenarios: list[dict[str, Any]] | None = None,
                 allowed_origins: list[str] | None = None):
        self.scenario = scenario
        self.data, self.cfg, self.rules = data, cfg, rules
        self.trace: list[str] = []
        self.observer: Observer | None = None
        start = (scenario or (scenarios or [{}])[0]).get("now")
        if not start:
            raise ValueError("need a scenario to start the simulated clock")
        self.clock = SimClock(datetime.fromisoformat(start))
        self.store, self.sim = MemoryStore(), MemoryStore()
        for scen in ([scenario] if scenario else []) + list(scenarios or []):
            _seed(self.store, self.sim, data, scen)
        self.callbacks = QueueCallbacks()
        self.messenger = RecordingMessenger(on_offer=self._persona_receives)
        self.api = Api(self.store, cfg, rules, self.clock, LocalGuard(fail=guard_fails),
                       LocalAgent(cfg), self.messenger, self.callbacks, RecordingLauncher(),
                       solver=partial(solve, time_limit_s=time_limit_s))
        self.app = create_app(self.api, internal_auth=lambda: None,
                              allowed_origins=allowed_origins or ["http://localhost:3000"])
        self.client = TestClient(self.app)
        self._cb = 0
        self._lock = threading.Lock()
        self.gap_id = ""

    # ---------------------------------------------------------------- plumbing
    def step(self, name: str, gap_id: str = "") -> None:
        self.trace.append(name)
        if self.observer is not None:
            self.observer(gap_id or self.gap_id, name)

    def post(self, path: str, body: dict[str, Any], client: TestClient | None = None) -> dict[str, Any]:
        resp = (client or self.client).post(path, json=body)
        if resp.status_code != 200:
            raise RuntimeError(f"{path} -> {resp.status_code}: {resp.text}")
        return dict(resp.json())

    def get(self, path: str, client: TestClient | None = None) -> Any:
        resp = (client or self.client).get(path)
        if resp.status_code != 200:
            raise RuntimeError(f"GET {path} -> {resp.status_code}: {resp.text}")
        return resp.json()

    def transition(self, key: str, body: dict[str, Any], gap_id: str = "",
                   client: TestClient | None = None) -> dict[str, Any]:
        gid = gap_id or self.gap_id
        return self.post("/internal/transition",
                         dict(body, gap_id=gid, idempotency_key=f"local:{gid}:{key}"), client)

    def create_callback(self, gap_id: str = "") -> str:
        with self._lock:
            self._cb += 1
            return f"local://callback/{gap_id or self.gap_id}/{self._cb}"

    def _persona_receives(self, message: dict[str, Any]) -> None:
        offer = {"offer_id": message["offer_id"], "staff_id": message["staff_id"],
                 "start": message["start"], "end": message["end"], "attempt": message["attempt"]}
        scenario = self.sim.get(f"scenarios/{message.get('scenario_id')}") or {}
        persona_sim.schedule(self.sim, offer, scenario, self.clock.now())

    def _deliver_due(self, client: TestClient | None = None) -> None:
        for item in persona_sim.due(self.sim, self.clock.now()):
            persona_sim.mark_delivered(self.sim, item["message_id"])
            self.post("/replies", {"message_id": item["message_id"], "offer_id": item["offer_id"],
                                   "text": item["text"], "channel": "sim"}, client)

    def _lead_acts(self, url: str, kind: str, gap_id: str = "", client: TestClient | None = None) -> None:
        """The simulated lead: approve by tap, or pick the first ranked fallback, at once."""
        gid = gap_id or self.gap_id
        if kind == "approval":
            pending = self.get(f"/gaps/{gid}/approval", client)
            self.post("/approvals", {"gap_id": gid, "nonce": pending["nonce"], "decision": "approve",
                                     "channel": "tap", "transcript": ""}, client)
        else:
            view = self.get(f"/gaps/{gid}", client)
            self.post("/fallbacks", {"gap_id": gid, "option": view["gap"]["fallbacks"][0]}, client)

    def _await_lead(self, url: str, kind: str, gap_id: str, client: TestClient, lead: str,
                    timeout_s: float) -> dict[str, Any]:
        if lead == "auto":
            self._lead_acts(url, kind, gap_id, client)
        deadline = time.monotonic() + timeout_s
        while True:
            queue = self.callbacks.queues.get(url) or []
            if queue:
                return queue.pop(0)
            if lead == "auto" or time.monotonic() > deadline:
                raise _LeadTimeout(kind)
            time.sleep(0.1)

    # ---------------------------------------------------------------- the workflow
    def run(self) -> dict[str, Any]:
        if self.scenario is None:
            raise ValueError("run() needs a scenario")
        self.gap_id = self.post("/gaps", {"scenario_id": self.scenario["id"]})["gap_id"]
        self.execute(self.gap_id)
        return self._finish()

    def execute(self, gap_id: str, client: TestClient | None = None, lead: str = "auto",
                pace_s: float = 0.0, lead_timeout_s: float = 1800.0) -> None:
        """Run coverage-cascade for ``gap_id`` (the YAML ``main``), step by step."""
        c = client or self.client
        step = partial(self.step, gap_id=gap_id)
        tr = partial(self.transition, gap_id=gap_id, client=c)
        post = partial(self.post, client=c)
        step("init")
        step("guard_input")
        g = post("/internal/guard-input", {"gap_id": gap_id})
        step("guard_route")
        if g["status"] == "unavailable":
            step("guard_unavailable")
            tr("guard.unavailable", {"type": "guard.unavailable", "actor": "system",
                                     "payload": {"guard_impl": "stub-v0"}})
            return
        if g["status"] != "ok":
            step("guard_flagged")
            tr("guard.flagged", {"type": "guard.flagged", "actor": "system",
                                 "payload": {"labels": g["labels"], "guard_impl": "stub-v0"}})
            return
        step("guarded")
        tr("input.guarded", {"type": "input.guarded", "actor": "system",
                             "payload": {"guard_impl": "stub-v0", "labels": g["labels"]}})
        nxt, plan_id, rounds = "solve", "", 0
        n: dict[str, Any] = {}
        while nxt != "done":
            if nxt == "solve":
                step("solve")
                s = post("/internal/solve", {"gap_id": gap_id})
                step("solve_route")
                if s["status"] == "disagreement":
                    step("disagreement")
                    tr("plan.disagreement", {"type": "plan.disagreement", "actor": "system",
                                             "rule_ids": s["rule_ids"], "payload": {"details": s["details"]}})
                    nxt = "done"
                    continue
                step("solved")
                tr(f"plan.solved:{s['plan_id']}", {"type": "plan.solved", "actor": "system",
                                                   "rule_ids": s["rule_ids"],
                                                   "payload": {"plan_id": s["plan_id"], "status": s["status"]}})
                step("set_plan")
                plan_id = s["plan_id"]
                nxt = "approval_cb"
            elif nxt == "approval_cb":
                step("approval_cb")
                acb = self.create_callback(gap_id)
                step("approval_req")
                post("/internal/approval-request", {"gap_id": gap_id, "plan_id": plan_id, "callback_url": acb})
                step("await_approval")
                try:
                    ar = self._await_lead(acb, "approval", gap_id, c, lead, lead_timeout_s)
                except _LeadTimeout:
                    step("approval_timeout")
                    step("cancel_no_approval")
                    tr("gap.cancelled", {"type": "gap.cancelled", "actor": "system",
                                         "payload": {"reason": "no lead approval before the wait expired"}})
                    nxt = "done"
                    continue
                step("approval_route")
                if ar.get("cancel"):
                    nxt = "cancelled"
                elif ar.get("decision") == "approve":
                    step("approved")
                    tr(f"plan.approved:{ar['approval_id']}", {"type": "plan.approved", "actor": "lead",
                                                              "payload": {"approval_id": ar["approval_id"]}})
                    nxt = "outreach"
                else:
                    step("rejected")
                    tr(f"plan.rejected:{ar['approval_id']}", {"type": "plan.rejected", "actor": "lead",
                                                              "payload": {"approval_id": ar["approval_id"]}})
                    nxt = "solve"
            elif nxt == "outreach":
                rounds += 1
                if rounds > MAX_ROUNDS:
                    raise RuntimeError(f"{gap_id}: more than {MAX_ROUNDS} outreach rounds")
                step("outreach")
                step("next_offers")
                n = post("/internal/next-offers", {"gap_id": gap_id})
                step("outreach_route")
                if n["mode"] == "escalate":
                    nxt = "escalate"
                    continue
                step("send_offers")
                winner, cancelled = self._parallel_offers(gap_id, n, rounds, c, pace_s)
                step("after_offers")
                if cancelled:
                    nxt = "cancelled"
                elif winner:
                    nxt = "commit"
                else:
                    step("counters")
                    cr = post("/internal/counter-resolve", {"gap_id": gap_id})
                    step("counter_route")
                    if cr.get("to_state") == "SOLVED":
                        step("reapprove")
                        plan_id = cr["plan_id"]
                        nxt = "approval_cb"
                    else:
                        nxt = "outreach"
            elif nxt == "commit":
                step("commit")
                result = post("/internal/commit", {"gap_id": gap_id})
                step("commit_route")
                nxt = "done" if result["result"] == "ok" else "outreach"
            elif nxt == "escalate":
                step("escalate")
                tr("escalation.due", {"type": "escalation.due", "actor": "system",
                                      "payload": {"t_esc": n["t_esc"], "reason": n["reason"]}})
                step("fallback_cb")
                fcb = self.create_callback(gap_id)
                step("fallback_req")
                post("/internal/escalation-request", {"gap_id": gap_id, "callback_url": fcb})
                step("await_fallback")
                try:
                    fr = self._await_lead(fcb, "fallback", gap_id, c, lead, lead_timeout_s)
                except _LeadTimeout:
                    step("fallback_timeout")
                    step("resolve_unfilled")
                    tr("fallback.chosen", {"type": "fallback.chosen", "actor": "system",
                                           "payload": {"option": "unfilled",
                                                       "reason": "no fallback chosen before the wait expired"}})
                    nxt = "done"
                    continue
                step("fallback_route")
                if fr.get("cancel"):
                    nxt = "cancelled"
                    continue
                step("resolved")
                tr("fallback.chosen", {"type": "fallback.chosen", "actor": "lead",
                                       "payload": {"option": fr["option"]}})
                nxt = "done"
            elif nxt == "cancelled":
                step("cancelled")
                tr("gap.cancelled", {"type": "gap.cancelled", "actor": "lead",
                                     "payload": {"reason": "lead cancelled"}})
                nxt = "done"
        step("done")

    def _parallel_offers(self, gap_id: str, n: dict[str, Any], rnd: int, c: TestClient,
                         pace_s: float) -> tuple[str | None, bool]:
        """The ``send_offers`` parallel for-loop: one callback endpoint and one wait per offer."""
        step = partial(self.step, gap_id=gap_id)
        post = partial(self.post, client=c)
        branches: list[_Branch] = []
        winner: str | None = None
        cancelled = False
        start = self.clock.now()
        for offer in n["offers"]:
            step("create_cb")
            url = self.create_callback(gap_id)
            step("register_offer")
            reg = post("/internal/offers", {
                "gap_id": gap_id, "offer": offer, "callback_url": url, "window_s": n["window_s"],
                "fanout_group": f"{n['mode']}:{rnd}", "key": f"local:{gap_id}:offer:{rnd}:{offer['staff_id']}"})
            deadline = datetime.fromtimestamp(start.timestamp() + n["window_s_real"], start.tzinfo)
            branches.append(_Branch(offer, url, reg["offer_id"], deadline))
        while any(not b.done for b in branches):
            progressed = False
            for b in branches:
                queue = self.callbacks.queues.get(b.url) or []
                if b.done or not queue:
                    continue
                reply = queue.pop(0)
                progressed = True
                b.done = True
                step("wait_reply")
                step("reply_route")
                if reply.get("withdrawn"):
                    continue
                if reply.get("cancel"):
                    step("mark_cancel")
                    cancelled = True
                    continue
                step("read_reply")
                r = post("/internal/reply", {"offer_id": b.offer_id, "message_id": reply["message_id"]})
                step("classify")
                if r["flagged"]:
                    step("on_flagged")
                    post("/internal/offer-outcome", {"offer_id": b.offer_id, "outcome": "flagged",
                                                     "info": {"guard_labels": r["guard_labels"],
                                                              "guard_impl": r["guard_impl"]}})
                elif r["parsed"]["intent"] == "accept":
                    step("on_accept")
                    acc = post("/internal/accept", {"offer_id": b.offer_id, "info": {
                        "parser_impl": r["parsed"]["parser_impl"], "guard_impl": r["guard_impl"]}})
                    step("accept_route")
                    if acc["won"]:
                        step("set_winner")
                        winner = b.offer_id
                elif r["parsed"]["intent"] == "counter":
                    step("on_counter")
                    post("/internal/counter", {"offer_id": b.offer_id, "window": r["parsed"]["counter_window"],
                                               "info": {"parser_impl": r["parsed"]["parser_impl"]}})
                else:
                    step("on_decline")
                    post("/internal/offer-outcome", {"offer_id": b.offer_id, "outcome": "decline", "info": {
                        "intent": r["parsed"]["intent"], "reason_category": r["parsed"]["reason_category"],
                        "parser_impl": r["parsed"]["parser_impl"], "guard_impl": r["guard_impl"]}})
            if progressed:
                continue
            if pace_s:
                time.sleep(pace_s)  # dev server only: let a viewer see each step
            open_deadlines = [b.deadline for b in branches if not b.done]
            due = persona_sim.next_due_time(self.sim)
            if due is not None and due <= min(open_deadlines):
                self.clock.advance_to(due)
                self._deliver_due(c)
                continue
            t = min(open_deadlines)
            self.clock.advance_to(t)
            for b in branches:
                if not b.done and b.deadline <= t:
                    b.done = True
                    step("wait_reply")
                    step("on_offer_timeout")
                    post("/internal/offer-outcome", {"offer_id": b.offer_id, "outcome": "timeout"})
        return winner, cancelled

    def _finish(self, gap_id: str = "") -> dict[str, Any]:
        gid = gap_id or self.gap_id
        # Late replies still in the outbox arrive after the outcome: they must get a courtesy reply.
        while (due := persona_sim.next_due_time(self.sim)) is not None:
            self.clock.advance_to(due)
            self._deliver_due()
        gap = self.store.get(f"gaps/{gid}") or {}
        events = [ev for _, ev in self.store.list(f"gaps/{gid}/events")]
        offers = [o for _, o in self.store.list("offers") if o["gap_id"] == gid]
        segments = (gap.get("committing") or {}).get("segments") or [] if gap.get("state") == "FILLED" else []
        cost = (gap.get("committing") or {}).get("cost_breakdown") if segments else None
        cost = cost or {"base_cents": 0, "overtime_cents": 0, "rest_day_cents": 0, "total_cents": 0}
        violations: list[str] = []
        if segments:
            ctx = self.api.planner_context(dict(gap, excluded=[], windows={}, accepted={}))
            ctx["shifts"] = [s for s in ctx["shifts"] if not s.get("source")]
            for seg in segments:
                violations += [r.rule_id for r in blocking_violations(validate_assignment(seg, ctx, self.rules))]
        reported = datetime.fromisoformat(gap["reported_at"])
        ttf = None
        late_arrivals = 0
        if gap.get("filled_at"):
            filled = datetime.fromisoformat(gap["filled_at"])
            ttf = round((filled - reported).total_seconds() / 60, 2)
            travel = (self.store.get("config/travel") or {})["staff_to_outlet_min"]
            late_arrivals = sum(
                1 for s in segments
                if filled.timestamp() + 60 * int(travel[s["staff_id"]][gap["outlet"]])
                > datetime.fromisoformat(s["start"]).timestamp())
        chain = verify_chain(self.store, gid)
        return {
            "scenario_id": gap.get("scenario_id"),
            "gap_id": gid,
            "state": gap.get("state"),
            "outcome": gap.get("outcome"),
            "assignment": [{"staff_id": s["staff_id"], "start": s["start"], "end": s["end"]} for s in segments],
            "cost_breakdown": cost,
            "overtime_cost_cents": cost["overtime_cents"] + cost["rest_day_cents"],
            "time_to_fill_min": ttf,
            "late_arrivals": late_arrivals,
            "violations": len(violations),
            "violated_rules": violations,
            "disagreements": sum(1 for e in events if e["type"] == "plan.disagreement"),
            "verify_chain": chain.to_dict(),
            "events": [e["type"] for e in events],
            "offers": [{"offer_id": o["offer_id"], "staff_id": o["staff_id"], "start": o["start"],
                        "end": o["end"], "status": o["status"], "fanout_group": o["fanout_group"],
                        "late_reply": bool(o.get("late_reply"))} for o in offers],
            "outbound_kinds": [m["kind"] for _, m in self.store.list("outbound")],
            "p0": {"unapproved_outbound": unapproved_outbound(self.store), "pii_leak": pii_leaks(self.store),
                   "escalation_late": escalation_late(self.store), "outcome_missing": outcome_missing(self.store),
                   "solver_validator_disagreements": sum(1 for e in events if e["type"] == "plan.disagreement"),
                   "rule_violations": len(violations)},
            "steps": list(self.trace),
            "synthetic": True,
        }


def _seed(store: MemoryStore, sim: MemoryStore, data: dict[str, Any], scenario: dict[str, Any]) -> None:
    if store.get("config/travel") is None:
        for sid, rec in data["staff"].items():
            store.set(f"staff/{sid}", rec)
        for oid, rec in data["outlets"].items():
            store.set(f"outlets/{oid}", rec)
        for s in data["shifts"]:
            store.set(f"shifts/{s['shift_id']}", s)
        for lid, rec in data["ledgers"].items():
            store.set(f"ledgers/{lid}", rec)
        store.set("config/travel", dict(data["travel_meta"], staff_to_outlet_min=data["travel"]))
        for pid, rec in data["personas"].items():
            sim.set(f"personas/{pid}", rec)
    public: dict[str, Any] = {k: scenario[k] for k in ("id", "description", "now", "seed", "gap") if k in scenario}
    public["overrides"] = scenario.get("overrides") or []
    store.set(f"scenarios/{scenario['id']}", dict(public, synthetic=True))  # no personas here
    sim.set(f"scenarios/{scenario['id']}", dict(scenario))


def run_scenario(scenario: dict[str, Any], data: dict[str, Any] | None = None,
                 time_limit_s: float | None = None, **kw: Any) -> dict[str, Any]:
    return LocalRun(scenario, data or load_data(), load_company_config(), load_rules(),
                    time_limit_s=time_limit_s, **kw).run()


def load_scenario(sid: str) -> dict[str, Any]:
    return dict(yaml.safe_load(Path(f"evals/datasets/golden/{sid}.yaml").read_text(encoding="utf-8")))


def check_j2(res: dict[str, Any]) -> list[str]:
    problems = []
    by_staff: dict[str, list[str]] = {}
    for o in res["offers"]:
        by_staff.setdefault(o["staff_id"], []).append(o["status"])
    if res["outcome"] != "filled":
        problems.append(f"J2 outcome {res['outcome']} != filled")
    for sid, status in (("stf_019", "decline"), ("stf_022", "countered"), ("stf_008", "timeout")):
        if status not in by_staff.get(sid, []):
            problems.append(f"J2 expected {sid} {status}, got {by_staff.get(sid)}")
    for etype in ("reply.decline", "reply.counter", "offer.timeout", "reply.accept", "commit.ok"):
        if etype not in res["events"]:
            problems.append(f"J2 missing event {etype}")
    return problems


def check_j3(res: dict[str, Any]) -> list[str]:
    problems = []
    groups = [o["fanout_group"] for o in res["offers"] if str(o["fanout_group"]).startswith("fanout:")]
    if len(groups) < 2:
        problems.append("J3 expected a fan-out round with several offers at once")
    if "escalation.due" not in res["events"] or res["state"] != "RESOLVED":
        problems.append(f"J3 expected ESCALATED -> RESOLVED, got {res['state']}")
    return problems


def common_checks(res: dict[str, Any]) -> list[str]:
    problems = []
    if not res["verify_chain"]["ok"]:
        problems.append(f"verify_chain failed: {res['verify_chain']['errors']}")
    for name, value in res["p0"].items():
        if value:
            problems.append(f"P0 {name} = {value}")
    if res["state"] not in ("FILLED", "RESOLVED", "CANCELLED", "HELD") or not res["outcome"]:
        problems.append("gap did not end in a recorded terminal outcome")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run J2 and J3 through the local cascade driver")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    data = load_data()
    failures: list[str] = []
    report = {}
    for journey, sid, check in (("J2", "S-017", check_j2), ("J3", "S-002", check_j3)):
        res = run_scenario(load_scenario(sid), data)
        problems = check(res) + common_checks(res)
        failures += [f"{journey} {p}" for p in problems]
        report[journey] = res
        if not args.json:
            print(f"{journey} ({sid}): state={res['state']} outcome={res['outcome']} "
                  f"time_to_fill_min={res['time_to_fill_min']} verify_chain={'OK' if res['verify_chain']['ok'] else 'FAIL'} "
                  f"events={res['verify_chain']['events']} violations={res['violations']} p0={res['p0']}")
            print(f"  events: {' -> '.join(res['events'])}")
            print("  offers: " + "; ".join(f"{o['staff_id']} {o['start'][11:16]}-{o['end'][11:16]} "
                                          f"{o['status']} [{o['fanout_group']}]"
                                          + (" (late reply: courtesy sent)" if o["late_reply"] else "")
                                          for o in res["offers"]))
            print("  " + ("PASS" if not problems else "FAIL: " + "; ".join(problems)))
    if args.json:
        print(json.dumps(report, indent=2, default=str))
    print("All data is synthetic.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
