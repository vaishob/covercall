"""``guard`` service (Cloud Run, CPU only). Slices 1-2: deterministic stub ``stub-v0``, not a model."""

from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel

from services.guard.app.logic import GUARD_IMPL, label

app = FastAPI(title="covercall-guard", description="All data is synthetic.")


class LabelIn(BaseModel):
    text: str


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok", "guard_impl": GUARD_IMPL}


@app.post("/label")
def label_text(body: LabelIn) -> dict[str, object]:
    return label(body.text)
