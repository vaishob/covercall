"""Synthetic data, data gates, scenarios, baseline and compare (§1.2, §3.8, §3.9, §8)."""

from __future__ import annotations

import ast
import hashlib
import inspect
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pytest
import yaml

from datagen import build_synthetic_dataset
from datagen.loader import DataGateError, load_data, load_staff
from datagen.personas import decide_reply, make_persona
from datagen.scenarios import S017
from evals.cascade_sim import run_covercall
from policy.compile_cpsat import load_company_config, load_rules
from policy.validate import blocking_violations, compute_part4_covered, validate_assignment

RULES = load_rules()
CFG = load_company_config()
COVERAGE = next(r for r in RULES if r["id"] == "SG-EA4-COVERAGE")


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    d = tmp_path_factory.mktemp("data")
    build_synthetic_dataset(seed=42, data_dir=d, with_scenarios=False)
    return load_data(d) | {"dir": d}


def test_generation_is_deterministic(built: dict[str, Any], tmp_path: Path) -> None:
    build_synthetic_dataset(seed=42, data_dir=tmp_path, with_scenarios=False)
    for name in ("staff.json", "shifts.json", "ledgers.json", "sim_personas.json"):
        a = hashlib.sha256((built["dir"] / name).read_bytes()).hexdigest()
        b = hashlib.sha256((tmp_path / name).read_bytes()).hexdigest()
        assert a == b, name


def test_committed_data_matches_generator(built: dict[str, Any]) -> None:
    for name in ("outlets.json", "staff.json", "shifts.json", "ledgers.json", "sim_personas.json",
                 "travel_cache.json"):
        assert (Path("data") / name).read_bytes() == (built["dir"] / name).read_bytes(), name


def test_staff_mix(built: dict[str, Any]) -> None:
    staff = list(built["staff"].values())
    assert 28 <= len(staff) <= 34
    ft = sum(s["contract_type"] == "full_time" for s in staff)
    assert round(100 * ft / len(staff)) in range(58, 63)  # 60/40 design default
    assert sum(s["employee_class"] == "manager_executive" for s in staff) == 1
    covered = [compute_part4_covered(s, COVERAGE) for s in staff]
    assert any(covered) and not all(covered), "salaries must straddle the Part 4 thresholds"
    assert any(not c for s, c in zip(staff, covered, strict=True)
               if s["employee_class"] != "manager_executive")
    for s in staff:
        assert s["synthetic"] is True
        assert s["age"] >= 17
        assert "part4_covered" not in s
        if s["is_student"]:
            assert s["contract_type"] == "part_time" and s["institution"] in (
                "polytechnic", "ITE", "university")
    fsc = [s["fsc_l1_passed_on"] for s in staff]
    assert None in fsc
    assert any(f and f < "2021-11-03" for f in fsc), "some certificates must be lapsed"
    assert any(f and f >= "2022-01-01" for f in fsc)


def test_every_record_is_synthetic(built: dict[str, Any]) -> None:
    for coll in ("outlets", "staff", "ledgers", "personas"):
        for rec in built[coll].values():
            assert rec["synthetic"] is True
    assert all(s["synthetic"] is True for s in built["shifts"])


def test_deliberate_traps_present(built: dict[str, Any]) -> None:
    assert any(led["ot_hours_used"] == 70 for led in built["ledgers"].values())
    # 11 days since the last rest day, derived from the roster and ledger (never stored).
    rests = {date.fromisoformat(d) for lid, led in built["ledgers"].items()
             if led["staff_id"] == "stf_006" for d in led["rest_days"]}
    last = max(d for d in rests if d < date(2026, 11, 3))
    assert (date(2026, 11, 3) - last).days == 11


def test_base_roster_breaks_no_hard_rule(built: dict[str, Any]) -> None:
    week = {(date(2026, 11, 2) + timedelta(days=i)).isoformat() for i in range(7)}
    for s in built["shifts"]:
        if s["start"][:10] not in week:
            continue
        ctx = dict(built, shifts=[x for x in built["shifts"] if x is not s], company=CFG, now=s["start"],
                   gap={"outlet": s["outlet"], "station": s["station"], "start": s["start"],
                        "end": s["end"], "absent_staff_id": None})
        bad = [r.rule_id for r in blocking_violations(validate_assignment(s, ctx, RULES))]
        assert bad == [], (s["shift_id"], s["staff_id"], bad)


