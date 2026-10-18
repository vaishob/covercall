"""Tests for synthetic data generation, CO-AGE-SCOPE gate, S-017 scenario, and baseline comparison (§3.8, §3.9)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from datagen import DataGateError, build_synthetic_dataset, validate_and_load_staff
from evals.compare import compare_dataset


def test_datagen_builds_all_synthetic_records_and_scenarios() -> None:
    summary = build_synthetic_dataset(seed=42)
    assert summary["outlets"] == 3
    assert summary["staff"] == 30
    assert summary["golden_scenarios"] == 60
    assert summary["heldout_scenarios"] == 40

    staff = json.loads(Path("data/staff.json").read_text(encoding="utf-8"))
    ledgers = json.loads(Path("data/ledgers.json").read_text(encoding="utf-8"))
    personas = json.loads(Path("data/sim_personas.json").read_text(encoding="utf-8"))

    # Every record carries synthetic: True and age >= 17
    for s in staff:
        assert s["synthetic"] is True
        assert s["age"] >= 17
        assert "part4_covered" not in s

    # 60/40 FT/PT ratio (18 FT, 12 PT) and exactly 1 manager_executive
    ft_count = sum(1 for s in staff if s["contract_type"] == "full_time")
    pt_count = sum(1 for s in staff if s["contract_type"] == "part_time")
    mgr_count = sum(1 for s in staff if s["employee_class"] == "manager_executive")
    assert ft_count == 18
    assert pt_count == 12
    assert mgr_count == 1

    # Deliberately includes one person at 70 of 72 OT hours and one at 11 days since last rest day
    assert any(led["ot_hours_used"] == 70 for led in ledgers.values())
    assert any(led["days_since_last_rest_day"] == 11 for led in ledgers.values())

    # Personas have style sampled independently of name
    assert len(personas) == 30
    for p in personas.values():
        assert p["synthetic"] is True
        assert "style_profile" in p


def test_co_age_scope_rejects_under_16() -> None:
    """§1.2 & §3.8: The data loader MUST reject any staff record under 16 (CO-AGE-SCOPE)."""
    underage_record = [
        {
            "staff_id": "stf_999",
            "display_name": "YoungStaff",
            "age": 15,
            "contract_type": "part_time",
            "employee_class": "non_workman",
            "hourly_basic_sgd": 11.0,
            "synthetic": True,
        }
    ]
    with pytest.raises(DataGateError, match="CO-AGE-SCOPE"):
        validate_and_load_staff(underage_record)


def test_s017_matches_canonical_spec() -> None:
    s017 = yaml.safe_load(Path("evals/datasets/golden/S-017.yaml").read_text(encoding="utf-8"))
    assert s017["id"] == "S-017"
    assert s017["now"] == "2026-11-03T06:02:00+08:00"
    assert s017["seed"] == 17
    assert s017["gap"] == {
        "outlet": "bugis",
        "station": "barista",
        "start": "07:00",
        "end": "15:00",
        "absent": "stf_011",
    }
    assert s017["expect"]["outcome"] == "filled"
    assert s017["expect"]["violations"] == 0


def test_compare_golden_and_heldout_zero_violations() -> None:
    golden_rep = compare_dataset("golden")
    assert golden_rep["covercall"]["rule_violations"] == 0
    assert golden_rep["covercall"]["solver_validator_disagreements"] == 0
    assert golden_rep["baseline"]["rule_violations"] > 0
    assert golden_rep["overtime_saved_sgd"]["total_saved_sgd"] > 0

    heldout_rep = compare_dataset("heldout")
    assert heldout_rep["covercall"]["rule_violations"] == 0
    assert heldout_rep["covercall"]["solver_validator_disagreements"] == 0
