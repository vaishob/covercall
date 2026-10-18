"""Deterministic PII redaction (§4.1, §7.4, §12.2). Runs before anything is written to events,
logs or traces. ``pii_leak`` is a P0 metric, so ``find_pii`` is also used by the tests and evals.

Patterns: Singapore NRIC/FIN, Singapore phone numbers (optional +65), email addresses, and
13-19 digit card-like numbers. Only strings are inspected; numbers stay numbers.
"""

from __future__ import annotations

import re
from typing import Any

PATTERNS: dict[str, re.Pattern[str]] = {
    "nric": re.compile(r"(?<![A-Za-z0-9])[STFGM]\d{7}[A-Z](?![A-Za-z0-9])", re.IGNORECASE),
    "email": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    # Word boundaries on both sides, so digit runs inside hashes and IDs (hex, base64) never match.
    "card": re.compile(r"(?<![\w+])(?:\d[ -]?){12,18}\d(?!\w)"),
    "phone": re.compile(r"(?<![\w+])(?:\+65[ -]?)?[3689]\d{3}[ -]?\d{4}(?!\w)"),
}


def redact_text(text: str) -> str:
    out = text
    for kind, pattern in PATTERNS.items():
        out = pattern.sub(f"[REDACTED:{kind}]", out)
    return out


def redact(value: Any) -> Any:
    """Return a deep copy of ``value`` with every string redacted."""
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, dict):
        return {k: redact(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(v) for v in value]
    return value


def find_pii(value: Any) -> list[str]:
    """Return the kinds of PII still present in ``value`` (empty list = clean)."""
    found: list[str] = []
    if isinstance(value, str):
        found += [k for k, p in PATTERNS.items() if p.search(value)]
    elif isinstance(value, dict):
        for v in value.values():
            found += find_pii(v)
    elif isinstance(value, (list, tuple)):
        for v in value:
            found += find_pii(v)
    return found
