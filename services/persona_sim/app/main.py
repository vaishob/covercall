"""``persona-sim`` service (Cloud Run). Reads only the ``sim`` Firestore database.

``POST /offers`` decides a reply (seeded intent; scenario ``will`` wins) and writes it to the
``sim`` outbox; ``POST /deliver`` delivers every due reply to the api's ``POST /replies``. Delivery
runs every 5 s in a background loop on the warm instance (min instances 1), and the api's message dedup makes repeats
harmless (docs/decisions/0012-persona-delivery.md). Surface text: ``stub-v0`` templates, not a model.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import FastAPI

from services.persona_sim.app import logic

_SIM: Any = None


@asynccontextmanager
async def _lifespan(_: FastAPI) -> AsyncIterator[None]:  # pragma: no cover - Cloud Run path
    task = None
    if os.environ.get("COVERCALL_ENV") == "cloud":
        async def loop() -> None:
            while True:
                try:
                    await asyncio.to_thread(deliver)
                except Exception:  # keep looping; due items stay in the outbox
                    pass
                await asyncio.sleep(5)

        task = asyncio.create_task(loop())
    yield
    if task:
        task.cancel()


app = FastAPI(title="covercall-persona-sim", description="All data is synthetic.", lifespan=_lifespan)


def sim() -> Any:  # pragma: no cover - needs the Firestore sim database
    global _SIM
    if _SIM is None:
        from services.common.store import SIM_DATABASE, FirestoreStore

        _SIM = FirestoreStore(SIM_DATABASE)
    return _SIM


_WRITER: Any = None


def writer() -> Any:  # pragma: no cover - Cloud Run path; PERSONA_TEXT_IMPL=gemini turns it on
    """(write, model_id, prompt_sha) for Gemini surface text at temperature 0.8, or None (templates)."""
    global _WRITER
    if _WRITER is None and os.environ.get("PERSONA_TEXT_IMPL") == "gemini":
        from pathlib import Path

        from services.common.gemini import generate_json, prompt_sha256
        from services.common.models import enterprise_client, pinned_role

        spec = pinned_role("persona_sim")
        client = enterprise_client("persona_sim", timeout_ms=8000)
        system = Path("prompts/persona_text.md").read_text(encoding="utf-8")
        schema = {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}

        def write(user: str, seed: int) -> dict[str, Any]:
            return generate_json(client, spec["model_id"], system, user, schema, float(spec["temperature"]), seed)

        _WRITER = (write, spec["model_id"], prompt_sha256("prompts/persona_text.md"))
    return _WRITER


def _now() -> datetime:
    return datetime.now(timezone(timedelta(hours=8)))


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok", "text_impl": logic.TEXT_IMPL}


@app.post("/offers")
def offers(body: dict[str, Any]) -> dict[str, Any]:  # pragma: no cover - Cloud Run path
    scenario = sim().get(f"scenarios/{body.get('scenario_id')}") or {}
    item = logic.schedule(sim(), body, scenario, _now(), float(os.environ.get("TIME_SCALE", "1")), writer())
    return {"scheduled": item is not None}


@app.post("/deliver")
def deliver() -> dict[str, int]:  # pragma: no cover - Cloud Run path
    import httpx

    sent = 0
    for item in logic.due(sim(), _now()):
        httpx.post(f"{os.environ['API_URL']}/replies", timeout=10, json={
            "message_id": item["message_id"], "offer_id": item["offer_id"], "text": item["text"],
            "channel": "sim", "text_impl": item.get("text_impl"),
            "text_prompt_sha256": item.get("text_prompt_sha256")}).raise_for_status()
        logic.mark_delivered(sim(), item["message_id"])
        sent += 1
    return {"delivered": sent}
