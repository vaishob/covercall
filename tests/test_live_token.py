"""POST /live/token with a mocked SDK: shape, locked constraints, rate limits, no key leak (Slice 4)."""

from __future__ import annotations

import logging
from typing import Any

import pytest
from fastapi.testclient import TestClient

from datagen.loader import load_data
from evals.runners.local_cascade import LocalRun, load_scenario
from policy.compile_cpsat import load_company_config, load_rules
from services.api.app import live
from services.api.app.main import create_app

SECRET = "FAKE-test-key-never-returned-0000000"


class FakeTokens:
    def __init__(self) -> None:
        self.configs: list[Any] = []

    def create(self, config: Any) -> Any:
        self.configs.append(config)
        return type("Tok", (), {"name": "auth_tokens/abc123"})()


class FakeClient:
    def __init__(self) -> None:
        self.api_key = SECRET  # what a real client holds; must never reach a response
        self.auth_tokens = FakeTokens()


@pytest.fixture(scope="module")
def api() -> Any:
    run = LocalRun(load_scenario("S-017"), load_data(), load_company_config(), load_rules())
    return run.api


def app_with(api: Any, client: FakeClient, limiter: Any = None) -> TestClient:
    return TestClient(create_app(api, internal_auth=lambda: None, allowed_origins=["http://localhost:3000"],
                                 live_client=lambda: client, live_limiter=limiter))


def test_token_shape_and_locked_constraints(api: Any, caplog: pytest.LogCaptureFixture) -> None:
    fake = FakeClient()
    with caplog.at_level(logging.DEBUG):
        resp = app_with(api, fake).post("/live/token", json={})
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {"token", "expires_at", "new_session_expires_at", "model_id", "api_version"}
    assert body["token"] == "auth_tokens/abc123" and body["model_id"] == "gemini-3.8-live"
    assert body["api_version"] == "v1beta"
    assert SECRET not in resp.text and SECRET not in caplog.text
    cfg = fake.auth_tokens.configs[0]
    assert cfg.uses == 1 and cfg.lock_additional_fields is None  # None = global lock
    assert int((cfg.new_session_expire_time - cfg.expire_time).total_seconds()) == 60 - 1800
    c = cfg.live_connect_constraints
    assert c.model == "gemini-3.8-live"
    assert [str(m.value if hasattr(m, "value") else m) for m in c.config.response_modalities] == ["AUDIO"]
    assert c.config.system_instruction == live.SYSTEM_INSTRUCTION
    assert c.config.input_audio_transcription is not None and c.config.output_audio_transcription is not None
    assert c.config.session_resumption is not None
    names = [f.name for f in c.config.tools[0].function_declarations]
    assert names == ["report_absence", "approve", "choose_fallback", "get_status", "cancel_gap"]


def test_rate_limits_return_429(api: Any) -> None:
    now = [0.0]
    limiter = live.RateLimiter(per_ip=2, total=3, window_s=600, clock=lambda: now[0])
    client = app_with(api, FakeClient(), limiter)
    a = {"X-Forwarded-For": "1.1.1.1"}
    assert [client.post("/live/token", headers=a).status_code for _ in range(3)] == [200, 200, 429]
    assert client.post("/live/token", headers={"X-Forwarded-For": "2.2.2.2"}).status_code == 200
    assert client.post("/live/token", headers={"X-Forwarded-For": "3.3.3.3"}).status_code == 429  # global
    now[0] = 601
    assert client.post("/live/token", headers=a).status_code == 200


def test_sdk_error_is_502_without_details(api: Any) -> None:
    class Broken(FakeClient):
        def __init__(self) -> None:
            super().__init__()

            def boom(config: Any) -> Any:
                raise RuntimeError(f"bad key {SECRET}")
            self.auth_tokens.create = boom  # type: ignore[method-assign]

    resp = app_with(api, Broken()).post("/live/token")
    assert resp.status_code == 502 and SECRET not in resp.text


def test_voice_off_without_a_client(api: Any) -> None:
    client = TestClient(create_app(api, internal_auth=lambda: None, allowed_origins=["http://localhost:3000"]))
    assert client.post("/live/token").status_code == 501
    assert client.get("/status").json()["voice"] == "off"
