"""Agent tools (§7.3). Slices 1-2 ship a deterministic stub parser ``stub-v0``. It is NOT a model.

- ``parse_reply``: guard-cleared staff text -> the §7.3 schema. Staff text is data, never
  instructions. Confidence below ``parse_confidence_min`` becomes ``unclear``.
- ``explain_plan``: one sentence from structured solver output, plus ``check_explanation``, the
  deterministic check that rejects any number or name not present in the input.
- ``draft_offer``: a staff message under ``draft_max_chars`` stating outlet, start, end, pay basis.

The model-backed implementation (ADK + Gemini Flash) is only allowed once ``config/models.yaml``
pins the ``agent`` model; ``require_impl`` refuses to start otherwise (no silent fallback).
"""

from __future__ import annotations

import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

PARSER_IMPL = "stub-v0"
SCHEMA_INTENTS = ("accept", "decline", "counter", "question", "unclear")
REASONS = ("school", "health", "family", "transport", "none", "other")


class StartupRefused(RuntimeError):
    pass


def require_impl(env: dict[str, str] | None = None,
                 models_path: str | Path = "config/models.yaml") -> str:
    """Return the implementation to use, or refuse to start (names the role)."""
    env = dict(os.environ) if env is None else env
    impl = env.get("AGENT_IMPL", "")
    if impl == PARSER_IMPL:
        return impl
    if impl == "gemini":
        roles = yaml.safe_load(Path(models_path).read_text(encoding="utf-8"))["roles"]
        if "TODO-VERIFY" in str(roles["agent"]["model_id"]):
            raise StartupRefused("role 'agent': model_id is TODO-VERIFY in config/models.yaml")
        raise StartupRefused("role 'agent': Gemini implementation is not built yet (Slice 2 uses stub-v0)")
    raise StartupRefused("role 'agent': set AGENT_IMPL=stub-v0 (deterministic stub) or AGENT_IMPL=gemini")


_ACCEPT = [r"\bok\b", r"\bokay\b", r"\byes\b", r"\bcan\b(?!'t|not| not)", r"\bsure\b", r"\bomw\b", r"\bon my way\b",
           r"\bconfirm", r"\bi'?ll (come|do|take)", r"👍", r"\bjia ?you\b", r"\bboleh\b"]
_DECLINE = [r"\bcannot\b", r"\bcan'?t\b", r"\bcan not\b", r"\bsorry\b", r"\bno\b", r"\bunable\b",
            r"\bnot (free|available)\b", r"\bmc\b", r"\bsick\b", r"\bbusy\b", r"\btak boleh\b"]
_COUNTER = [r"\bonly after\b", r"\bafter (\d)", r"\bnot \d", r"\b\d{1,2}(:\d{2})?\s*(am|pm)?\s*can\b",
            r"\bfrom \d", r"\b\d{1,2}[:.]\d{2}\s*[-–to]+\s*\d{1,2}[:.]\d{2}\b", r"\bcan do \d"]
_REASON = {"school": r"\b(lecture|class|exam|school|tutorial|lab)\b",
           "health": r"\b(mc|sick|fever|doctor|clinic|unwell)\b",
           "family": r"\b(family|mum|mom|dad|kid|child|grandma)\b",
           "transport": r"\b(mrt|bus|train|traffic|breakdown|late)\b"}


def _hhmm(token: str, pm_hint: bool) -> str | None:
    m = re.match(r"(\d{1,2})(?:[:.](\d{2}))?\s*(am|pm)?", token)
    if not m:
        return None
    h, mins, ampm = int(m.group(1)), int(m.group(2) or 0), m.group(3)
    if ampm == "pm" and h < 12:
        h += 12
    elif ampm is None and pm_hint and h < 7:
        h += 12
    if not (0 <= h <= 23 and 0 <= mins <= 59):
        return None
    return f"{h:02d}:{mins:02d}"


