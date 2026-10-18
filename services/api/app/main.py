"""``api`` service (FastAPI, Cloud Run). Public routes need no sign-in; ``/internal/*`` routes accept
only the workflow service account (Google-signed OIDC ID token). All data is synthetic."""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse

from services.api.app.core import Api, ApiError
from services.api.app.events import verify_chain
from services.api.app.page import TEST_PAGE


def require_workflow_caller(authorization: str = Header(default="")) -> None:
    """Verify a Google-signed ID token for the workflow service account. Fails closed."""
    expected = os.environ.get("WORKFLOW_SA_EMAIL")
    audience = os.environ.get("API_URL")
    if not expected or not audience or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=403, detail="internal route: workflow identity required")
    try:  # pragma: no cover - needs Google-signed tokens
        import google.auth.transport.requests
        import google.oauth2.id_token

        claims = google.oauth2.id_token.verify_oauth2_token(
            authorization.removeprefix("Bearer "), google.auth.transport.requests.Request(), audience)
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=403, detail="invalid identity token") from exc
    if claims.get("email") != expected or not claims.get("email_verified"):  # pragma: no cover
        raise HTTPException(status_code=403, detail="caller is not the workflow service account")


def create_app(api: Api, internal_auth: Callable[..., None] = require_workflow_caller,
               time_scale_label: str = "") -> FastAPI:
    app = FastAPI(title="covercall-api", description="All data is synthetic.")
    app.state.api = api
    internal = [Depends(internal_auth)]

    @app.exception_handler(ApiError)
    def _api_error(_: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(status_code=exc.status, content={"error": str(exc)})

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    # ---------------------------------------------------------------- public
    @app.post("/gaps")
    def create_gap(body: dict[str, Any]) -> dict[str, Any]:
        return api.create_gap(body)

    @app.get("/gaps/{gap_id}")
    def get_gap(gap_id: str) -> dict[str, Any]:
        gap = api._gap(gap_id)
        return {k: v for k, v in gap.items() if k not in ("overrides",)}

    @app.get("/gaps/{gap_id}/events")
    def get_events(gap_id: str) -> list[dict[str, Any]]:
        return [ev for _, ev in api.store.list(f"gaps/{gap_id}/events")]

    @app.get("/gaps/{gap_id}/verify")
    def verify(gap_id: str) -> dict[str, Any]:
        return verify_chain(api.store, gap_id).to_dict()

    @app.get("/plans/{plan_id}")
    def get_plan(plan_id: str) -> dict[str, Any]:
        plan = api.store.get(f"plans/{plan_id}")
        if plan is None:
            raise HTTPException(404)
        return plan

    @app.post("/approvals")
    def approvals(body: dict[str, Any]) -> dict[str, Any]:
        return api.record_approval(body)

    @app.post("/replies")
    def replies(body: dict[str, Any]) -> dict[str, Any]:
        return api.receive_reply(body)

    @app.post("/fallbacks")
    def fallbacks(body: dict[str, Any]) -> dict[str, Any]:
        return api.choose_fallback(body["gap_id"], body["option"])

    @app.post("/gaps/{gap_id}/cancel")
    def cancel(gap_id: str) -> dict[str, Any]:
        return api.cancel(gap_id)

    @app.post("/live/token")
    def live_token() -> JSONResponse:
        # Slice 4: single-use ephemeral Live API token. Not built; never returns a key.
        return JSONResponse(status_code=501, content={"error": "voice is Slice 4; use text or Scenario buttons"})

    @app.get("/test", response_class=HTMLResponse)
    def test_page() -> str:
        return TEST_PAGE.replace("{{TIME_SCALE}}", time_scale_label or "none (real time)")

    # ---------------------------------------------------------------- internal (workflow only)
    @app.post("/internal/guard-input", dependencies=internal)
    def guard_input(body: dict[str, Any]) -> dict[str, Any]:
        return api.guard_input(body["gap_id"])

    @app.post("/internal/transition", dependencies=internal)
    def transition(body: dict[str, Any]) -> dict[str, Any]:
        return api.transition(body)

    @app.post("/internal/solve", dependencies=internal)
    def solve(body: dict[str, Any]) -> dict[str, Any]:
        return api.solve_gap(body["gap_id"])

    @app.post("/internal/approval-request", dependencies=internal)
    def approval_request(body: dict[str, Any]) -> dict[str, Any]:
        return api.approval_request(body["gap_id"], body["plan_id"], body["callback_url"])

    @app.post("/internal/next-offers", dependencies=internal)
    def next_offers(body: dict[str, Any]) -> dict[str, Any]:
        return api.next_offers(body["gap_id"])

    @app.post("/internal/offers", dependencies=internal)
    def offers(body: dict[str, Any]) -> dict[str, Any]:
        return api.register_offer(body["gap_id"], body["offer"], body["callback_url"],
                                  int(body["window_s"]), body.get("fanout_group"), body.get("key"))

    @app.post("/internal/reply", dependencies=internal)
    def reply(body: dict[str, Any]) -> dict[str, Any]:
        return api.read_reply(body["offer_id"], body["message_id"])

    @app.post("/internal/offer-outcome", dependencies=internal)
    def offer_outcome(body: dict[str, Any]) -> dict[str, Any]:
        return api.offer_outcome(body["offer_id"], body["outcome"], body.get("info"))

    @app.post("/internal/accept", dependencies=internal)
    def accept(body: dict[str, Any]) -> dict[str, Any]:
        return api.accept(body["offer_id"], body.get("info"))

    @app.post("/internal/counter", dependencies=internal)
    def counter(body: dict[str, Any]) -> dict[str, Any]:
        return api.counter(body["offer_id"], body["window"], body.get("info"))

    @app.post("/internal/counter-resolve", dependencies=internal)
    def counter_resolve(body: dict[str, Any]) -> dict[str, Any]:
        return api.resolve_counters(body["gap_id"])

    @app.post("/internal/commit", dependencies=internal)
    def commit(body: dict[str, Any]) -> dict[str, Any]:
        return api.commit(body["gap_id"])

    @app.post("/internal/escalation-request", dependencies=internal)
    def escalation_request(body: dict[str, Any]) -> dict[str, Any]:
        return api.escalation_request(body["gap_id"], body["callback_url"])

    return app


def _cloud_app() -> FastAPI:  # pragma: no cover - Cloud Run wiring, not run in this build
    from policy.compile_cpsat import load_company_config, load_rules
    from services.api.app.deps import (
        HttpCallbacks,
        HttpGuard,
        HttpMessenger,
        HttpSolver,
        LocalAgent,
        WorkflowsLauncher,
    )
    from services.common.store import FirestoreStore

    cfg = load_company_config()
    scale = float(os.environ.get("TIME_SCALE", "1"))
    api = Api(FirestoreStore("(default)"), cfg, load_rules(), clock=_RealClock(), guard=HttpGuard(os.environ["GUARD_URL"]),
              agent=LocalAgent(cfg), messenger=HttpMessenger(os.environ["PERSONA_SIM_URL"]),
              callbacks=HttpCallbacks(),
              launcher=WorkflowsLauncher(), solver=HttpSolver(os.environ["SOLVER_URL"]), time_scale=scale)
    return create_app(api, time_scale_label=f"x{scale:g}" if scale != 1 else "")


class _RealClock:  # pragma: no cover
    def now(self) -> Any:
        from datetime import datetime, timedelta, timezone

        return datetime.now(timezone(timedelta(hours=8)))


app = _cloud_app() if os.environ.get("COVERCALL_ENV") == "cloud" else None
