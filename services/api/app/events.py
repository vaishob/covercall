"""Gap state machine table, tamper-evident event chain, and reply dedup (§4.1 KICKSTART, §5.1, §5.4).

``TRANSITIONS`` encodes the §5.1 table once; the append guard, the workflow check and the tests
all use it. Any transition not in the table is a bug and raises ``IllegalTransition``.

Each event lives at ``gaps/{gapId}/events/{seq:06d}``. Its hash is
``sha256(prev_hash.encode() + canonical)`` with
``canonical = json.dumps(event_without_hash, sort_keys=True, separators=(",", ":"),
ensure_ascii=False).encode("utf-8")``; the genesis ``prev_hash`` is ``"0" * 64``.
The append is one transaction: read the gap, check version and transition, write the event,
update ``state``, ``version + 1``, ``last_seq`` and ``last_hash``.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

from services.common.pii import redact
from services.common.store import AlreadyExists, Store, Txn

GENESIS = "0" * 64
TERMINAL_STATES = frozenset({"FILLED", "RESOLVED", "CANCELLED", "HELD"})
NON_TERMINAL_STATES = ("REPORTED", "GUARDED", "SOLVED", "OUTREACH", "COMMITTING", "ESCALATED")

# (from_state, event_type, to_state). from_state None = the gap does not exist yet.
TRANSITIONS: tuple[tuple[str | None, str, str], ...] = (
    (None, "gap.reported", "REPORTED"),
    ("REPORTED", "input.guarded", "GUARDED"),
    ("REPORTED", "guard.unavailable", "HELD"),
    ("REPORTED", "guard.flagged", "HELD"),
    ("GUARDED", "plan.solved", "SOLVED"),
    ("GUARDED", "plan.disagreement", "HELD"),
    ("SOLVED", "plan.approved", "OUTREACH"),
    ("SOLVED", "plan.rejected", "GUARDED"),
    ("OUTREACH", "reply.accept", "COMMITTING"),
    ("OUTREACH", "reply.decline", "OUTREACH"),
    ("OUTREACH", "offer.timeout", "OUTREACH"),
    ("OUTREACH", "reply.counter", "OUTREACH"),
    ("OUTREACH", "reply.counter", "SOLVED"),
    ("OUTREACH", "reply.flagged", "OUTREACH"),
    ("OUTREACH", "escalation.due", "ESCALATED"),
    ("COMMITTING", "commit.ok", "FILLED"),
    ("COMMITTING", "commit.conflict", "OUTREACH"),
    ("ESCALATED", "fallback.chosen", "RESOLVED"),
    # "any" in §5.1: every state a gap can be in once it exists, except the terminal FILLED,
    # RESOLVED and CANCELLED. HELD can still be cancelled by the lead.
    *((s, "gap.cancelled", "CANCELLED") for s in (*NON_TERMINAL_STATES, "HELD")),
)
EVENT_TYPES = frozenset(t for _, t, _ in TRANSITIONS)


class IllegalTransition(RuntimeError):
    pass


class VersionConflict(RuntimeError):
    """``commit.conflict`` handling: the gap changed since the caller read it."""


def targets(from_state: str | None, event_type: str) -> list[str]:
    return [to for frm, t, to in TRANSITIONS if frm == from_state and t == event_type]


def canonical(event_without_hash: dict[str, Any]) -> bytes:
    return json.dumps(event_without_hash, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def event_hash(prev_hash: str, event_without_hash: dict[str, Any]) -> str:
    return hashlib.sha256(prev_hash.encode() + canonical(event_without_hash)).hexdigest()


def gap_path(gap_id: str) -> str:
    return f"gaps/{gap_id}"


def event_path(gap_id: str, seq: int) -> str:
    return f"gaps/{gap_id}/events/{seq:06d}"


def append_in_txn(
    txn: Txn,
    gap_id: str,
    event_type: str,
    *,
    actor: str,
    ts: str,
    payload: dict[str, Any] | None = None,
    to_state: str | None = None,
    expected_version: int | None = None,
    model_ids: list[str] | None = None,
    rule_ids: list[str] | None = None,
    trace_id: str = "",
    gap_fields: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Append one event inside an existing transaction and return it (with its hash)."""
    gap = txn.get(gap_path(gap_id))
    from_state = gap["state"] if gap else None
    allowed = targets(from_state, event_type)
    if not allowed:
        raise IllegalTransition(f"{gap_id}: ({from_state}, {event_type}) is not in TRANSITIONS")
    if to_state is None:
        if len(allowed) != 1:
            raise IllegalTransition(f"{event_type} from {from_state} needs to_state: {allowed}")
        to_state = allowed[0]
    elif to_state not in allowed:
        raise IllegalTransition(f"{gap_id}: ({from_state}, {event_type}, {to_state}) not allowed")
    version = int(gap["version"]) if gap else 0
    if expected_version is not None and expected_version != version:
        raise VersionConflict(f"{gap_id}: expected version {expected_version}, found {version}")
    if actor not in ("lead", "system") and not actor.startswith(("staff:", "model:")):
        raise ValueError(f"bad actor {actor!r}")

    seq = (int(gap["last_seq"]) if gap else 0) + 1
    prev_hash = gap["last_hash"] if gap else GENESIS
    event = {
        "seq": seq,
        "type": event_type,
        "from_state": from_state,
        "to_state": to_state,
        "actor": actor,
        "model_ids": list(model_ids or []),
        "rule_ids": list(rule_ids or []),
        "trace_id": trace_id,
        "payload": redact(payload or {}),
        "prev_hash": prev_hash,
        "ts": ts,
        "synthetic": True,
    }
    event["hash"] = event_hash(prev_hash, event)
    txn.create(event_path(gap_id, seq), event)
    update = dict(redact(gap_fields or {}), state=to_state, version=version + 1, last_seq=seq,
                  last_hash=event["hash"], updated_at=ts)
    if gap is None:
        txn.set(gap_path(gap_id), dict(update, gap_id=gap_id, created_at=ts, synthetic=True))
    else:
        txn.update(gap_path(gap_id), update)
    return event


