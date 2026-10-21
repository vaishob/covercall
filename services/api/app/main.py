"""``api`` service (FastAPI, Cloud Run). Public routes need no sign-in; ``/internal/*`` routes accept
only the workflow service account (Google-signed OIDC ID token). All data is synthetic."""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from datetime import timedelta
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse

from services.api.app import live, views
from services.api.app.core import Api, ApiError
from services.api.app.page import TEST_PAGE
from services.common.models import pinned_role

DEFAULT_ALLOWED_ORIGINS = ("http://localhost:3000",)
log = logging.getLogger("covercall.api")  # uvicorn leaves app loggers at WARNING; stderr reaches Cloud Logging
log.setLevel(logging.INFO)
if not log.handlers:
    log.addHandler(logging.StreamHandler())


def allowed_origins_from_env() -> list[str]:
    """Comma-separated ``ALLOWED_ORIGINS``. A wildcard is refused (decision 0015)."""
    raw = os.environ.get("ALLOWED_ORIGINS", "")
    origins = [o.strip() for o in raw.split(",") if o.strip()] or list(DEFAULT_ALLOWED_ORIGINS)
    if any("*" in o for o in origins):
        raise ValueError("ALLOWED_ORIGINS must list exact origins; '*' is not allowed")
    return origins


def demo_clock_offset_from_env() -> timedelta:
    """Whole days in ``DEMO_CLOCK_OFFSET_DAYS`` (decision 0025); unset means the real clock.
    Whole days keep every time of day unchanged. A bad value stops the service from starting."""
    raw = os.environ.get("DEMO_CLOCK_OFFSET_DAYS", "").strip()
    days = int(raw) if raw else 0
    if not 0 <= days <= 30:
        raise ValueError(f"DEMO_CLOCK_OFFSET_DAYS must be 0..30 whole days, got {raw!r}")
    return timedelta(days=days)


def client_ip(request: Request) -> str:
    """The caller's IP for rate limiting: the right-most ``X-Forwarded-For`` entry, which Cloud Run's
    front end appends. Entries to its left are whatever the client sent, so they are not trusted."""
    forwarded = [p.strip() for p in request.headers.get("x-forwarded-for", "").split(",") if p.strip()]
    return forwarded[-1] if forwarded else (request.client.host if request.client else "unknown")


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
               time_scale_label: str = "", allowed_origins: list[str] | None = None,
               environment: str = "local", live_client: Callable[[], Any] | None = None,
               live_limiter: Any = None) -> FastAPI:
    app = FastAPI(title="covercall-api", description="All data is synthetic.")
    app.state.api = api
    origins = allowed_origins if allowed_origins is not None else allowed_origins_from_env()
    if any("*" in o for o in origins):
        raise ValueError("allowed_origins must list exact origins; '*' is not allowed")
    app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["GET", "POST"],
                       allow_headers=["Content-Type"], allow_credentials=False)
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

    # Read routes: client-safe projections only (services/api/app/views.py).
    @app.get("/status")
    def status() -> dict[str, Any]:
        return views.status_view(api, environment, "live" if live_client else "off")

    @app.get("/scenarios")
    def scenarios() -> list[dict[str, Any]]:
        return views.scenarios_view(api)

    @app.get("/gaps/{gap_id}")
    def get_gap(gap_id: str) -> dict[str, Any]:
        return views.gap_view(api, gap_id)

    @app.get("/gaps/{gap_id}/events")
    def get_events(gap_id: str) -> dict[str, Any]:
        return views.events_view(api, gap_id)

    @app.get("/gaps/{gap_id}/quarantine")
    def get_quarantine(gap_id: str) -> list[dict[str, Any]]:
        return views.quarantine_view(api, gap_id)

    @app.get("/gaps/{gap_id}/approval")
    def get_approval(gap_id: str) -> dict[str, Any]:
        return api.pending_approval(gap_id)

    @app.get("/evals")
    def evals() -> dict[str, Any]:
        return views.evals_view()

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

    limiter = live_limiter or live.RateLimiter()

    @app.post("/live/token")
    def live_token(request: Request) -> JSONResponse:
        # Single-use ephemeral Live API token (decision 0019). The key never leaves this process.
        if live_client is None:
            return JSONResponse(status_code=501, content={
                "error": "not_implemented",
                "message": "Voice is not enabled on this deployment. Use the Scenario buttons or text."})
        ip = client_ip(request)
        try:
            limiter.check(ip)
        except live.RateLimited as exc:
            log.info("live_token limiter_key=%s outcome=429 (%s)", ip, exc)
            return JSONResponse(status_code=429, content={"error": "rate_limited", "message": str(exc)})
        log.info("live_token limiter_key=%s outcome=allowed", ip)
        try:
            spec = pinned_role("voice")
            return JSONResponse(content=live.mint(live_client(), spec))
        except Exception as exc:  # never echo SDK errors (they could carry request details)
            return JSONResponse(status_code=502, content={
                "error": "token_unavailable", "message": f"Could not mint a voice token ({type(exc).__name__})."})

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
    agent: Any = LocalAgent(cfg)
    if os.environ.get("PARSER_IMPL") == "gemini":  # refuses to start if the agent model is TODO-VERIFY
        from services.agent.app.gemini import from_registry

        agent = from_registry(cfg)
    api = Api(FirestoreStore("(default)"), cfg, load_rules(), clock=_RealClock(), guard=HttpGuard(os.environ["GUARD_URL"]),
              agent=agent, messenger=HttpMessenger(os.environ["PERSONA_SIM_URL"]),
              callbacks=HttpCallbacks(),
              launcher=WorkflowsLauncher(), solver=HttpSolver(os.environ["SOLVER_URL"]), time_scale=scale,
              demo_isolation=os.environ.get("DEMO_ISOLATION") == "1",
              clock_offset=demo_clock_offset_from_env())
    live_client = None
    if os.environ.get("VOICE_ENABLED") == "1" and os.environ.get("GEMINI_API_KEY"):
        voice = pinned_role("voice")  # refuses to start if the voice model is TODO-VERIFY

        def live_client() -> Any:
            return live.developer_client(os.environ["GEMINI_API_KEY"], voice["api_version"])
    return create_app(api, time_scale_label=f"x{scale:g}" if scale != 1 else "", environment="cloud",
                      live_client=live_client)


class _RealClock:  # pragma: no cover
    def now(self) -> Any:
        from datetime import datetime, timedelta, timezone

        return datetime.now(timezone(timedelta(hours=8)))


app = _cloud_app() if os.environ.get("COVERCALL_ENV") == "cloud" else None
