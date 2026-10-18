"""``POST /live/token``: single-use Live API ephemeral tokens for the browser (Slice 4, decision 0019).

The token locks the whole session config server-side (``lock_additional_fields`` omitted = global
lock): the model, audio responses, both transcriptions, session resumption, the system instruction
and the five tool declarations. The browser cannot change them. The API key never leaves this
process: it is not logged and not returned. Abuse limits: per-IP and global, in memory.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Any

SYSTEM_INSTRUCTION = (
    "You are CoverCall's voice front end for a shift lead at a small Singapore cafe chain. All data is "
    "synthetic. Collect the absence details (outlet: bugis, tampines or jurong_east; station: barista, "
    "kitchen or cashier; shift start time and date; the absent person's name if given), then call "
    "report_absence. If the tool result asks a question, ask the lead that question. When the result "
    "contains readback_text, read it back to the lead exactly, word for word, and ask for approval. "
    "Call approve with decision approve only after the lead clearly says yes; anything else is "
    "decision reject. You never decide legality and never invent plans, costs, times or names: every "
    "fact you say comes from a tool result. Use get_status for progress, choose_fallback when the gap "
    "is escalated and the lead picks an option, and cancel_gap only when the lead asks to cancel. "
    "Keep replies short."
)


def _fn(name: str, description: str, props: dict[str, str], required: list[str]) -> dict[str, Any]:
    return {"name": name, "description": description,
            "parameters": {"type": "OBJECT", "required": required,
                           "properties": {k: {"type": "STRING", "description": v} for k, v in props.items()}}}


TOOL_DECLARATIONS: list[dict[str, Any]] = [
    _fn("report_absence", "Report a staff absence. The server resolves the name and shift, or asks a question. "
        "Returns readback_text once a plan is ready.",
        {"outlet": "Outlet ID (bugis, tampines, jurong_east)",
         "shift_start": "Shift start, ISO 8601 with +08:00 (e.g. 2026-11-03T07:00:00+08:00) or HH:MM",
         "station": "Station (barista, kitchen, cashier)", "staff_name": "Absent staff member's name, if given"},
        ["outlet", "shift_start", "station"]),
    _fn("approve", "Record the lead's answer to the read-back. The server checks for a clear yes.",
        {"decision": "approve (only after a clear spoken yes) or reject"}, ["decision"]),
    _fn("choose_fallback", "Choose a fallback when the gap is escalated.",
        {"gap_id": "Gap ID", "option": "borrow, reduced_service, lead_covers, agency or unfilled"},
        ["gap_id", "option"]),
    _fn("get_status", "Current state of a gap.", {"gap_id": "Gap ID"}, ["gap_id"]),
    _fn("cancel_gap", "Cancel an active gap (open offers are withdrawn).", {"gap_id": "Gap ID"}, ["gap_id"]),
]


class RateLimited(Exception):
    pass


class RateLimiter:
    """Sliding window: at most ``per_ip`` tokens per IP and ``total`` overall per ``window_s``."""

    def __init__(self, per_ip: int = 5, total: int = 60, window_s: float = 600,
                 clock: Callable[[], float] = time.monotonic):
        self.per_ip, self.total, self.window_s, self.clock = per_ip, total, window_s, clock
        self._all: deque[float] = deque()
        self._by_ip: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def check(self, ip: str) -> None:
        with self._lock:
            now = self.clock()
            for q in (self._all, self._by_ip.setdefault(ip, deque())):
                while q and now - q[0] >= self.window_s:
                    q.popleft()
            if len(self._all) >= self.total:
                raise RateLimited("global token limit reached")
            if len(self._by_ip[ip]) >= self.per_ip:
                raise RateLimited("per-IP token limit reached")
            self._all.append(now)
            self._by_ip[ip].append(now)


def token_config(model_id: str, now: datetime, start_ttl_s: int, session_ttl_s: int, uses: int) -> Any:
    from google.genai import types

    return types.CreateAuthTokenConfig(
        uses=uses,
        new_session_expire_time=now + timedelta(seconds=start_ttl_s),
        expire_time=now + timedelta(seconds=session_ttl_s),
        live_connect_constraints=types.LiveConnectConstraints(
            model=model_id,
            config=types.LiveConnectConfig(
                response_modalities=[types.Modality.AUDIO],
                input_audio_transcription=types.AudioTranscriptionConfig(),
                output_audio_transcription=types.AudioTranscriptionConfig(),
                session_resumption=types.SessionResumptionConfig(),
                system_instruction=SYSTEM_INSTRUCTION,
                tools=[types.Tool(function_declarations=[types.FunctionDeclaration(**d)
                                                         for d in TOOL_DECLARATIONS])],
            ),
        ),
    )  # lock_additional_fields omitted: the SDK sends a global lock (every field fixed)


def mint(client: Any, spec: dict[str, Any], now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    cfg = token_config(spec["model_id"], now, int(spec["ephemeral_token_start_ttl_s"]),
                       int(spec["ephemeral_token_session_ttl_s"]), int(spec["ephemeral_token_uses"]))
    token = client.auth_tokens.create(config=cfg)
    return {"token": token.name, "expires_at": cfg.expire_time.isoformat(),
            "new_session_expires_at": cfg.new_session_expire_time.isoformat(),
            "model_id": spec["model_id"], "api_version": spec["api_version"]}


def developer_client(api_key: str, api_version: str) -> Any:  # pragma: no cover - needs the key
    from google import genai

    return genai.Client(api_key=api_key, http_options={"api_version": api_version})
