"""Deadlines, reply windows, fan-out and escalation time (§5.2). Pure functions.

    mustFillBy(c)   = shiftStart - travel(c) - buffer
    slack(t)        = max_c mustFillBy(c) - t
    replyWindow(t)  = min(w_max, max(w_min, slack(t) / k))
    viable(c, t)    iff t + window(t) <= mustFillBy(c)
    fan out to the top fanout_n viable candidates when slack(t) < fanout_threshold
    t_esc           = max_c mustFillBy(c) - escalation_lead, or now if no viable candidate remains

Two additions (docs/decisions/0009-timing.md):
- ``t_esc`` is computed when the lead approves the plan and then locked (§5.1: "escalation strategy
  locked"), because recomputing it after a decline can move it into the past.
- The window actually used is clamped so an offer never outlives the locked ``t_esc``:
  ``window(t) = min(replyWindow(t), t_esc - t)``. Escalation therefore never fires after ``t_esc``
  (``escalation_late`` is P0). All times are timezone-aware (ISO 8601, +08:00).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any


def must_fill_by(segment_start: datetime, travel_min: int, buffer_min: int) -> datetime:
    return segment_start - timedelta(minutes=travel_min) - timedelta(minutes=buffer_min)


def slack_min(t: datetime, deadlines: list[datetime]) -> float:
    if not deadlines:
        return float("-inf")
    return (max(deadlines) - t).total_seconds() / 60


def reply_window_min(t: datetime, deadlines: list[datetime], cfg: dict[str, Any]) -> float:
    s = slack_min(t, deadlines)
    return min(float(cfg["w_max_min"]), max(float(cfg["w_min_min"]), s / float(cfg["k"])))


def t_esc(deadlines: list[datetime], cfg: dict[str, Any], now: datetime) -> datetime:
    if not deadlines:
        return now
    return max(deadlines) - timedelta(minutes=int(cfg["escalation_lead_min"]))


@dataclass
class Candidate:
    staff_id: str
    segment_start: datetime
    travel_min: int
    key: str = ""  # caller's reference (plan rank, segment)


@dataclass
class OfferPlan:
    mode: str  # single | fanout | escalate
    window_min: float
    t_esc: datetime
    offers: list[Candidate] = field(default_factory=list)
    slack_min: float = 0.0
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "window_min": self.window_min,
            "window_s": int(round(self.window_min * 60)),
            "t_esc": self.t_esc.isoformat(),
            "slack_min": self.slack_min,
            "reason": self.reason,
            "offers": [{"staff_id": c.staff_id, "key": c.key,
                        "segment_start": c.segment_start.isoformat(), "travel_min": c.travel_min}
                       for c in self.offers],
        }


def locked_t_esc(t: datetime, remaining: list[Candidate], cfg: dict[str, Any]) -> datetime:
    """The escalation time to lock at approval. If it is already past, escalation is due at once (t)."""
    buffer = int(cfg["buffer_min"])
    return max(t, t_esc([must_fill_by(c.segment_start, c.travel_min, buffer) for c in remaining], cfg, t))


def plan_offers(t: datetime, ranked: list[Candidate], remaining: list[Candidate],
                cfg: dict[str, Any], locked: datetime | None = None) -> OfferPlan:
    """Decide the next step at time ``t``.

    ``ranked``: candidates in the order the solver ranks them (offer order).
    ``remaining``: every legal candidate still in play (drives slack).
    ``locked``: the ``t_esc`` locked at approval; computed from ``remaining`` if not given.
    """
    buffer = int(cfg["buffer_min"])
    deadlines = [must_fill_by(c.segment_start, c.travel_min, buffer) for c in remaining]
    esc = locked if locked is not None else t_esc(deadlines, cfg, t)
    slack = slack_min(t, deadlines)
    if not deadlines:
        return OfferPlan("escalate", 0.0, esc, [], slack, "no legal candidate remains")
    if t >= esc:
        return OfferPlan("escalate", 0.0, esc, [], slack, "t_esc reached")
    window = min(reply_window_min(t, deadlines, cfg), (esc - t).total_seconds() / 60)
    viable = [c for c in ranked
              if t + timedelta(minutes=window) <= must_fill_by(c.segment_start, c.travel_min, buffer)]
    if not viable:
        return OfferPlan("escalate", 0.0, esc, [], slack, "no viable candidate remains")
    if slack < float(cfg["fanout_threshold_min"]):
        return OfferPlan("fanout", window, esc, viable[: int(cfg["fanout_n"])], slack,
                         "slack below fan-out threshold")
    return OfferPlan("single", window, esc, viable[:1], slack, "sequential offer")
