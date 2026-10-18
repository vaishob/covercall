"""``connectors`` service (Cloud Run): Telegram webhook and Routes API client. Slice 7, not built.

Until then it only answers health checks and refuses every connector call, so nothing can reach a
real phone or a paid API by accident.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI(title="covercall-connectors", description="All data is synthetic.")


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok", "connectors": "not built (Slice 7)"}


@app.post("/telegram/webhook")
def telegram_webhook() -> JSONResponse:
    return JSONResponse(status_code=501, content={"error": "Telegram connector is Slice 7"})


@app.post("/routes")
def routes() -> JSONResponse:
    return JSONResponse(status_code=501, content={"error": "Routes API connector is Slice 7"})
