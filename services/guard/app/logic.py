"""Guard stub ``stub-v0`` (§1.3 KICKSTART, §7.4). NOT a model.

Deterministic redaction (``services.common.pii``) plus a minimal deterministic injection and abuse
check. Labels: ``injection``, ``pii``, ``abuse``, ``ok`` (multi-label). The fine-tuned Gemma guard
replaces this in Slice 5. Callers MUST treat any error or timeout as "unavailable" and fail closed.
"""

from __future__ import annotations

import re
from typing import Any

from services.common.pii import find_pii, redact_text

GUARD_IMPL = "stub-v0"

_INJECTION = [
    r"\bignore\b.{0,30}\b(rules?|instructions?|policy|polic(y|ies)|previous|above)\b",
    r"\b(disregard|override|bypass)\b.{0,30}\b(rules?|instructions?|policy|system|guard)\b",
    r"\bsystem prompt\b",
    r"\byou are now\b",
    r"\bact as\b",
    r"\bnew instructions?\b",
    r"\bjailbreak\b",
    r"\b(double|triple) pay\b",
    r"\bgive me the shift at\b",
    r"<\s*/?\s*(system|assistant|tool)\s*>",
]
_ABUSE = [r"\bf+u+c+k+", r"\bsh[i1]t\b", r"\bidiot\b", r"\bstupid\b", r"\bbastard\b",
          r"\bkill (you|yourself)\b"]


def label(text: str) -> dict[str, Any]:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    lowered = text.lower()
    labels = []
    if any(re.search(p, lowered) for p in _INJECTION):
        labels.append("injection")
    if find_pii(text):
        labels.append("pii")
    if any(re.search(p, lowered) for p in _ABUSE):
        labels.append("abuse")
    flagged = [x for x in labels if x in ("injection", "abuse")]
    return {
        "labels": labels or ["ok"],
        "flagged": bool(flagged),
        "redacted_text": redact_text(text),
        "guard_impl": GUARD_IMPL,
    }