def test_travel_is_flagged_placeholder(built: dict[str, Any]) -> None:
    assert built["travel_meta"]["source"] == "placeholder-not-routes-api"
    assert built["travel_meta"]["retrieved_at"] is None


def test_loader_rejects_under_16() -> None:
    rec = {"staff_id": "stf_999", "display_name": "Too Young", "age": 15, "synthetic": True}
    with pytest.raises(DataGateError, match="CO-AGE-SCOPE"):
        load_staff([rec], RULES, CFG)


def test_loader_rejects_missing_age_and_unflagged_records() -> None:
    with pytest.raises(DataGateError):
        load_staff([{"staff_id": "stf_998", "synthetic": True}], RULES, CFG)
    with pytest.raises(DataGateError, match="synthetic"):
        load_staff([{"staff_id": "stf_997", "age": 30}], RULES, CFG)
    with pytest.raises(DataGateError, match="part4_covered"):
        load_staff([{"staff_id": "stf_996", "age": 30, "synthetic": True, "part4_covered": True}],
                   RULES, CFG)


def test_persona_style_never_reads_the_name(built: dict[str, Any]) -> None:
    source = inspect.getsource(make_persona)
    names = {n.attr for n in ast.walk(ast.parse(source)) if isinstance(n, ast.Attribute)}
    consts = {n.value for n in ast.walk(ast.parse(source)) if isinstance(n, ast.Constant)}
    assert "display_name" not in consts and "display_name" not in names
    import random

    staff = built["staff"]["stf_004"]
    a = make_persona(staff, random.Random("x"), 1)
    b = make_persona(dict(staff, display_name="Someone Else"), random.Random("x"), 1)
    assert a == b


def test_persona_override_wins() -> None:
    persona = make_persona({"staff_id": "stf_x", "is_student": False}, __import__("random").Random(1), 1)
    offer = {"start": "2026-11-03T07:00:00+08:00", "end": "2026-11-03T15:00:00+08:00"}
    reply = decide_reply(persona, offer, {"seed": 1, "personas": {"stf_x": {
        "will": "counter", "window": ["09:00", "15:00"]}}})
    assert reply["intent"] == "counter"
    assert reply["window"] == ["2026-11-03T09:00:00+08:00", "2026-11-03T15:00:00+08:00"]


# --------------------------------------------------------------------------- committed scenarios


def _scenarios(name: str) -> list[dict[str, Any]]:
    return [yaml.safe_load(p.read_text(encoding="utf-8"))
            for p in sorted(Path(f"evals/datasets/{name}").glob("*.yaml"))]


def test_scenario_counts_and_flags() -> None:
    golden, heldout = _scenarios("golden"), _scenarios("heldout")
    assert len(golden) == 60 and len(heldout) == 40
    for s in golden + heldout:
        assert s["synthetic"] is True
        assert "never hand-typed" in s["expect"]["computed_by"]
        assert s["expect"]["violations"] == 0


def test_s017_is_exactly_as_specified() -> None:
    s = yaml.safe_load(Path("evals/datasets/golden/S-017.yaml").read_text(encoding="utf-8"))
    assert {k: v for k, v in s.items() if k not in ("expect", "synthetic")} == S017
    assert s["expect"]["outcome"] == "filled"


def test_s017_cascade_hits_decline_counter_silence() -> None:
    data = load_data()
    res = run_covercall(dict(S017), data, RULES, CFG)
    intents = {o["staff_id"]: o["intent"] for o in res["offers"]}
    assert intents["stf_019"] == "decline"
    assert intents["stf_022"] == "counter"
    assert intents["stf_008"] == "silent"
    assert res["outcome"] == "filled" and res["violations"] == 0


def test_expect_blocks_reproduce() -> None:
    """Labels must come from the solver: recompute a sample and compare (§3.8 step 8)."""
    data = load_data()
    for s in [x for x in _scenarios("golden") if x["id"] in ("S-002", "S-017", "S-031", "S-050")]:
        res = run_covercall(s, data, RULES, CFG, time_limit_s=float(CFG["offline_time_limit_s"]))
        assert res["outcome"] == s["expect"]["outcome"]
        assert res["assignment"] == s["expect"]["assignment"]
        assert res["overtime_cost_cents"] == s["expect"]["overtime_cost_cents"]
