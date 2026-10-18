"""Transition table, hash chain, redaction and dedup (§4.1, §4.7 KICKSTART; §5.1, §5.4)."""

from __future__ import annotations

import hashlib
import json

import pytest

from services.api.app.events import (
    EVENT_TYPES,
    GENESIS,
    TRANSITIONS,
    IllegalTransition,
    VersionConflict,
    append_event,
    dedup_message,
    event_path,
    verify_chain,
)
from services.common.pii import find_pii, redact
from services.common.store import MemoryStore

TS = "2026-11-03T06:02:00+08:00"
STATES = sorted({s for s, _, _ in TRANSITIONS if s} | {t for _, _, t in TRANSITIONS})


def _gap_in(state: str | None) -> MemoryStore:
    store = MemoryStore()
    if state is not None:
        store.set("gaps/g", {"gap_id": "g", "state": state, "version": 3, "last_seq": 0,
                             "last_hash": GENESIS})
    return store


@pytest.mark.parametrize(("frm", "etype", "to"), TRANSITIONS)
def test_every_table_transition_is_accepted(frm: str | None, etype: str, to: str) -> None:
    store = _gap_in(frm)
    event = append_event(store, "g", etype, actor="system", ts=TS, to_state=to)
    assert (event["from_state"], event["to_state"]) == (frm, to)
    assert store.require("gaps/g")["state"] == to


def test_every_transition_outside_the_table_is_rejected() -> None:
    allowed = {(f, t) for f, t, _ in TRANSITIONS}
    rejected = 0
    for frm in [None, *STATES]:
        for etype in sorted(EVENT_TYPES):
            if (frm, etype) in allowed:
                continue
            with pytest.raises(IllegalTransition):
                append_event(_gap_in(frm), "g", etype, actor="system", ts=TS)
            rejected += 1
    assert rejected > 100  # the full complement of the table, not a sample


def test_terminal_states_accept_nothing_but_held_can_be_cancelled() -> None:
    for state in ("FILLED", "RESOLVED", "CANCELLED"):
        assert not [t for f, t, _ in TRANSITIONS if f == state]
    assert ("HELD", "gap.cancelled", "CANCELLED") in TRANSITIONS


def test_ambiguous_target_needs_explicit_state() -> None:
    with pytest.raises(IllegalTransition):
        append_event(_gap_in("OUTREACH"), "g", "reply.counter", actor="staff:stf_022", ts=TS)
    with pytest.raises(IllegalTransition):
        append_event(_gap_in("OUTREACH"), "g", "reply.counter", actor="staff:stf_022", ts=TS,
                     to_state="FILLED")


def test_version_guard() -> None:
    store = _gap_in("COMMITTING")
    with pytest.raises(VersionConflict):
        append_event(store, "g", "commit.ok", actor="system", ts=TS, expected_version=2)
    append_event(store, "g", "commit.ok", actor="system", ts=TS, expected_version=3)
    assert store.require("gaps/g")["version"] == 4


def test_bad_actor_rejected() -> None:
    with pytest.raises(ValueError):
        append_event(_gap_in(None), "g", "gap.reported", actor="robot", ts=TS)


def _chain() -> MemoryStore:
    store = MemoryStore()
    steps = [("gap.reported", None), ("input.guarded", None), ("plan.solved", None),
             ("plan.approved", None), ("reply.decline", None), ("reply.accept", None),
             ("commit.ok", None)]
    for i, (etype, to) in enumerate(steps):
        append_event(store, "g", etype, actor="system", ts=f"2026-11-03T06:{2 + i:02d}:00+08:00",
                     to_state=to, payload={"n": i, "note": "synthetic"})
    return store


def test_clean_chain_verifies_and_matches_the_spec_formula() -> None:
    store = _chain()
    report = verify_chain(store, "g")
    assert report.ok and report.events == 7, report.errors
    first = store.require(event_path("g", 1))
    body = {k: v for k, v in first.items() if k != "hash"}
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    assert first["hash"] == hashlib.sha256(GENESIS.encode() + canonical).hexdigest()
    assert first["prev_hash"] == "0" * 64
    assert sorted(store.raw()) .count("gaps/g/events/000001") == 1
    for field in ("seq", "type", "from_state", "to_state", "actor", "model_ids", "rule_ids",
                  "trace_id", "payload", "prev_hash", "hash", "ts", "synthetic"):
        assert field in first


def test_tampered_payload_is_detected() -> None:
    store = _chain()
    store.raw()["gaps/g/events/000003"]["payload"]["n"] = 99
    report = verify_chain(store, "g")
    assert not report.ok and any("hash mismatch" in e for e in report.errors)


def test_deleted_event_is_detected() -> None:
    store = _chain()
    del store.raw()["gaps/g/events/000004"]
    report = verify_chain(store, "g")
    assert not report.ok and any("seq" in e or "prev_hash" in e for e in report.errors)


def test_reordered_events_are_detected() -> None:
    store = _chain()
    raw = store.raw()
    raw["gaps/g/events/000002"], raw["gaps/g/events/000003"] = (
        raw["gaps/g/events/000003"], raw["gaps/g/events/000002"])
    assert not verify_chain(store, "g").ok


def test_truncated_tail_is_detected() -> None:
    store = _chain()
    del store.raw()["gaps/g/events/000007"]
    assert not verify_chain(store, "g").ok


def test_failed_transition_writes_nothing() -> None:
    store = _chain()
    before = dict(store.raw())
    with pytest.raises(IllegalTransition):
        append_event(store, "g", "plan.solved", actor="system", ts=TS)
    assert store.raw() == before


def test_redaction_before_write() -> None:
    store = MemoryStore()
    append_event(store, "g", "gap.reported", actor="lead", ts=TS, payload={
        "input": "Ali S1234567D cannot come, call +65 9123 4567 or 81234567, ali@example.com, "
                 "card 4111 1111 1111 1111"})
    text = store.require(event_path("g", 1))["payload"]["input"]
    assert find_pii(text) == []
    for kind in ("nric", "phone", "email", "card"):
        assert f"[REDACTED:{kind}]" in text


def test_redaction_leaves_hashes_ids_and_numbers_alone() -> None:
    sample = {"hash": "f6f80027281d45c36fb0ee3e52b79ef469ad5bea25bc29fb40b4efe47532ba1b",
              "ts": "2026-11-03T06:02:00+08:00", "cents": 15105, "staff": "stf_004"}
    assert redact(sample) == sample
    assert find_pii(sample) == []


def test_dedup_drops_duplicates() -> None:
    store = MemoryStore()
    assert dedup_message(store, "m-1", TS) is True
    assert dedup_message(store, "m-1", TS) is False
    assert dedup_message(store, "m-2", TS) is True
    with pytest.raises(ValueError):
        dedup_message(store, "", TS)
