"""The local dev server runs the workflow in the background and waits for the lead's taps."""

from __future__ import annotations

import time

from fastapi.testclient import TestClient

from evals.runners.dev_server import build


def _wait(client: TestClient, gap_id: str, states: set[str], timeout_s: float = 60,
          pending: bool = False, fallbacks: bool = False) -> dict:
    end = time.monotonic() + timeout_s
    while time.monotonic() < end:
        view = client.get(f"/gaps/{gap_id}").json()
        gap = view["gap"]
        # ESCALATED is appended before escalation-request stores the fallbacks: wait for both.
        if (gap["state"] in states and (not pending or gap["approval_pending"])
                and (not fallbacks or gap["fallbacks"])):
            return view
        time.sleep(0.05)
    raise AssertionError(f"{gap_id} never reached {states}")


def test_dev_server_runs_s017_with_external_lead() -> None:
    run = build(pace_s=0.0, lead_timeout_s=30, origins=["http://localhost:3000"])
    client = TestClient(run.app)
    gap_id = client.post("/gaps", json={"scenario_id": "S-017"}).json()["gap_id"]
    view = _wait(client, gap_id, {"SOLVED"}, pending=True)
    assert view["gap"]["approval_pending"] is True
    pending = client.get(f"/gaps/{gap_id}/approval").json()
    assert client.post("/approvals", json={"gap_id": gap_id, "nonce": pending["nonce"],
                                           "decision": "approve", "channel": "tap"}).status_code == 200
    view = _wait(client, gap_id, {"FILLED"})
    assert view["gap"]["outcome"] == "filled"
    assert client.get(f"/gaps/{gap_id}/events").json()["chain"]["ok"] is True
    assert not run.api.launcher.errors  # type: ignore[attr-defined]


def test_dev_server_nobody_replies_waits_for_fallback() -> None:
    run = build(pace_s=0.0, lead_timeout_s=30, origins=["http://localhost:3000"])
    client = TestClient(run.app)
    gap_id = client.post("/gaps", json={"scenario_id": "S-002"}).json()["gap_id"]
    _wait(client, gap_id, {"SOLVED"}, pending=True)
    pending = client.get(f"/gaps/{gap_id}/approval").json()
    client.post("/approvals", json={"gap_id": gap_id, "nonce": pending["nonce"], "decision": "approve",
                                    "channel": "tap"})
    view = _wait(client, gap_id, {"ESCALATED"}, fallbacks=True)
    option = view["gap"]["fallbacks"][0]
    assert client.post("/fallbacks", json={"gap_id": gap_id, "option": option}).status_code == 200
    view = _wait(client, gap_id, {"RESOLVED"})
    assert view["gap"]["outcome"] == option
