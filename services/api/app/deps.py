"""Seams between ``api`` and everything it calls (§4.2 KICKSTART).

Each seam has a local implementation (in-process, used by tests and
``evals/runners/local_cascade.py``) and a Cloud implementation (HTTP with Google auth, used on
Cloud Run). The Cloud implementations are written but **not exercised** in this build: no Google
Cloud resource is created or called (unattended-mode rule).
"""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Protocol

from services.agent.app.logic import parse_reply
from services.guard.app.logic import label


class Clock(Protocol):
    def now(self) -> datetime: ...


@dataclass
class SimClock:
    """Simulated time. The local driver moves it forward; nothing sleeps."""

    current: datetime

    def now(self) -> datetime:
        return self.current

    def advance_to(self, t: datetime) -> None:
        if t > self.current:
            self.current = t

    def reset_to(self, t: datetime) -> None:
        """Local dev server only: a new scenario sets the simulated "now" (may move back)."""
        self.current = t


@dataclass
class CompressedClock:  # pragma: no cover - Cloud Run demo clock
    """Demo time on Cloud Run: scenario time plus real elapsed time x ``scale``.

    The test page labels this compression visibly (docs/decisions/0012-persona-delivery.md).
    """

    scenario_start: datetime
    real_start: datetime
    scale: float

    def now(self) -> datetime:
        elapsed = datetime.now(self.real_start.tzinfo) - self.real_start
        return self.scenario_start + timedelta(seconds=elapsed.total_seconds() * self.scale)


class GuardUnavailable(RuntimeError):
    """Guard errored or timed out. Callers fail closed."""


class GuardClient(Protocol):
    def label(self, text: str) -> dict[str, Any]: ...


@dataclass
class LocalGuard:
    fail: bool = False  # fault injection for fail-closed tests

    def label(self, text: str) -> dict[str, Any]:
        if self.fail:
            raise GuardUnavailable("guard fault injected")
        return label(text)


class AgentClient(Protocol):
    def parse_reply(self, text: str, offer: dict[str, Any]) -> dict[str, Any]: ...


@dataclass
class LocalAgent:
    cfg: dict[str, Any]

    def parse_reply(self, text: str, offer: dict[str, Any]) -> dict[str, Any]:
        return parse_reply(text, offer, self.cfg)


class Messenger(Protocol):
    def send(self, staff: dict[str, Any], message: dict[str, Any]) -> None: ...


@dataclass
class RecordingMessenger:
    """Records every staff-facing message and hands offers to a hook (persona-sim locally)."""

    on_offer: Callable[[dict[str, Any]], None] | None = None
    sent: list[dict[str, Any]] = field(default_factory=list)

    def send(self, staff: dict[str, Any], message: dict[str, Any]) -> None:
        record = dict(message, staff_id=staff["staff_id"])
        self.sent.append(record)
        if message["kind"] == "offer" and self.on_offer is not None:
            self.on_offer(record)


class CallbackSender(Protocol):
    def send(self, url: str, body: dict[str, Any]) -> None: ...


@dataclass
class QueueCallbacks:
    """Local stand-in for Workflows callback endpoints: requests land in a dict of queues."""

    queues: dict[str, list[dict[str, Any]]] = field(default_factory=dict)

    def send(self, url: str, body: dict[str, Any]) -> None:
        self.queues.setdefault(url, []).append(body)


class Launcher(Protocol):
    def start(self, gap_id: str) -> str: ...


@dataclass
class RecordingLauncher:
    started: list[str] = field(default_factory=list)

    def start(self, gap_id: str) -> str:
        self.started.append(gap_id)
        return f"local-execution-{gap_id}"


