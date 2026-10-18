"""workflows/coverage_cascade.yaml against the §5.1 table and the KICKSTART §4.4 rules.

Cloud Workflows has no local emulator, so the YAML is checked statically here and executed by the
local driver (evals/runners/local_cascade.py), which must mirror its steps.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from policy.compile_cpsat import load_company_config
from services.api.app.events import EVENT_TYPES, TRANSITIONS

WF = yaml.safe_load(Path("workflows/coverage_cascade.yaml").read_text(encoding="utf-8"))
DRIVER = Path("evals/runners/local_cascade.py").read_text(encoding="utf-8")
CORE = Path("services/api/app/core.py").read_text(encoding="utf-8")
CFG = load_company_config()


def _walk(node: Any, path: str = "") -> list[tuple[str, Any]]:
    out = [(path, node)]
    if isinstance(node, dict):
        for k, v in node.items():
            out += _walk(v, f"{path}/{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            out += _walk(v, f"{path}[{i}]")
    return out


def _step_names(steps: list[dict[str, Any]]) -> list[str]:
    names = []
    for step in steps:
        for name, body in step.items():
            names.append(name)
            if isinstance(body, dict):
                for key in ("steps",):
                    if key in body:
                        names += _step_names(body[key])
                if "parallel" in body:
                    names += _step_names(body["parallel"]["for"]["steps"])
                if "try" in body and isinstance(body.get("except"), dict):
                    names += _step_names(body["except"]["steps"])
    return names


def test_yaml_has_main_and_subworkflows() -> None:
    assert set(WF) == {"main", "post", "transition"}


def test_every_event_type_in_the_yaml_is_in_the_table() -> None:
    used = {v for p, v in _walk(WF) if p.endswith("/body/type") and isinstance(v, str)}
    assert used, "no transitions found"
    assert used <= EVENT_TYPES, used - EVENT_TYPES


def test_every_table_event_is_emitted_by_the_workflow_or_an_endpoint_it_calls() -> None:
    used = {v for p, v in _walk(WF) if p.endswith("/body/type") and isinstance(v, str)}
    via_api = set(re.findall(r'"((?:gap|reply|offer|commit)\.[a-z]+)"', CORE))
    assert EVENT_TYPES <= used | via_api, EVENT_TYPES - used - via_api


def test_guard_step_never_retries_and_fails_closed() -> None:
    guard = next(s["guard_input"] for s in WF["main"]["steps"] if "guard_input" in s)
    assert "retry" not in guard and "except" in guard
    names = [n for s in WF["main"]["steps"] for n in s]
    assert "guard_unavailable" in names


def test_every_http_call_uses_oidc_and_the_retry_policy() -> None:
    calls = [v for p, v in _walk(WF) if isinstance(v, dict) and v.get("call") == "http.post"]
    assert calls
    for c in calls:
        assert c["args"]["auth"]["type"] == "OIDC"
        assert c["args"]["auth"]["audience"] == "${api}"  # api verifies this audience
    post = WF["post"]["steps"][0]["call_api"]
    assert post["retry"]["max_retries"] + 1 == CFG["retry_attempts"]
    assert post["retry"]["backoff"]["multiplier"] > 1


def test_waits_are_durable_callbacks_with_timeout_handling() -> None:
    waits = [(p, v) for p, v in _walk(WF) if isinstance(v, dict) and v.get("call") == "events.await_callback"]
    assert len(waits) >= 3
    for _, w in waits:
        assert "timeout" in w["args"]
    text = Path("workflows/coverage_cascade.yaml").read_text(encoding="utf-8")
    assert text.count('"TimeoutError" in e.tags') >= 3
    assert "events.create_callback_endpoint" in text


def test_fan_out_uses_one_endpoint_per_offer_in_a_parallel_loop() -> None:
    send = next(s["send_offers"] for s in WF["main"]["steps"] if "send_offers" in s)
    branch = send["parallel"]["for"]["steps"]
    assert set(send["parallel"]["shared"]) == {"winner", "cancelled_flag"}
    assert list(branch[0])[0] == "create_cb"


def test_local_driver_mirrors_every_yaml_step() -> None:
    names = set(_step_names(WF["main"]["steps"]))
    # Error re-raises and the guard's except-branch have no driver counterpart.
    internal_only = {"guard_error", "approval_rethrow", "is_timeout", "rethrow", "fallback_rethrow"}
    mirrored = set(re.findall(r'(?<![A-Za-z_])step\("([a-z_]+)"\)', DRIVER))
    missing = names - internal_only - mirrored
    assert not missing, f"driver does not mirror: {sorted(missing)}"
    assert mirrored <= names, f"driver steps not in YAML: {sorted(mirrored - names)}"


def test_transitions_table_covers_every_state() -> None:
    states = {t for _, _, t in TRANSITIONS}
    assert states == {"REPORTED", "GUARDED", "SOLVED", "OUTREACH", "COMMITTING", "FILLED",
                      "ESCALATED", "RESOLVED", "HELD", "CANCELLED"}
