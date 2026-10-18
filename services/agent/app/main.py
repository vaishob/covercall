"""``agent`` service (Cloud Run). Refuses to start unless AGENT_IMPL is explicit (stub-v0 or a pinned model)."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel

from policy.compile_cpsat import load_company_config
from services.agent.app.logic import draft_offer, explain_plan, parse_reply, require_impl

IMPL = require_impl()  # raises StartupRefused naming the role
CFG = load_company_config()
app = FastAPI(title="covercall-agent", description="All data is synthetic.")


class ParseIn(BaseModel):
    text: str
    offer: dict[str, Any]


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok", "parser_impl": IMPL}


@app.post("/parse_reply")
def parse(body: ParseIn) -> dict[str, Any]:
    return parse_reply(body.text, body.offer, CFG)


@app.post("/explain_plan")
def explain(plan: dict[str, Any]) -> dict[str, Any]:
    return explain_plan(plan)


class DraftIn(BaseModel):
    outlet_name: str
    start: str
    end: str
    pay_basis: str


@app.post("/draft_offer")
def draft(body: DraftIn) -> dict[str, str]:
    return {"text": draft_offer(body.outlet_name, body.start, body.end, body.pay_basis, CFG),
            "draft_impl": IMPL}
