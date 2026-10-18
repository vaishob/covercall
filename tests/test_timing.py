"""policy/timing.py (§5.2)."""

from __future__ import annotations

from datetime import datetime, timedelta

from policy.compile_cpsat import load_company_config
from policy.timing import (
    Candidate,
    locked_t_esc,
    must_fill_by,
    plan_offers,
    reply_window_min,
    slack_min,
    t_esc,
)

CFG = load_company_config()
START = datetime.fromisoformat("2026-11-03T07:00:00+08:00")


def at(hhmm: str) -> datetime:
    h, m = (int(x) for x in hhmm.split(":"))
    return START.replace(hour=h, minute=m)


def cand(sid: str, travel: int) -> Candidate:
    return Candidate(sid, START, travel)


def test_must_fill_by_slack_and_window() -> None:
    assert must_fill_by(START, 16, 10) == at("06:34")
    deadlines = [at("06:34"), at("06:22")]
    assert slack_min(at("06:02"), deadlines) == 32
    assert reply_window_min(at("06:02"), deadlines, CFG) == 10  # min(w_max, 32/3)
    assert reply_window_min(at("06:19"), deadlines, CFG) == 5  # 15/3
    assert reply_window_min(at("06:31"), deadlines, CFG) == 3  # floor at w_min
    assert t_esc(deadlines, CFG, at("06:02")) == at("06:19")


def test_single_offer_when_slack_is_high() -> None:
    plan = plan_offers(at("06:02"), [cand("a", 16), cand("b", 28)], [cand("a", 16), cand("b", 28)], CFG)
    assert plan.mode == "single" and [c.staff_id for c in plan.offers] == ["a"]
    assert plan.window_min == 10


def test_fan_out_when_slack_below_threshold() -> None:
    ranked = [cand(s, 16) for s in "abcd"]
    plan = plan_offers(at("06:12"), ranked, ranked, CFG)
    assert plan.slack_min == 22 and plan.mode == "fanout"
    assert [c.staff_id for c in plan.offers] == ["a", "b", "c"]  # fanout_n = 3


def test_viability_drops_candidates_who_cannot_answer_in_time() -> None:
    # b must be filled by 06:22; at 06:15 a 4 min window still fits, but at 06:20 it does not.
    ranked = [cand("b", 28), cand("a", 16)]
    plan = plan_offers(at("06:15"), ranked, ranked, CFG, locked=at("06:19"))
    assert [c.staff_id for c in plan.offers][0] == "b"
    plan = plan_offers(at("06:19"), ranked, ranked, CFG, locked=at("06:25"))
    assert all(c.staff_id != "b" for c in plan.offers)


def test_escalate_when_no_candidate_or_t_esc_reached() -> None:
    assert plan_offers(at("06:02"), [], [], CFG).mode == "escalate"
    plan = plan_offers(at("06:20"), [cand("a", 16)], [cand("a", 16)], CFG, locked=at("06:19"))
    assert plan.mode == "escalate" and plan.reason == "t_esc reached"


def test_window_never_outlives_locked_t_esc() -> None:
    for minute in range(2, 19):
        t = at(f"06:{minute:02d}")
        plan = plan_offers(t, [cand("a", 16)], [cand("a", 16)], CFG, locked=at("06:19"))
        if plan.mode != "escalate":
            assert t + timedelta(minutes=plan.window_min) <= at("06:19")


def test_locked_t_esc_is_never_before_approval() -> None:
    assert locked_t_esc(at("06:02"), [cand("a", 16)], CFG) == at("06:19")
    assert locked_t_esc(at("06:25"), [cand("a", 16)], CFG) == at("06:25")  # due at once
    assert locked_t_esc(at("06:02"), [], CFG) == at("06:02")
