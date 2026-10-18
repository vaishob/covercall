"""Model registry pins (decisions 0019-0021) and Enterprise Agent Platform client construction."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from google.auth.credentials import AnonymousCredentials

from services.common.models import StartupRefused, enterprise_client, load_roles, pinned_role

ENV = {"GOOGLE_CLOUD_PROJECT": "demo-project"}


def test_registry_pins() -> None:
    roles = load_roles()
    assert (roles["voice"]["model_id"], roles["voice"]["provider"], roles["voice"]["api_version"]) == (
        "gemini-3.8-live", "gemini_developer_api", "v1beta")
    for name, model in [("agent", "gemini-3.8-flash"), ("persona_sim", "gemini-3.8-flash"),
                        ("eval_judge", "gemini-4-argon")]:
        role = roles[name]
        assert (role["model_id"], role["provider"], role["location"]) == (model, "vertex_ai", "global"), name
    for name in ("voice", "agent", "persona_sim", "eval_judge"):
        assert str(roles[name]["pinned_at"]) == "2026-10-18", name
    assert roles["guard"]["model_id"] == "TODO-VERIFY" and roles["guard"]["pinned_at"] is None


def test_every_pinned_role_cites_a_source() -> None:
    text = Path("config/models.yaml").read_text(encoding="utf-8")
    blocks = re.split(r"\n  (?=[a-z_]+:\n)", text)[1:]
    for name in ("voice", "agent", "persona_sim", "eval_judge"):
        block = next(b for b in blocks if b.startswith(f"{name}:"))
        assert "# source: https://" in block, name
    assert "google/gemma-3-270m" in next(b for b in blocks if b.startswith("guard:"))


@pytest.mark.parametrize("role", ["agent", "persona_sim"])
def test_enterprise_client_uses_global_endpoint(role: str) -> None:
    client = enterprise_client(role, env=ENV, credentials=AnonymousCredentials())
    api = client._api_client
    assert client.vertexai is True  # enterprise=True; the SDK keeps vertexai as the legacy name
    assert (api.project, api.location) == ("demo-project", "global")
    assert api._http_options.api_version == "v1"
    assert api._http_options.base_url == "https://aiplatform.googleapis.com/"


def test_enterprise_client_refuses() -> None:
    with pytest.raises(StartupRefused, match="role 'guard'"):
        enterprise_client("guard", env=ENV)
    with pytest.raises(StartupRefused, match="GOOGLE_CLOUD_PROJECT"):
        enterprise_client("agent", env={})
    with pytest.raises(StartupRefused, match="role 'voice'"):
        enterprise_client("voice", env=ENV)
    with pytest.raises(StartupRefused, match="role 'nope'"):
        pinned_role("nope")


def test_unpinned_registry_refuses(tmp_path: Path) -> None:
    models = tmp_path / "models.yaml"
    models.write_text("roles:\n  agent: {provider: vertex_ai, api_version: v1, location: global,"
                      " model_id: TODO-VERIFY, pinned_at: null}\n", encoding="utf-8")
    with pytest.raises(StartupRefused, match="role 'agent': model_id is TODO-VERIFY"):
        enterprise_client("agent", env=ENV, models_path=models)
