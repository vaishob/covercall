"""``solver`` service (Cloud Run): FastAPI wrapper around ``policy.compile_cpsat.solve``.

A solver/validator disagreement returns HTTP 409 with the details (P0; the workflow holds the gap).
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from policy.compile_cpsat import (
    PlanDisagreement,
    SolverDataError,
    load_company_config,
    load_rules,
    solve,
)

RULES = load_rules()
CFG = load_company_config()
app = FastAPI(title="covercall-solver", description="All data is synthetic.")


@app.get("/healthz")
def healthz() -> dict[str, Any]:
    return {"status": "ok", "rules": len(RULES)}


@app.post("/solve")
def solve_route(body: dict[str, Any]) -> Any:
    try:
        result = solve(body["gap"], body["context"], RULES, CFG)
    except PlanDisagreement as exc:
        return JSONResponse(status_code=409, content={"error": "plan.disagreement", "details": exc.details})
    except SolverDataError as exc:
        return JSONResponse(status_code=422, content={"error": str(exc)})
    return result.to_dict()
