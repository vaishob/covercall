"""Unit, fixture, AST-isolation, determinism, and Hypothesis property tests for Slice 1 (§3.6, §3.7)."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

import pytest
import yaml
from hypothesis import given, settings
from hypothesis import strategies as st

from policy.compile_cpsat import (
     _evaluate_candidate_segment_cpsat,
    check_forced_assignment,
    load_company_config,
    load_rules,
    solve,
)
from policy.lint_rules import lint_rules_dir
from policy.validate import validate_assignment

ALLOWED_VALIDATOR_IMPORTS = {
    "__future__",
    "dataclasses",
    "datetime",
    "pathlib",
    "typing",
    "yaml",
}


def test_validate_ast_has_no_forbidden_imports() -> None:
    """§3.6: Parse validate.py's AST and fail on any forbidden import (ortools, compile_cpsat, etc.)."""
    source = Path("policy/validate.py").read_text(encoding="utf-8")
    tree = ast.parse(source, filename="policy/validate.py")
    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_modules.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported_modules.add(node.module.split(".")[0])

    forbidden = imported_modules - ALLOWED_VALIDATOR_IMPORTS
    assert not forbidden, f"Forbidden imports found in policy/validate.py: {forbidden}"
    assert "ortools" not in imported_modules
    assert "policy" not in imported_modules


def test_lint_rules_passes() -> None:
    """§3.4: Every rule spec has all required fields, complete source, >=2 tests, and no TODO-VERIFY."""
    errors = lint_rules_dir()
    assert errors == []


def _collect_rule_fixture_pairs() -> list[tuple[str, str, str]]:
    rules = load_rules()
    pairs: list[tuple[str, str, str]] = []
    for r in rules:
        rid = str(r["id"])
        for t in r.get("tests", []):
            pairs.append((rid, str(t["fixture"]), str(t["expect"])))
    return pairs


@pytest.mark.parametrize(("rule_id", "fixture_name", "expected_status"), _collect_rule_fixture_pairs())
def test_rule_fixtures_against_both_engines(
    rule_id: str, fixture_name: str, expected_status: str
) -> None:
    """§3.7: Every rule's fixtures run against BOTH validate.py and compile_cpsat.py and match expect."""
    rules = load_rules()
    cfg = load_company_config()
    rules_by_id = {r["id"]: r for r in rules}
    rule = rules_by_id[rule_id]

    fix_path = Path("policy/fixtures") / f"{fixture_name}.yaml"
    fix_data = yaml.safe_load(fix_path.read_text(encoding="utf-8"))

    # 1. Check independent plain-Python validator
    val_results = validate_assignment(fix_data, fix_data, rules)
    by_id = {res.rule_id: res for res in val_results}
    assert rule_id in by_id, f"Rule {rule_id} not evaluated by validator"
    assert by_id[rule_id].status == expected_status, (
        f"Validator mismatch on {rule_id} / {fixture_name}: "
        f"got {by_id[rule_id].status}, expected {expected_status}"
    )

    # 2. Check CP-SAT compiler on hard / data_gate rules
    if rule["kind"] in ("hard", "data_gate"):
        is_feasible_single_rule, _ = _evaluate_candidate_segment_cpsat(
            fix_data["employee"],
            fix_data["ledger"],
            fix_data["shift"],
            {
                "SG-EA4-COVERAGE": rules_by_id["SG-EA4-COVERAGE"],
                rule_id: rule,
            },
            cfg,
        )
        if expected_status == "violation":
            assert not is_feasible_single_rule, (
                f"CP-SAT compiler accepted {fixture_name} for hard rule {rule_id}"
            )
            # Also verify forced full model is infeasible
            assert not check_forced_assignment(fix_data, fix_data, rules, cfg)
        else:
            assert is_feasible_single_rule, (
                f"CP-SAT compiler rejected {fixture_name} for rule {rule_id} (expected {expected_status})"
            )


