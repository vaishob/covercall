"""The local dev server runs the workflow in the background and waits for the lead's taps."""

from __future__ import annotations

import time
from datetime import datetime
from typing import Any

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


def test_s017_twice_in_a_row_gives_identical_plans() -> None:
    """Decision 0023: a scenario gap's commit lives in its own overlay, never in the shared roster."""
    run = build(pace_s=0.0, lead_timeout_s=30, origins=["http://localhost:3000"])
    client = TestClient(run.app)
    roster_before = run.store.list("shifts")
    views = []
    for _ in range(2):
        gap_id = client.post("/gaps", json={"scenario_id": "S-017"}).json()["gap_id"]
        _wait(client, gap_id, {"SOLVED"}, pending=True)
        pending = client.get(f"/gaps/{gap_id}/approval").json()
        client.post("/approvals", json={"gap_id": gap_id, "nonce": pending["nonce"], "decision": "approve",
                                        "channel": "tap"})
        views.append(_wait(client, gap_id, {"FILLED"}))
        overlay = run.store.get(f"overlays/{gap_id}")
        assert overlay is not None and overlay["cover_shifts"]
    first, second = views
    strip = ("plan_id",)
    assert [{k: v for k, v in o.items() if k not in strip} for o in first["plan"]["options"]] == \
           [{k: v for k, v in o.items() if k not in strip} for o in second["plan"]["options"]]
    assert first["gap"]["summary"] == second["gap"]["summary"]
    assert first["gap"]["cost_saved_cents"] == second["gap"]["cost_saved_cents"]
    assert run.store.list("shifts") == roster_before  # the seeded roster is untouched


def _lead_report_to_terminal(run: Any, client: TestClient) -> dict:
    # A lead report does not move the simulated clock (only scenarios do): set it to the report time.
    run.clock.reset_to(datetime.fromisoformat("2026-11-03T06:02:00+08:00"))
    body = {"outlet": "bugis", "station": "barista", "shift_start": "2026-11-03T07:00:00+08:00",
            "staff_name": "Ali", "text": "Ali is sick for the 7am barista shift at Bugis on Tuesday, 3 November"}
    created = client.post("/gaps", json=body).json()
    assert created["status"] == "created", created
    gap_id = created["gap_id"]
    solved = _wait(client, gap_id, {"SOLVED"}, pending=True)
    pending = client.get(f"/gaps/{gap_id}/approval").json()
    client.post("/approvals", json={"gap_id": gap_id, "nonce": pending["nonce"], "decision": "approve",
                                    "channel": "voice", "transcript": "yes, approve"})
    final = _wait(client, gap_id, {"FILLED"})
    return {"solved": solved, "final": final}


def test_demo_isolation_same_lead_report_twice_gives_identical_plans() -> None:
    """DEMO_ISOLATION=1: lead-reported gaps commit to their own overlay, so every judge who reports
    the same absence sees the same plan, and the seeded roster never changes."""
    run = build(pace_s=0.0, lead_timeout_s=30, origins=["http://localhost:3000"])
    run.api.demo_isolation = True
    client = TestClient(run.app)
    roster_before = run.store.list("shifts")
    first, second = _lead_report_to_terminal(run, client), _lead_report_to_terminal(run, client)

    def options(view: dict) -> list:
        return [{k: v for k, v in o.items() if k != "plan_id"} for o in view["plan"]["options"]]

    assert options(first["solved"]) == options(second["solved"])
    assert first["final"]["gap"]["summary"] == second["final"]["gap"]["summary"]
    assert run.store.list("shifts") == roster_before
