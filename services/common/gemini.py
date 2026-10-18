"""Gemini calls shared by the reply parser (api) and persona text (persona-sim).

Every call is pinned by ``config/models.yaml`` and identified by the model ID plus the SHA-256 of
its prompt file (``prompts/*.md``), which callers record in events. All data is synthetic.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def prompt_sha256(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def generate_json(client: Any, model_id: str, system: str, user: str, schema: dict[str, Any],
                  temperature: float, seed: int | None = None) -> dict[str, Any]:
    """One structured-output call. Raises on transport errors or non-JSON output."""
    from google.genai import types

    resp = client.models.generate_content(
        model=model_id, contents=user,
        config=types.GenerateContentConfig(system_instruction=system, temperature=temperature, seed=seed,
                                           response_mime_type="application/json",
                                           response_json_schema=schema))
    out = json.loads(resp.text or "")
    if not isinstance(out, dict):
        raise ValueError("model output is not a JSON object")
    return out
