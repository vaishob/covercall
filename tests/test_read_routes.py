"""Client-safe read routes, CORS, report_absence resolution, approval isolation (decision 0015)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from datagen.loader import load_data
from evals.runners.capture_fixtures import FIXTURE_DIR, SCENARIOS, capture, render
from evals.runners.local_cascade import LocalRun, load_scenario
from policy.compile_cpsat import load_company_config, load_rules
from services.api.app.main import create_app

CFG = load_company_config()
RULES = load_rules()


@pytest.fixture(scope="module")
def data() -> dict[str, Any]:
    return load_data()


@pytest.fixture(scope="module")
def captured(data: dict[str, Any]) -> dict[str, tuple[dict[str, Any], list[tuple[str, Any]]]]:
    return {sid: capture(sid, data) for sid in SCENARIOS.values()}


def test_status_reports_impls_and_registry_models(data: dict[str, Any]) -> None:
    run = LocalRun(load_scenario("S-017"), data, CFG, RULES)
    status = run.get("/status")
    assert status["guard_impl"] == "stub-v0" and status["parser_impl"] == "stub-v0"
    roles = yaml.safe_load(Path("config/models.yaml").read_text(encoding="utf-8"))["roles"]
    assert {k: m["model_id"] for k, m in status["models"].items()} == {k: r["model_id"] for k, r in roles.items()}
    assert status["models"]["guard"]["model_id"] == "TODO-VERIFY"  # stub-v0 runs; no guard model yet
    assert status["time_scale"] == 1.0 and status["synthetic"] is True


def test_scenarios_are_real_dataset_ids(data: dict[str, Any]) -> None:
    scenarios = [yaml.safe_load(p.read_text(encoding="utf-8"))
                 for p in sorted(Path("evals/datasets/golden").glob("*.yaml"))]
    run = LocalRun(None, data, CFG, RULES, scenarios=scenarios)
    listed = run.get("/scenarios")
    assert [s["scenario_id"] for s in listed] == ["S-017", "S-002"]
    assert [s["label"] for s in listed] == ["6:02am sick call", "Nobody replies"]
    for s in listed:
        assert Path(f"evals/datasets/golden/{s['scenario_id']}.yaml").exists()
        assert "personas" not in s and "overrides" not in s  # no hidden persona state


def test_evals_serves_no_numbers_before_bigquery(data: dict[str, Any]) -> None:
    ev = LocalRun(load_scenario("S-017"), data, CFG, RULES).get("/evals")
    assert ev["status"] == "no_eval_run" and ev["latest_run"] is None and ev["metrics"] == []


def test_gap_view_shape_and_naive_saving(captured: dict[str, Any]) -> None:
    fixture, _ = captured["S-017"]
    final = fixture["snapshots"][-1]["gap"]
    assert final["gap"]["state"] == "FILLED" and final["gap"]["absent_staff_name"] == "Ali"
    assert final["gap"]["t_esc_locked"] and isinstance(final["gap"]["cost_saved_cents"], int)
    plan = final["plan"]
    naive = plan["naive_first_pick"]
    assert naive["staff_id"] == "stf_004" and "SG-EA4-OT-CAP-72" in naive["blocking_rule_ids"]
    for opt in plan["options"]:
        assert opt["saves_vs_naive_cents"] == naive["overtime_cents"] - opt["overtime_cost_cents"]
        for seg in opt["segments"]:
            assert seg["display_name"] and all(isinstance(v, int) for v in seg["cost_breakdown"].values())
            assert all({"rule_id", "status", "kind", "title", "message", "source_url"} <= set(r)
                       for r in seg["rules_checked"])
    assert any(len(o["segments"]) == 2 for o in plan["options"])  # two-person split plans exist
    rejected = {r["staff_id"]: r for r in plan["rejected"]}
    assert rejected["stf_004"]["rules"][0]["rule_id"] == "SG-EA4-OT-CAP-72"
    assert rejected["stf_004"]["rules"][0]["kind"] == "hard"
    statuses = [o["status"] for o in final["offers"]]
    assert statuses[:3] == ["decline", "countered", "timeout"]
    assert final["committed"]["segments"][0]["display_name"]


def test_rule_sources_come_from_the_specs(captured: dict[str, Any]) -> None:
    specs = {r["id"]: r["source"]["url"] for r in RULES}
    for fixture, _ in captured.values():
        for snap in fixture["snapshots"]:
            plan = snap["gap"]["plan"]
            if not plan:
                continue
            for opt in plan["options"]:
                for seg in opt["segments"]:
                    for r in seg["rules_checked"]:
                        assert r["source_url"] == specs[r["rule_id"]]
            for rej in plan["rejected"]:
                for r in rej["rules"]:
                    assert r["source_url"] == specs[r["rule_id"]]


def test_events_view_includes_chain_verification(captured: dict[str, Any]) -> None:
    for fixture, _ in captured.values():
        assert fixture["events"]["chain"]["ok"] is True
        assert fixture["events"]["chain"]["events"] == len(fixture["events"]["events"])


def test_approval_route_only_while_pending(data: dict[str, Any], captured: dict[str, Any]) -> None:
    fixture, responses = captured["S-017"]
    pending = [s for s in fixture["snapshots"] if s["approval"]]
    assert pending and all(s["gap"]["gap"]["state"] == "SOLVED" for s in pending)
    run = LocalRun(load_scenario("S-017"), data, CFG, RULES)
    gap_id = run.post("/gaps", {"scenario_id": "S-017"})["gap_id"]
    idle = run.client.get(f"/gaps/{gap_id}/approval")
    assert idle.status_code == 200 and idle.json() == {"gap_id": gap_id, "pending": False, "synthetic": True}


def _secrets(run_store: Any) -> tuple[set[str], set[str], set[str]]:
    nonces: set[str] = set()
    urls: set[str] = set()
    texts: set[str] = set()
    for _, doc in run_store.list("server"):
        if doc.get("pending_approval"):
            nonces.add(doc["pending_approval"]["nonce"])
        urls.update(v for k, v in doc.items() if k.endswith("_callback") and v)
    for _, a in run_store.list("approvals"):
        nonces.add(a["nonce"])
    for _, o in run_store.list("offers"):
        urls.add(o["callback_url"])
    texts.update(r["text"] for _, r in run_store.list("replies_raw"))
    texts.update(i["text"] for _, i in run_store.list("inputs") if i["text"])
    return nonces, urls, texts


def test_no_read_route_leaks_nonce_callback_url_or_raw_text(data: dict[str, Any]) -> None:
    for sid in SCENARIOS.values():
        run = LocalRun(load_scenario(sid), data, CFG, RULES)
        responses: list[tuple[str, Any]] = []

        def observe(gap_id: str, step: str, run: LocalRun = run,
                    responses: list[tuple[str, Any]] = responses) -> None:
            if not gap_id:
                return
            for path in (f"/gaps/{gap_id}", f"/gaps/{gap_id}/events", f"/gaps/{gap_id}/quarantine",
                         "/status", "/scenarios", "/evals", f"/gaps/{gap_id}/approval"):
                resp = run.client.get(path)
                responses.append((path, resp.json()))

        run.observer = observe
        run.run()
        nonces, urls, texts = _secrets(run.store)
        assert nonces and urls and texts
        for path, body in responses:
            dumped = json.dumps(body, ensure_ascii=False)
            for url in urls:
                assert url not in dumped, (path, url)
            for text in texts:
                assert text not in dumped, (path, text)
            if not path.endswith("/approval"):
                for nonce in nonces:
                    assert nonce not in dumped, (path, nonce)
            assert "callback" not in dumped, path
        assert any(path.endswith("/approval") and body.get("pending") and body.get("nonce") for path, body in responses)
        assert all("nonce" not in body for path, body in responses if path.endswith("/approval") and not body.get("pending"))


def test_cors_allows_only_configured_origins(data: dict[str, Any]) -> None:
    run = LocalRun(load_scenario("S-017"), data, CFG, RULES, allowed_origins=["http://localhost:3000"])
    ok = run.client.options("/status", headers={"Origin": "http://localhost:3000",
                                                "Access-Control-Request-Method": "GET"})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:3000"
    bad = run.client.get("/status", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in bad.headers
    with pytest.raises(ValueError):
        create_app(run.api, internal_auth=lambda: None, allowed_origins=["*"])


def test_report_absence_resolves_names_or_asks(data: dict[str, Any]) -> None:
    run = LocalRun(load_scenario("S-017"), data, CFG, RULES)
    made = run.post("/gaps", {"outlet": "bugis", "station": "barista", "shift_start": "07:00",
                              "staff_name": "Ali", "text": "Ali can't make it, Bugis morning"})
    assert made["status"] == "created"
    gap = run.get(f"/gaps/{made['gap_id']}")["gap"]
    assert gap["absent_staff_id"] == "stf_011" and gap["end"] == "2026-11-03T15:00:00+08:00"
    unknown = run.post("/gaps", {"outlet": "bugis", "station": "barista", "shift_start": "07:00",
                                 "staff_name": "Zorro"})
    assert unknown["status"] == "clarify" and "gap_id" not in unknown
    wrong_time = run.post("/gaps", {"outlet": "bugis", "station": "barista", "shift_start": "05:00"})
    assert wrong_time["status"] == "clarify" and "Nobody is rostered" in wrong_time["question"]
    twin = dict(data["staff"]["stf_004"], staff_id="stf_099", display_name="Ali")
    run.store.set("staff/stf_099", twin)
    ambiguous = run.post("/gaps", {"outlet": "bugis", "station": "barista", "shift_start": "07:00",
                                   "staff_name": "ali"})
    assert ambiguous["status"] == "clarify" and len(ambiguous["candidates"]) == 2
    assert len(run.store.list("gaps")) == 1  # clarifications never create a gap


def test_live_token_is_an_honest_501(data: dict[str, Any]) -> None:
    resp = LocalRun(load_scenario("S-017"), data, CFG, RULES).client.post("/live/token")
    assert resp.status_code == 501 and "Slice 4" in resp.json()["message"]


@pytest.mark.parametrize("name", sorted(SCENARIOS))
def test_contract_fixtures_match_current_backend(name: str, captured: dict[str, Any]) -> None:
    """Drift guard: regenerate with `python -m evals.runners.capture_fixtures` after an intended change."""
    fixture, _ = captured[SCENARIOS[name]]
    assert (FIXTURE_DIR / f"{name}.json").read_text(encoding="utf-8") == render(fixture)
