"""persona-sim logic (§4.5 KICKSTART, §8.3). Reads only the ``sim`` store.

The reply intent comes from ``datagen.personas.decide_reply`` (scenario ``will`` wins). Surface text
is a fixed template chosen from that intent: ``text_impl: stub-v0``, deterministic, NOT a model.
The ``persona_sim`` model is pinned (config/models.yaml), but Gemini Flash writes the text only once
that is explicitly enabled, through ``services.common.models.enterprise_client``.

Delivery (docs/decisions/0012-persona-delivery.md): a scheduled reply is written to
``outbox/{message_id}`` in the ``sim`` store with ``deliver_at``; ``due`` returns what should be
delivered by a given simulated time, and delivery is idempotent through the api's message dedup.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta
from typing import Any

from datagen.personas import decide_reply
from services.common.store import Store

TEXT_IMPL = "stub-v0"

_TEMPLATES = {
    "accept": ["ok can, I'll take it", "ok omw", "yes I can cover", "sure, confirm can"],
    "decline": ["sorry cannot, MC today", "sorry, not free today", "cannot leh, sorry",
                "sorry can't make it"],
    "counter": ["can lah but only after {start}, got lecture", "can do {start} to {end}",
                "wah 7am ah... only after {start} can"],
}


def surface_text(intent: str, window: list[str] | None, rng: random.Random) -> str | None:
    if intent == "silent":
        return None
    template = rng.choice(_TEMPLATES[intent])
    if intent == "counter" and window:
        a = datetime.fromisoformat(window[0]).strftime("%H:%M")
        b = datetime.fromisoformat(window[1]).strftime("%H:%M")
        return template.format(start=a, end=b)
    return template


def schedule(sim: Store, offer: dict[str, Any], scenario: dict[str, Any], sent_at: datetime,
             time_scale: float = 1.0) -> dict[str, Any] | None:
    """Decide the reply to one offer and put it in the outbox. Returns the outbox item, or None (silence)."""
    persona = sim.get(f"personas/{offer['staff_id']}")
    if persona is None:
        raise KeyError(f"no persona for {offer['staff_id']}")
    reply = decide_reply(persona, offer, scenario, attempt=int(offer.get("attempt", 0)))
    rng = random.Random(f"{persona['seed']}:{offer['offer_id']}:text")
    text = surface_text(reply["intent"], reply["window"], rng)
    if text is None:
        return None
    item = {
        "message_id": f"{offer['offer_id']}:r1",
        "offer_id": offer["offer_id"],
        "staff_id": offer["staff_id"],
        "text": text,
        "intent_label": reply["intent"],  # ground truth for evals; never sent to the api
        "deliver_at": (sent_at + timedelta(seconds=reply["delay_s"] / time_scale)).isoformat(),
        "delay_s": reply["delay_s"],
        "delivered": False,
        "text_impl": TEXT_IMPL,
        "synthetic": True,
    }
    sim.set(f"outbox/{item['message_id']}", item)
    return item


def due(sim: Store, now: datetime) -> list[dict[str, Any]]:
    return sorted(
        (d for _, d in sim.list("outbox")
         if not d["delivered"] and datetime.fromisoformat(d["deliver_at"]) <= now),
        key=lambda d: (d["deliver_at"], d["message_id"]),
    )


def next_due_time(sim: Store) -> datetime | None:
    pending = [datetime.fromisoformat(d["deliver_at"]) for _, d in sim.list("outbox")
               if not d["delivered"]]
    return min(pending) if pending else None


def mark_delivered(sim: Store, message_id: str) -> None:
    doc = sim.get(f"outbox/{message_id}")
    if doc is not None:
        doc["delivered"] = True
        sim.set(f"outbox/{message_id}", doc)
