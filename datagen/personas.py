"""Simulated staff behaviour (§8.1 ``sim`` database, §8.3).

Only the simulation reads this: ``persona-sim``, the eval runners and the baseline, which all use
the same personas and seeds. The planner (solver, api) never sees hidden availability (§8.1).

Each reply's intent is fixed here first. Surface text is written afterwards from the intent and a
style vector, and the intent label is ground truth (§8.3).
"""

from __future__ import annotations

import math
import random
from datetime import datetime, timedelta
from typing import Any

INTENTS = ("accept", "decline", "counter", "silent")


def _rng(*parts: Any) -> random.Random:
    # String seeds are hashed deterministically by random.Random (SHA-512), across runs and OSes.
    return random.Random(":".join(str(p) for p in parts))


def _on_date(day: datetime, hhmm: str) -> datetime:
    h, m = (int(x) for x in hhmm.split(":"))
    return day.replace(hour=h, minute=m, second=0, microsecond=0)


def busy_blocks(persona: dict[str, Any], day: datetime) -> list[tuple[datetime, datetime]]:
    """Hidden availability on ``day``: lecture blocks, or the whole day in an exam week."""
    hidden = persona.get("hidden_availability") or {}
    iso_year, iso_week, iso_weekday = day.isocalendar()
    if f"{iso_year}-W{iso_week:02d}" in (hidden.get("exam_weeks") or []):
        return [(_on_date(day, "00:00"), _on_date(day, "00:00") + timedelta(days=1))]
    blocks = []
    for blk in hidden.get("weekly_busy") or []:
        if int(blk["iso_weekday"]) == iso_weekday:
            blocks.append((_on_date(day, blk["start"]), _on_date(day, blk["end"])))
    return blocks


def decide_reply(
    persona: dict[str, Any],
    offer: dict[str, Any],
    scenario: dict[str, Any],
    attempt: int = 0,
) -> dict[str, Any]:
    """Return ``{intent, window, delay_s, reason_category, source}`` for one offer.

    ``offer`` has ISO ``start``/``end``. Scenario ``personas`` overrides win (§4.5: scenario
    ``will`` wins). Otherwise hidden availability, then the persona's seeded tendencies.
    """
    sid = str(persona["staff_id"])
    start = datetime.fromisoformat(offer["start"])
    end = datetime.fromisoformat(offer["end"])
    rng = _rng(persona["seed"], scenario.get("seed", 0), sid, offer["start"], offer["end"], attempt)
    delay = _delay_s(persona, rng)
    override = (scenario.get("personas") or {}).get(sid)
    if override:
        will = override["will"]
        window = None
        if will == "counter":
            w0, w1 = override["window"]
            window = [_on_date(start, w0).isoformat(), _on_date(start, w1).isoformat()]
        reason = {"decline": "health", "counter": "school"}.get(will, "none")
        return {"intent": will, "window": window, "delay_s": delay, "reason_category": reason,
                "source": "scenario_override"}

    for b0, b1 in busy_blocks(persona, start):
        if b0 < end and b1 > start:
            # Busy for the start only: offer the rest of the shift instead ("can lah after 9").
            if b0 <= start and b1 < end and (end - b1) >= timedelta(hours=2):
                return {"intent": "counter", "window": [b1.isoformat(), end.isoformat()],
                        "delay_s": delay, "reason_category": "school", "source": "hidden_availability"}
            return {"intent": "decline", "window": None, "delay_s": delay,
                    "reason_category": "school", "source": "hidden_availability"}

    t = persona["tendencies"]
    roll = rng.random()
    cumulative = 0.0
    intent = "accept"
    for name in INTENTS:
        cumulative += float(t[name])
        if roll < cumulative:
            intent = name
            break
    window = None
    if intent == "counter":
        later = start + timedelta(hours=2)
        if end - later >= timedelta(hours=2):
            window = [later.isoformat(), end.isoformat()]
        else:
            intent = "decline"
    reason = {"decline": rng.choice(["family", "transport", "health", "other"]),
              "counter": "other"}.get(intent, "none")
    return {"intent": intent, "window": window, "delay_s": delay, "reason_category": reason,
            "source": "tendency"}


def _delay_s(persona: dict[str, Any], rng: random.Random) -> int:
    d = persona["reply_delay_s"]
    # Log-normal with the persona's median and 90th percentile.
    mu = math.log(float(d["median"]))
    sigma = max(0.05, (math.log(float(d["p90"])) - mu) / 1.2816)
    return max(5, int(round(math.exp(rng.gauss(mu, sigma)))))


def make_persona(staff: dict[str, Any], rng: random.Random, seed: int) -> dict[str, Any]:
    """Seeded persona. Style is sampled independently of the name (§8.3 MUST): the name is never read."""
    accept = rng.uniform(0.45, 0.8)
    decline = rng.uniform(0.1, 0.3)
    counter = rng.uniform(0.03, 0.12)
    silent = rng.uniform(0.03, 0.1)
    total = accept + decline + counter + silent
    weekly_busy = []
    exam_weeks: list[str] = []
    if staff.get("is_student"):
        for weekday in rng.sample([1, 2, 3, 4, 5], k=rng.choice([1, 2, 3])):
            begin = rng.choice(["08:00", "09:00", "10:00", "13:00"])
            hours = rng.choice([2, 3, 4])
            h = int(begin[:2]) + hours
            weekly_busy.append({"iso_weekday": weekday, "start": begin, "end": f"{h:02d}:00"})
        exam_weeks = [rng.choice(["2026-W45", "2026-W47", "2026-W48"])]
    median = rng.choice([30, 45, 60, 90, 120, 180])
    return {
        "staff_id": staff["staff_id"],
        "hidden_availability": {"weekly_busy": weekly_busy, "exam_weeks": exam_weeks},
        "reply_delay_s": {"median": median, "p90": median * rng.choice([2, 3, 4])},
        "tendencies": {
            "accept": round(accept / total, 3),
            "decline": round(decline / total, 3),
            "counter": round(counter / total, 3),
            "silent": round(1 - (round(accept / total, 3) + round(decline / total, 3)
                                 + round(counter / total, 3)), 3),
        },
        "style": {
            "singlish_particles": round(rng.random(), 2),
            "code_mix": rng.choice(["none", "malay", "mandarin", "hokkien", "tamil"]),
            "script": rng.choice(["romanised", "romanised", "native"]),
            "genz_slang": round(rng.random(), 2),
            "typos": round(rng.random() * 0.3, 2),
            "emoji_only_rate": round(rng.random() * 0.1, 2),
            "voice_note_style": rng.random() < 0.15,
        },
        "seed": seed,
        "synthetic": True,
    }