def append_event(store: Store, gap_id: str, event_type: str, **kwargs: Any) -> dict[str, Any]:
    return store.transaction(lambda txn: append_in_txn(txn, gap_id, event_type, **kwargs))


@dataclass
class ChainReport:
    gap_id: str
    ok: bool
    events: int
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"gap_id": self.gap_id, "ok": self.ok, "events": self.events, "errors": self.errors}


def verify_chain(store: Store, gap_id: str) -> ChainReport:
    """Recompute every hash; check seq continuity, links, and the gap's head pointer."""
    errors: list[str] = []
    docs = store.list(f"gaps/{gap_id}/events")
    prev = GENESIS
    for i, (doc_id, ev) in enumerate(docs, start=1):
        if doc_id != f"{i:06d}" or ev.get("seq") != i:
            errors.append(f"seq gap or reorder at position {i}: doc {doc_id}, seq {ev.get('seq')}")
        if ev.get("prev_hash") != prev:
            errors.append(f"event {doc_id}: prev_hash does not link to the previous event")
        body = {k: v for k, v in ev.items() if k != "hash"}
        if event_hash(ev.get("prev_hash", ""), body) != ev.get("hash"):
            errors.append(f"event {doc_id}: hash mismatch (content changed)")
        prev = ev.get("hash", "")
    gap = store.get(gap_path(gap_id))
    if gap is None:
        errors.append("gap document missing")
    else:
        if gap.get("last_seq") != len(docs):
            errors.append(f"gap.last_seq={gap.get('last_seq')} but {len(docs)} events")
        if docs and gap.get("last_hash") != prev:
            errors.append("gap.last_hash does not match the last event")
        if docs and gap.get("state") != docs[-1][1].get("to_state"):
            errors.append("gap.state does not match the last event's to_state")
    return ChainReport(gap_id=gap_id, ok=not errors, events=len(docs), errors=errors)


def dedup_message(store: Store, message_id: str, ts: str) -> bool:
    """Transactionally create ``dedup/{message_id}``. True = first time seen; False = duplicate."""
    if not message_id:
        raise ValueError("message_id is required")

    def run(txn: Txn) -> bool:
        if txn.get(f"dedup/{message_id}") is not None:
            return False
        txn.create(f"dedup/{message_id}", {"message_id": message_id, "first_seen": ts,
                                           "synthetic": True})
        return True

    try:
        return store.transaction(run)
    except AlreadyExists:
        return False
