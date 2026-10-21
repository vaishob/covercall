"""DEMO_CLOCK_OFFSET_DAYS (decision 0025): the demo journeys behave as before 3 Nov on any date to 6 Nov.

Production's clock is real and a scenario cannot reset it, so these runs use a clock without
``reset_to`` started at a judge's time. All data is synthetic.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
import yaml

from datagen.loader import load_data
from evals.runners.local_cascade import LocalRun, check_j2, common_checks
from policy.compile_cpsat import load_company_config, load_rules
from services.api.app.main import demo_clock_offset_from_env

CFG = load_company_config()
RULES = load_rules()
LATE = datetime.fromisoformat("2026-11-06T23:59:00+08:00")  # last minute of judging
VOICE = {"outlet": "bugis", "station": "barista", "shift_start": "2026-11-03T07:00:00+08:00",
         "staff_name": "Ali", "text": "Ali is sick for the 7am barista shift at Bugis on Tuesday, 3 November."}


@dataclass
class RealClock:
    """Production-like: moves forward only; a scenario cannot set it."""

    current: datetime

    def now(self) -> datetime:
        return self.current

    def advance_to(self, t: datetime) -> None:
        self.current = max(self.current, t)


@pytest.fixture(scope="module")
def data() -> dict[str, Any]:
    return load_data()


def _run(data: dict[str, Any], judge: datetime, offset_days: int) -> LocalRun:
    scenarios = [yaml.safe_load(Path(f"evals/datasets/golden/{s}.yaml").read_text(encoding="utf-8"))
                 for s in ("S-017", "S-002")]
    run = LocalRun(None, data, CFG, RULES, scenarios=scenarios)
    run.clock = RealClock(judge)  # type: ignore[assignment]
    run.api.clock = run.clock
    run.api.demo_isolation = True
    run.api.clock_offset = timedelta(days=offset_days)
    return run


def _journey(run: LocalRun, body: dict[str, Any]) -> dict[str, Any]:
    gap_id = run.post("/gaps", body)["gap_id"]
    run.gap_id = gap_id
    run.execute(gap_id)
    return run._finish(gap_id)


def test_without_offset_s017_escalates_at_once_after_3_nov(data: dict[str, Any]) -> None:
    """The bug: on the real clock the demo shift is past, so no offer is ever sent."""
    res = _journey(_run(data, LATE, 0), {"scenario_id": "S-017"})
    assert res["state"] == "RESOLVED" and res["offers"] == []


def test_offset_s017_fills_with_single_offers(data: dict[str, Any]) -> None:
    run = _run(data, LATE, 7)
    res = _journey(run, {"scenario_id": "S-017"})
    assert check_j2(res) == [] and common_checks(res) == [] and res["late_arrivals"] == 0
    assert all(o["fanout_group"].startswith("single:") for o in res["offers"])
    gap = run.store.require(f"gaps/{res['gap_id']}")
    assert gap["t_esc_locked"] == "2026-11-03T06:19:00+08:00"  # deadlines keep the scenario's dates
    events = [ev for _, ev in run.store.list(f"gaps/{res['gap_id']}/events")]
    assert all(ev["ts"] >= LATE.isoformat() for ev in events)  # timestamps stay real


def test_offset_nobody_replies_times_out_then_resolves(data: dict[str, Any]) -> None:
    res = _journey(_run(data, LATE, 7), {"scenario_id": "S-002"})
    assert common_checks(res) == []
    assert res["state"] == "RESOLVED" and res["events"][-2:] == ["escalation.due", "fallback.chosen"]
    assert len(res["offers"]) > 1 and {o["status"] for o in res["offers"]} == {"timeout"}
    assert all(o["fanout_group"].startswith("single:") for o in res["offers"])


def test_offset_voice_report_for_3_nov_fills(data: dict[str, Any]) -> None:
    res = _journey(_run(data, LATE, 7), dict(VOICE))
    assert common_checks(res) == [] and res["state"] == "FILLED"
    assert all(o["fanout_group"].startswith("single:") for o in res["offers"])


def test_countdown_uses_the_offset_and_the_view_clock_stays_real(data: dict[str, Any]) -> None:
    run = _run(data, LATE, 7)
    gap_id = run.post("/gaps", {"scenario_id": "S-017"})["gap_id"]
    run.gap_id = gap_id
    run.transition("guarded", {"type": "input.guarded", "actor": "system"})
    plan_id = run.post("/internal/solve", {"gap_id": gap_id})["plan_id"]
    run.transition("solved", {"type": "plan.solved", "actor": "system", "payload": {"plan_id": plan_id}})
    run.post("/internal/approval-request", {"gap_id": gap_id, "plan_id": plan_id, "callback_url": "local://a"})
    nonce = run.get(f"/gaps/{gap_id}/approval")["nonce"]
    approval = run.post("/approvals", {"gap_id": gap_id, "nonce": nonce, "decision": "approve", "channel": "tap"})
    run.transition("approved", {"type": "plan.approved", "actor": "lead",
                                "payload": {"approval_id": approval["approval_id"]}})
    view = run.get(f"/gaps/{gap_id}")
    t_esc = datetime.fromisoformat("2026-11-03T06:19:00+08:00")
    assert view["clock"]["seconds_to_escalation"] == int((t_esc - (LATE - timedelta(days=7))).total_seconds())
    assert view["clock"]["seconds_to_escalation"] > 3 * 86400  # still days, as before 3 Nov
    assert view["clock"]["now"] == LATE.isoformat()


def test_offset_env_parsing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DEMO_CLOCK_OFFSET_DAYS", raising=False)
    assert demo_clock_offset_from_env() == timedelta(0)  # unset: the real clock
    monkeypatch.setenv("DEMO_CLOCK_OFFSET_DAYS", "7")
    assert demo_clock_offset_from_env() == timedelta(days=7)
    for bad in ("-1", "31", "1.5", "seven"):
        monkeypatch.setenv("DEMO_CLOCK_OFFSET_DAYS", bad)
        with pytest.raises(ValueError):
            demo_clock_offset_from_env()