@st.composite
def random_assignment_strategy(draw: st.DrawFn) -> dict[str, Any]:
    contract_type = draw(st.sampled_from(["full_time", "part_time"]))
    emp_class = draw(st.sampled_from(["workman", "non_workman", "manager_executive"]))
    age = draw(st.integers(min_value=14, max_value=55))
    monthly_basic = draw(st.integers(min_value=1800, max_value=5000))
    hourly_basic = draw(st.floats(min_value=10.0, max_value=22.0, allow_nan=False, allow_infinity=False))
    skills = draw(
        st.lists(
            st.sampled_from(["barista", "kitchen", "cashier"]),
            min_size=1,
            max_size=3,
            unique=True,
        )
    )
    fsc_year = draw(st.sampled_from([None, "2018-04-10", "2023-06-15", "2025-02-01"]))
    keyholder = draw(st.booleans())
    ot_used = draw(st.integers(min_value=0, max_value=74))
    covers_14d = draw(st.integers(min_value=0, max_value=5))
    station = draw(st.sampled_from(["barista", "kitchen", "cashier"]))
    work_hours = float(draw(st.integers(min_value=4, max_value=10)))
    prior_hours = float(draw(st.sampled_from([0, 2, 4, 6])))
    breaks_min = draw(st.sampled_from([0, 15, 45, 60]))
    is_opening = draw(st.booleans())
    other_key = draw(st.booleans())
    prev_rest = float(draw(st.integers(min_value=6, max_value=20)))
    days_since_rest = draw(st.integers(min_value=1, max_value=15))

    return {
        "synthetic": True,
        "employee": {
            "staff_id": "stf_hyp",
            "display_name": "HypStaff",
            "age": age,
            "contract_type": contract_type,
            "employee_class": emp_class,
            "monthly_basic_sgd": monthly_basic if contract_type == "full_time" else None,
            "hourly_basic_sgd": round(hourly_basic, 2) if contract_type == "part_time" else None,
            "weekly_contract_hours": 44 if contract_type == "full_time" else 20,
            "normal_daily_hours": 8 if contract_type == "full_time" else 4,
            "skills": skills,
            "fsc_l1_passed_on": fsc_year,
            "keyholder": keyholder,
            "home_outlet": "bugis",
        },
        "ledger": {
            "ot_hours_used": ot_used,
            "rest_days": ["2026-11-01"],
            "cover_requests_14d": covers_14d,
        },
        "shift": {
            "outlet": "bugis",
            "station": station,
            "start": "2026-11-03T07:00:00+08:00",
            "end": f"2026-11-03T{7 + int(work_hours):02d}:00:00+08:00",
            "work_hours": work_hours,
            "hours_worked_today_before_shift": prior_hours,
            "breaks_min": breaks_min,
            "is_rest_day": False,
            "is_public_holiday": False,
            "is_extra_cover_shift": contract_type == "full_time",
            "is_opening_shift": is_opening,
            "other_keyholder_present": other_key,
            "hours_since_prev_shift_end": prev_rest,
            "hours_until_next_shift_start": 16.0,
            "days_since_last_rest_day": days_since_rest,
            "travel_min": 20,
        },
    }


@settings(derandomize=True, max_examples=80, deadline=None)
@given(case=random_assignment_strategy())
def test_property_dual_compilation_equivalence(case: dict[str, Any]) -> None:
    """§3.7 & §6.3 Property tests (Hypothesis, derandomized):
    (a) every solver assignment passes the validator;
    (b) every validator-rejected assignment, when forced into the solver model, is infeasible.
    """
    rules = load_rules()
    cfg = load_company_config()

    val_results = validate_assignment(case, case, rules)
    validator_rejected = any(
        r.status == "violation" and r.kind in ("hard", "data_gate") for r in val_results
    )
    forced_feasible = check_forced_assignment(case, case, rules, cfg)

    if validator_rejected:
        assert not forced_feasible, (
            f"Validator rejected assignment with {[r.rule_id for r in val_results if r.status == 'violation']}, "
            "but forced CP-SAT model was feasible!"
        )
    else:
        assert forced_feasible, "Validator accepted assignment, but CP-SAT model was infeasible!"
        # Also verify solve() returns the plan and passes validator without PlanDisagreement
        emp = dict(case["employee"])
        emp["ledger"] = case["ledger"]
        emp["shift_context"] = case["shift"]
        plan_res = solve(case["shift"], {"candidates": [emp], "now": "2026-11-03T06:02:00+08:00"}, rules, cfg)
        assert len(plan_res.candidates) == 1


def test_solver_determinism_across_three_runs() -> None:
    """§3.7 & §6.4: Same scenario and seed produces identical ranking across 3 runs."""
    rules = load_rules()
    cfg = load_company_config()
    candidates = [
        {
            "staff_id": f"stf_{i:03d}",
            "display_name": f"Staff_{i}",
            "age": 22 + i,
            "contract_type": "part_time" if i % 2 == 0 else "full_time",
            "employee_class": "non_workman",
            "monthly_basic_sgd": 2400 if i % 2 == 1 else None,
            "hourly_basic_sgd": 13.0 if i % 2 == 0 else None,
            "weekly_contract_hours": 20 if i % 2 == 0 else 44,
            "normal_daily_hours": 4 if i % 2 == 0 else 8,
            "skills": ["barista", "cashier"],
            "fsc_l1_passed_on": "2024-03-01",
            "keyholder": True,
            "home_outlet": "bugis" if i < 3 else "tampines",
            "ledger": {"ot_hours_used": 10 * i, "rest_days": ["2026-11-01"], "cover_requests_14d": i % 3},
        }
        for i in range(1, 7)
    ]
    gap = {"outlet": "bugis", "station": "barista", "start": "07:00", "end": "15:00", "absent": "stf_099"}
    ctx = {"candidates": candidates, "now": "2026-11-03T06:02:00+08:00", "seed": 17}

    runs = [solve(gap, ctx, rules, cfg).to_dict() for _ in range(3)]
    assert runs[0] == runs[1] == runs[2]
    assert len(runs[0]["candidates"]) == 3