class HttpGuard:  # pragma: no cover - Cloud Run only
    def __init__(self, url: str, timeout_s: float = 5.0):
        self.url, self.timeout_s = url, timeout_s

    def label(self, text: str) -> dict[str, Any]:
        import httpx

        try:
            resp = httpx.post(f"{self.url}/label", json={"text": text}, timeout=self.timeout_s,
                              headers=_id_token_header(self.url))
            resp.raise_for_status()
            return dict(resp.json())
        except Exception as exc:  # any failure fails closed
            raise GuardUnavailable(str(exc)) from exc


class HttpCallbacks:  # pragma: no cover - Cloud Run only
    """POST to a Workflows callback URL with an OAuth token (needs workflows.callbacks.send)."""

    def send(self, url: str, body: dict[str, Any]) -> None:
        import google.auth
        import google.auth.transport.requests
        import httpx

        creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
        creds.refresh(google.auth.transport.requests.Request())
        for _ in range(3):
            resp = httpx.post(url, json=body, timeout=10,
                              headers={"Authorization": f"Bearer {creds.token}"})
            if resp.status_code != 429:  # single callback slot busy: retry
                resp.raise_for_status()
                return
        resp.raise_for_status()


class HttpSolver:  # pragma: no cover - Cloud Run only
    """Calls the ``solver`` service. HTTP 409 is a solver/validator disagreement (P0)."""

    def __init__(self, url: str):
        self.url = url

    def __call__(self, gap: dict[str, Any], context: dict[str, Any], rules: Any, cfg: Any,
                 **_: Any) -> Any:
        import httpx

        from policy.compile_cpsat import PlanDisagreement, PlanResult

        body = {"gap": gap, "context": {k: v for k, v in context.items() if k != "company"}}
        resp = httpx.post(f"{self.url}/solve", json=body, timeout=60, headers=_id_token_header(self.url))
        if resp.status_code == 409:
            raise PlanDisagreement("solver service reported plan.disagreement", resp.json()["details"])
        resp.raise_for_status()
        d = resp.json()
        return PlanResult(candidates=d["candidates"], rejected_candidates=d["rejected_candidates"],
                          solver_params=d["solver_params"], validator_version=d["validator_version"],
                          compiler_version=d["compiler_version"])


class HttpMessenger:  # pragma: no cover - Cloud Run only
    """Sim-channel staff go to persona-sim; Telegram staff need the Slice 7 connector (refused)."""

    def __init__(self, persona_sim_url: str):
        self.url = persona_sim_url

    def send(self, staff: dict[str, Any], message: dict[str, Any]) -> None:
        import httpx

        if staff.get("channel", "sim") != "sim":
            raise RuntimeError("Telegram connector is Slice 7; refusing to send")
        if message["kind"] != "offer":
            return  # courtesy, withdrawal and confirmation messages need no simulated reply
        body = {k: message[k] for k in ("offer_id", "start", "end", "attempt", "scenario_id")}
        body["staff_id"] = staff["staff_id"]
        httpx.post(f"{self.url}/offers", json=body, timeout=10,
                   headers=_id_token_header(self.url)).raise_for_status()


class WorkflowsLauncher:  # pragma: no cover - Cloud Run only
    def __init__(self) -> None:
        self.project = os.environ["GOOGLE_CLOUD_PROJECT"]
        self.region = os.environ.get("REGION", "asia-southeast1")
        self.api_url = os.environ["API_URL"]

    def start(self, gap_id: str) -> str:
        import json

        from google.cloud.workflows import executions_v1

        client = executions_v1.ExecutionsClient()
        parent = client.workflow_path(self.project, self.region, "coverage-cascade")
        execution = executions_v1.Execution(
            argument=json.dumps({"gap_id": gap_id, "api_url": self.api_url}))
        return str(client.create_execution(parent=parent, execution=execution).name)


def _id_token_header(audience: str) -> dict[str, str]:  # pragma: no cover - Cloud Run only
    import google.auth.transport.requests
    import google.oauth2.id_token

    token = google.oauth2.id_token.fetch_id_token(google.auth.transport.requests.Request(), audience)
    return {"Authorization": f"Bearer {token}"}