def parse_reply(text: str, offer: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    """Deterministic stub for the §7.3 schema. ``offer`` = {start, end} ISO of the offered segment."""
    t = text.lower().strip()
    start_hm = datetime.fromisoformat(offer["start"]).strftime("%H:%M")
    end_hm = datetime.fromisoformat(offer["end"]).strftime("%H:%M")
    reason = next((k for k, p in _REASON.items() if re.search(p, t)), "none")
    window = None
    rng = re.search(r"(\d{1,2}(?:[:.]\d{2})?\s*(?:am|pm)?)\s*(?:-|–|to)\s*(\d{1,2}(?:[:.]\d{2})?\s*(?:am|pm)?)", t)
    after = re.search(r"(?:only after|after|from|can do)\s*(\d{1,2}(?:[:.]\d{2})?\s*(?:am|pm)?)", t)
    if rng:
        a, b = _hhmm(rng.group(1), False), _hhmm(rng.group(2), True)
        if a and b:
            window = {"start": a, "end": b}
    elif after:
        a = _hhmm(after.group(1), False)
        if a:
            window = {"start": a, "end": end_hm}
    else:  # "wah 7am ah... 8 can?" (§8.3): the last time followed by "can" is the offered start
        times = re.findall(r"(\d{1,2}(?:[:.]\d{2})?\s*(?:am|pm)?)\s*can\b", t)
        a = _hhmm(times[-1], False) if times else None
        if a:
            window = {"start": a, "end": end_hm}
    counter = window is not None and window != {"start": start_hm, "end": end_hm} and any(
        re.search(p, t) for p in _COUNTER)
    accept = any(re.search(p, t) for p in _ACCEPT)
    decline = any(re.search(p, t) for p in _DECLINE)
    if counter:
        intent, confidence = "counter", 0.8
    elif accept and not decline:
        intent, confidence = "accept", 0.85
    elif decline and not accept:
        intent, confidence = "decline", 0.85
    elif t.endswith("?"):
        intent, confidence = "question", 0.75
    else:
        intent, confidence = "unclear", 0.4
    if confidence < float(cfg["parse_confidence_min"]):
        intent = "unclear"
    return {
        "intent": intent,
        "counter_window": window if intent == "counter" else None,
        "reason_category": reason,
        "confidence": confidence,
        "language_tags": ["singlish"] if re.search(r"\b(lah|leh|lor|ah|meh|sia)\b", t) else ["english"],
        "parser_impl": PARSER_IMPL,
    }


_NUM = re.compile(r"\d+(?:[.:]\d+)?")


def check_explanation(text: str, source: dict[str, Any]) -> list[str]:
    """Return the numbers and capitalised names in ``text`` that are absent from ``source``."""
    flat = " ".join(str(v) for v in _walk(source))
    problems = [n for n in _NUM.findall(text) if n not in flat]
    for word in re.findall(r"\b[A-Z][a-z]+\b", text):
        if word not in flat and word not in _ALLOWED_WORDS:
            problems.append(word)
    return problems


_ALLOWED_WORDS = {"The", "This", "Plan", "Cover", "Covers", "Rank", "No", "SGD", "From", "At", "With",
                  "Overtime", "Total", "Cost", "Arrives", "Travel", "It", "A", "And", "To"}


def _walk(value: Any) -> list[Any]:
    if isinstance(value, dict):
        out: list[Any] = []
        for k, v in value.items():
            out += [k] + _walk(v)
        return out
    if isinstance(value, list):
        out = []
        for v in value:
            out += _walk(v)
        return out
    return [value]


def explain_plan(plan: dict[str, Any]) -> dict[str, Any]:
    segs = plan["segments"]
    parts = [f"{s['display_name']} {s['start'][11:16]}-{s['end'][11:16]}" for s in segs]
    cost = plan["cost_breakdown"]["total_cents"] / 100
    text = f"Plan {plan['rank']}: {' and '.join(parts)}. Total cost {cost:.2f} SGD."
    source = dict(plan, total_sgd=f"{cost:.2f}")
    problems = check_explanation(text, source)
    return {"text": text if not problems else "", "rejected_tokens": problems,
            "explain_impl": PARSER_IMPL}


def draft_offer(outlet_name: str, start: str, end: str, pay_basis: str, cfg: dict[str, Any]) -> str:
    s, e = datetime.fromisoformat(start), datetime.fromisoformat(end)
    msg = (f"Hi! Can you cover {outlet_name} on {s.strftime('%a %d %b')}, "
           f"{s.strftime('%H:%M')}-{e.strftime('%H:%M')}? Pay: {pay_basis}. "
           f"Reply yes or no. (All data is synthetic.)")
    return msg[: int(cfg["draft_max_chars"])]
