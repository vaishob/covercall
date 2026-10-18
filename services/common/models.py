"""Model registry (``config/models.yaml``) and Gen AI SDK client construction.

Roles on the Gemini Enterprise Agent Platform (formerly Vertex AI) get a ``google-genai`` client
built as Google's docs specify: ``genai.Client(enterprise=True, project=..., location=...)``
(``vertexai=True`` is now the SDK's legacy flag). The location comes from the registry (``global``,
decision 0021); the project from ``GOOGLE_CLOUD_PROJECT``.

Nothing here runs while the services use their stubs (``AGENT_IMPL=stub-v0``, persona text
``stub-v0``): a client is built only when a model-backed implementation is explicitly enabled.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

MODELS_PATH = Path("config/models.yaml")
ENTERPRISE_PROVIDERS = ("vertex_ai",)


class StartupRefused(RuntimeError):
    pass


def load_roles(models_path: str | Path = MODELS_PATH) -> dict[str, dict[str, Any]]:
    roles: dict[str, dict[str, Any]] = yaml.safe_load(Path(models_path).read_text(encoding="utf-8"))["roles"]
    return roles


def pinned_role(role: str, models_path: str | Path = MODELS_PATH) -> dict[str, Any]:
    """The role's registry entry, or refuse to start (names the role) if it is not pinned."""
    spec = load_roles(models_path).get(role)
    if spec is None:
        raise StartupRefused(f"role '{role}': not in config/models.yaml")
    if "TODO-VERIFY" in str(spec.get("model_id")) or not spec.get("pinned_at"):
        raise StartupRefused(f"role '{role}': model_id is TODO-VERIFY in config/models.yaml")
    return spec


def enterprise_client(role: str, env: dict[str, str] | None = None,
                      models_path: str | Path = MODELS_PATH, credentials: Any = None) -> Any:
    """A ``google-genai`` client for a Gemini Enterprise Agent Platform role (agent, persona_sim,
    eval_judge). Authenticates with the service account (Application Default Credentials)."""
    spec = pinned_role(role, models_path)
    if spec["provider"] not in ENTERPRISE_PROVIDERS:
        raise StartupRefused(f"role '{role}': provider {spec['provider']} is not the Enterprise Agent Platform")
    env = dict(os.environ) if env is None else env
    project = env.get("GOOGLE_CLOUD_PROJECT", "")
    if not project:
        raise StartupRefused(f"role '{role}': GOOGLE_CLOUD_PROJECT is not set")
    from google import genai
    from google.genai import types

    return genai.Client(enterprise=True, project=project, location=spec["location"], credentials=credentials,
                        http_options=types.HttpOptions(api_version=spec["api_version"]))
