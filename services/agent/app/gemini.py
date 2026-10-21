"""Model-backed ``parse_reply`` (§7.3): Gemini Flash on the Enterprise Agent Platform (global) or,
with ``PARSER_BACKEND=developer``, the Gemini Developer API (decision 0026).

Fails closed: staff text goes inside delimiters as data; output is validated against the §7.3
schema; one retry on invalid output, then ``unclear``; confidence below ``parse_confidence_min``, any
error or a timeout also give ``unclear``, never an accept. The guard runs before this (api).
Transient model errors (429/500/503/504) are retried with backoff inside a total time budget; every
failed attempt is logged (error class and HTTP code, never the staff text).
"""

from __future__ import annotations

import logging
import os
import re
import time
from collections.abc import Callable, Mapping
from typing import Any

from services.agent.app.logic import REASONS, SCHEMA_INTENTS

PROMPT_PATH = "prompts/parse_reply.md"
RETRYABLE_CODES = frozenset({429, 500, 503, 504})
# The SDK sends X-Server-Timeout = attempt timeout and Vertex stops ~3.4 s earlier, so 9 s leaves the
# model ~5.6 s. Worst case: 9 + 0.5 + 9 + 1.5 + 9 = 29 s, under the 30 s budget (workflow allows 60 s).
# The Developer API refuses deadlines under 10 s (400), so it gets 10 s: two full attempts, or three when
# errors come back fast; the budget check decides.
ATTEMPT_TIMEOUT_S = 9.0
ATTEMPT_TIMEOUT_S_BY_BACKEND = {"vertex": ATTEMPT_TIMEOUT_S, "developer": 10.0}
ATTEMPTS = 3
BACKOFF_S = (0.5, 1.5)
BUDGET_S = 30.0
PARSER_BACKENDS = ("vertex", "developer")
log = logging.getLogger(__name__)
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
                 model_id: str, system: str, prompt_sha: str, cfg: dict[str, Any], backend: str = "vertex",
                 attempts: int = ATTEMPTS, attempt_timeout_s: float = ATTEMPT_TIMEOUT_S,
                 backoff_s: tuple[float, ...] = BACKOFF_S, budget_s: float = BUDGET_S,
                 sleep: Callable[[float], None] = time.sleep, clock: Callable[[], float] = time.monotonic):
        self.generate, self.model_id, self.system, self.prompt_sha = generate, model_id, system, prompt_sha
        self.min_conf = float(cfg["parse_confidence_min"])
        self.backend, self.attempts, self.attempt_timeout_s = backend, attempts, attempt_timeout_s
        self.backoff_s, self.budget_s, self.sleep, self.clock = backoff_s, budget_s, sleep, clock

    def parse_reply(self, text: str, offer: dict[str, Any]) -> dict[str, Any]:
        user = build_user_message(text, offer)
        parsed, error = None, None
        start, attempt, invalid_retry_left = self.clock(), 0, 1
        while attempt < self.attempts:
            attempt += 1
            try:
                parsed = validate(self.generate(self.system, user, SCHEMA, 0.0))
            except Exception as exc:  # error or timeout: fail closed; only transient codes are retried
                code = getattr(exc, "code", None)
                error = f"{type(exc).__name__}:{code}" if code is not None else type(exc).__name__
                log.warning("parse_reply attempt %d/%d failed: %s backend=%s elapsed=%.1fs", attempt,
                            self.attempts, error, self.backend, self.clock() - start)
                if code not in RETRYABLE_CODES or not self._retry_fits(attempt, start):
                    break
                self.sleep(self._backoff(attempt))
                continue
            error = None if parsed is not None else "invalid_output"
            if parsed is not None or not invalid_retry_left or not self._retry_fits(attempt, start):
                break
            invalid_retry_left -= 1  # one retry on invalid output
        if parsed is None:
            parsed = {"intent": "unclear", "counter_window": None, "reason_category": "none",
                      "confidence": 0.0, "language_tags": []}
        elif parsed["confidence"] < self.min_conf:
            parsed = dict(parsed, intent="unclear", counter_window=None)
        return dict(parsed, parser_impl=self.model_id, prompt_sha256=self.prompt_sha,
                    parser_backend=self.backend, parse_attempts=attempt,
                    **({"parse_error": error} if error else {}))

    def _retry_fits(self, attempt: int, start: float) -> bool:
        """Another attempt only if it can finish inside the total budget, backoff included."""
        if attempt >= self.attempts:
            return False
        return (self.clock() - start) + self._backoff(attempt) + self.attempt_timeout_s <= self.budget_s

    def _backoff(self, attempt: int) -> float:
        return self.backoff_s[min(attempt, len(self.backoff_s)) - 1]


def parser_backend(env: Mapping[str, str]) -> str:
    """``PARSER_BACKEND``: ``vertex`` (default, Enterprise Agent Platform) or ``developer``."""
    backend = env.get("PARSER_BACKEND", "").strip() or "vertex"
    if backend not in PARSER_BACKENDS:
        raise ValueError(f"PARSER_BACKEND must be one of {PARSER_BACKENDS}, got {backend!r}")
    return backend


def from_registry(cfg: dict[str, Any]) -> GeminiParser:  # pragma: no cover - needs Google Cloud
    from pathlib import Path

    from services.common.gemini import generate_json, prompt_sha256
    from services.common.models import developer_client, enterprise_client, pinned_role

    spec = pinned_role("agent")
    backend = parser_backend(os.environ)
    attempt_timeout_s = ATTEMPT_TIMEOUT_S_BY_BACKEND[backend]
    timeout_ms = int(attempt_timeout_s * 1000)
    client = (developer_client("agent", timeout_ms=timeout_ms) if backend == "developer"
              else enterprise_client("agent", timeout_ms=timeout_ms))

    def generate(system: str, user: str, schema: dict[str, Any], temperature: float) -> dict[str, Any]:
        return generate_json(client, spec["model_id"], system, user, schema, temperature)

    return GeminiParser(generate, spec["model_id"], Path(PROMPT_PATH).read_text(encoding="utf-8"),
                        prompt_sha256(PROMPT_PATH), cfg, backend=backend, attempt_timeout_s=attempt_timeout_s)
