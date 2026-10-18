"""Model-backed ``parse_reply`` (§7.3): Gemini Flash on the Enterprise Agent Platform (global).

Fails closed: staff text goes inside delimiters as data; output is validated against the §7.3
schema; one retry on invalid output, then ``unclear``; confidence below ``parse_confidence_min``, any
error or a timeout also give ``unclear``, never an accept. The guard runs before this (api).
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from services.agent.app.logic import REASONS, SCHEMA_INTENTS

PROMPT_PATH = "prompts/parse_reply.md"
_HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "intent": {"type": "string", "enum": list(SCHEMA_INTENTS)},
        "counter_window": {"anyOf": [{"type": "null"}, {
            "type": "object", "properties": {"start": {"type": "string"}, "end": {"type": "string"}},
            "required": ["start", "end"]}]},
        "reason_category": {"type": "string", "enum": list(REASONS)},
        "confidence": {"type": "number"},
        "language_tags": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["intent", "counter_window", "reason_category", "confidence", "language_tags"],
}


def validate(out: dict[str, Any]) -> dict[str, Any] | None:
    """The §7.3 shape, or None."""
    intent, window = out.get("intent"), out.get("counter_window")
    conf, tags = out.get("confidence"), out.get("language_tags")
    if intent not in SCHEMA_INTENTS or out.get("reason_category") not in REASONS:
        return None
    if not isinstance(conf, (int, float)) or isinstance(conf, bool) or not 0 <= conf <= 1:
        return None
    if not isinstance(tags, list) or not all(isinstance(t, str) for t in tags):
        return None
    if intent == "counter":
        if not (isinstance(window, dict) and all(isinstance(window.get(k), str) and _HHMM.match(window[k])
                                                 for k in ("start", "end")) and window["start"] < window["end"]):
            return None
        window = {"start": window["start"], "end": window["end"]}
    else:
        window = None
    return {"intent": intent, "counter_window": window, "reason_category": out["reason_category"],
            "confidence": float(conf), "language_tags": tags}


def build_user_message(text: str, offer: dict[str, Any]) -> str:
    safe = text.replace("</staff_reply>", "").replace("<staff_reply>", "")
    return (f"Offered shift: {offer['start'][11:16]} to {offer['end'][11:16]} on {offer['start'][:10]}.\n"
            f"<staff_reply>\n{safe}\n</staff_reply>")


class GeminiParser:
    def __init__(self, generate: Callable[[str, str, dict[str, Any], float], dict[str, Any]],
                 model_id: str, system: str, prompt_sha: str, cfg: dict[str, Any]):
        self.generate, self.model_id, self.system, self.prompt_sha = generate, model_id, system, prompt_sha
        self.min_conf = float(cfg["parse_confidence_min"])

    def parse_reply(self, text: str, offer: dict[str, Any]) -> dict[str, Any]:
        user = build_user_message(text, offer)
        parsed, error = None, None
        for _ in range(2):  # one retry on invalid output
            try:
                parsed = validate(self.generate(self.system, user, SCHEMA, 0.0))
            except Exception as exc:  # error or timeout: fail closed, no retry storm
                error = type(exc).__name__
                break
            if parsed is not None:
                break
        if parsed is None:
            parsed = {"intent": "unclear", "counter_window": None, "reason_category": "none",
                      "confidence": 0.0, "language_tags": []}
        elif parsed["confidence"] < self.min_conf:
            parsed = dict(parsed, intent="unclear", counter_window=None)
        return dict(parsed, parser_impl=self.model_id, prompt_sha256=self.prompt_sha,
                    **({"parse_error": error} if error else {}))


def from_registry(cfg: dict[str, Any]) -> GeminiParser:  # pragma: no cover - needs Google Cloud
    from pathlib import Path

    from services.common.gemini import generate_json, prompt_sha256
    from services.common.models import enterprise_client, pinned_role

    spec = pinned_role("agent")
    client = enterprise_client("agent", timeout_ms=8000)

    def generate(system: str, user: str, schema: dict[str, Any], temperature: float) -> dict[str, Any]:
        return generate_json(client, spec["model_id"], system, user, schema, temperature)

    return GeminiParser(generate, spec["model_id"], Path(PROMPT_PATH).read_text(encoding="utf-8"),
                        prompt_sha256(PROMPT_PATH), cfg)
