"""Slice 1 policy tests: lint, validator isolation, fixtures on both engines, property tests,
determinism (§3.4, §3.6, §3.7, §6.3)."""

from __future__ import annotations

import ast
import shutil
from pathlib import Path
from typing import Any

import pytest
import yaml
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from policy.compile_cpsat import (
    PlanDisagreement,
    check_forced,
    compiled_cost,
    compiled_rule_ids_failing,
    load_company_config,
    load_rules,
    solve,
)
from policy.lint_rules import lint_rules_dir
from policy.validate import blocking_violations, cost_breakdown, validate_assignment
from tests.fixture_context import load_fixture

RULES = load_rules()
COMPANY = load_company_config()
BY_ID = {r["id"]: r for r in RULES}
STDLIB_ALLOWED = {"__future__", "ast", "dataclasses", "datetime", "fractions", "pathlib", "typing"}


# --------------------------------------------------------------------------- isolation and lint


def test_validator_imports_only_stdlib_and_yaml() -> None:
    tree = ast.parse(Path("policy/validate.py").read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add((node.module or "").split(".")[0])
            assert node.level == 0, "relative imports are forbidden in validate.py"
    assert "ortools" not in imported
    assert "policy" not in imported
    assert imported <= STDLIB_ALLOWED | {"yaml"}, imported - STDLIB_ALLOWED - {"yaml"}


def test_lint_passes_on_repo_rules() -> None:
    assert lint_rules_dir() == []


def test_lint_fails_without_source(tmp_path: Path) -> None:
    rules = tmp_path / "rules"
    shutil.copytree("policy/rules", rules)
    spec = yaml.safe_load((rules / "SG-EA4-OT-CAP-72.yaml").read_text(encoding="utf-8"))
    del spec["source"]["url"]
    (rules / "SG-EA4-OT-CAP-72.yaml").write_text(yaml.safe_dump(spec), encoding="utf-8")
    errors = lint_rules_dir(rules, Path("policy/fixtures"))
    assert any("source.url" in e for e in errors)


def test_lint_fails_on_todo_verify(tmp_path: Path) -> None:
    rules = tmp_path / "rules"
    shutil.copytree("policy/rules", rules)
    spec = yaml.safe_load((rules / "SG-PT-OT-RATE.yaml").read_text(encoding="utf-8"))
    spec["source"]["url"] = "TODO-VERIFY"
    (rules / "SG-PT-OT-RATE.yaml").write_text(yaml.safe_dump(spec), encoding="utf-8")
    assert any("TODO-VERIFY" in e for e in lint_rules_dir(rules, Path("policy/fixtures")))


# --------------------------------------------------------------------------- fixtures, both engines


def _cases() -> list[tuple[str, str, str]]:
    return [(r["id"], t["fixture"], t["expect"]) for r in RULES for t in r["tests"]]


@pytest.mark.parametrize(("rule_id", "fixture", "expect"), _cases())
def test_rule_fixture_on_both_engines(rule_id: str, fixture: str, expect: str) -> None:
    assignment, context = load_fixture(fixture, COMPANY)
    results = {r.rule_id: r for r in validate_assignment(assignment, context, RULES)}
    assert results[rule_id].status == expect, results[rule_id].message

    # The compiler sees only the coverage gate plus the rule under test.
    subset = [BY_ID["SG-EA4-COVERAGE"]] + ([BY_ID[rule_id]] if rule_id != "SG-EA4-COVERAGE" else [])
    feasible = check_forced(assignment, context, subset, COMPANY)
    if BY_ID[rule_id]["kind"] in ("hard", "data_gate"):
        assert feasible == (expect != "violation")
    else:
        assert feasible


def test_ot_cap_message_uses_computed_numbers() -> None:
    assignment, context = load_fixture("ot_cap_70_plus_3", COMPANY)
    res = {r.rule_id: r for r in validate_assignment(assignment, context, RULES)}
    assert res["SG-EA4-OT-CAP-72"].message == (
        "Test Lead-Barista: 70 of 72 overtime hours used this month. This shift adds 3. "
        "Breaches the EA Part 4 monthly cap."
    )


def test_ok_results_never_show_breach_text() -> None:
    assignment, context = load_fixture("ot_cap_69_plus_3", COMPANY)
    for r in validate_assignment(assignment, context, RULES):
        if r.status != "violation":
            assert "Breaches" not in r.message


@pytest.mark.parametrize("fixture", ["ot_rate_ft_covered", "rest_day_pay_full_shift",
                                     "pt_ot_rate_part_timer", "normal_hours_within_contract"])
def test_costs_match_between_engines(fixture: str) -> None:
    assignment, context = load_fixture(fixture, COMPANY)
    v_cost = cost_breakdown(validate_assignment(assignment, context, RULES))
    assert compiled_cost(assignment, context, RULES, COMPANY) == v_cost


def test_known_costs() -> None:
    # 8 h OT at 1.5 x (12 x 2400) / (52 x 44) = S$151.05; rest day 2 x (12 x 2400)/(52 x 5) = S$221.54
    a, c = load_fixture("ot_rate_ft_covered", COMPANY)
    assert cost_breakdown(validate_assignment(a, c, RULES))["overtime_cents"] == 15105
    a, c = load_fixture("rest_day_pay_full_shift", COMPANY)
    assert cost_breakdown(validate_assignment(a, c, RULES))["rest_day_cents"] == 22154
    a, c = load_fixture("pt_ot_rate_part_timer", COMPANY)
    assert cost_breakdown(validate_assignment(a, c, RULES))["total_cents"] == 9600


# --------------------------------------------------------------------------- property tests


DAYS = ["2026-11-02", "2026-11-03", "2026-11-04", "2026-11-05", "2026-11-06", "2026-11-07",
        "2026-11-08"]


@st.composite
def roster_case(draw: st.DrawFn) -> tuple[dict[str, Any], dict[str, Any]]:
    """A random person, a random week of shifts, and a random cover segment on Saturday."""
    part_time = draw(st.booleans())
    emp_class = draw(st.sampled_from(["workman", "non_workman", "manager_executive"]))
    employee = {
        "staff_id": "stf_h", "display_name": "Hyp", "age": draw(st.integers(14, 60)),
        "home_outlet": "bugis", "contract_type": "part_time" if part_time else "full_time",
        "employee_class": emp_class,
        "monthly_basic_sgd": None if part_time else draw(st.sampled_from([1800, 2400, 2600, 2601, 4500, 4800])),
        "hourly_basic_sgd": draw(st.sampled_from([10.5, 12.0, 14.25])) if part_time else None,
        "weekly_contract_hours": draw(st.sampled_from([16, 24, 30])) if part_time else 40,
        "normal_daily_hours": 8,
        "skills": draw(st.lists(st.sampled_from(["barista", "kitchen", "cashier"]), min_size=1,
                                max_size=3, unique=True)),
        "fsc_l1_passed_on": draw(st.sampled_from([None, "2019-04-15", "2021-11-07", "2024-03-15"])),
        "keyholder": draw(st.booleans()), "synthetic": True,
    }
    shifts = []
    for day in DAYS:
        kind = draw(st.sampled_from(["off", "off", "am", "pm", "late", "short"]))
        span = {"am": ("07:00", "15:00"), "pm": ("13:00", "21:00"), "late": ("15:00", "23:00"),
                "short": ("07:00", "11:00")}.get(kind)
        if span:
            shifts.append({"staff_id": "stf_h", "outlet": "bugis", "station": "cashier",
                           "start": f"{day}T{span[0]}:00+08:00", "end": f"{day}T{span[1]}:00+08:00",
                           "breaks": [], "status": "scheduled", "synthetic": True})
    if draw(st.booleans()):
        shifts.append({"staff_id": "stf_k", "outlet": "bugis", "station": "cashier",
                       "start": "2026-11-07T07:00:00+08:00", "end": "2026-11-07T15:00:00+08:00",
                       "breaks": [], "status": "scheduled", "synthetic": True})
    start_h = draw(st.sampled_from([7, 8, 11, 15]))
    length_h = draw(st.sampled_from([2, 3, 4, 6, 7, 8, 9, 12]))
    end_h = min(start_h + length_h, 23)
    with_break = draw(st.booleans())
    station = draw(st.sampled_from(["barista", "kitchen", "cashier"]))
    assignment = {
        "staff_id": "stf_h",
        "start": f"2026-11-07T{start_h:02d}:00:00+08:00",
        "end": f"2026-11-07T{end_h:02d}:00:00+08:00",
        "breaks": ([{"start": f"2026-11-07T{start_h + (end_h - start_h) // 2:02d}:00:00+08:00",
                     "duration_min": 45}] if with_break and end_h - start_h > 1 else []),
        "compelled": draw(st.booleans()) and draw(st.booleans()),
    }
    rest_days = draw(st.lists(st.sampled_from(DAYS), max_size=2, unique=True))
    keyholder_other = {"staff_id": "stf_k", "display_name": "K", "age": 30, "home_outlet": "bugis",
                       "contract_type": "full_time", "employee_class": "non_workman",
                       "monthly_basic_sgd": 2300, "weekly_contract_hours": 40, "normal_daily_hours": 8,
                       "skills": ["cashier"], "keyholder": True, "synthetic": True}
    context = {
        "now": "2026-11-07T05:00:00+08:00",
        "gap": {"outlet": "bugis", "station": station, "start": assignment["start"],
                "end": assignment["end"], "absent_staff_id": "stf_a"},
        "staff": {"stf_h": employee, "stf_k": keyholder_other},
        "shifts": shifts,
        "ledgers": {
            "stf_h_202611": {"ledger_id": "stf_h_202611", "staff_id": "stf_h",
                             "ot_hours_used": draw(st.integers(0, 75)), "rest_days": rest_days,
                             "cover_requests_14d": draw(st.integers(0, 4)), "synthetic": True},
            "stf_k_202611": {"ledger_id": "stf_k_202611", "staff_id": "stf_k", "ot_hours_used": 0,
                             "rest_days": [], "cover_requests_14d": 0, "synthetic": True},
        },
        "outlets": yaml.safe_load(Path("policy/fixtures/_base.yaml").read_text(encoding="utf-8"))
        ["outlets"],
        "travel": {"stf_h": {"bugis": 15}, "stf_k": {"bugis": 15}},
        "company": COMPANY,
    }
    context["outlets"] = {o["outlet_id"]: o for o in context["outlets"]}
    return assignment, context


@settings(derandomize=True, max_examples=300, deadline=None,
          suppress_health_check=[HealthCheck.too_slow])
@given(case=roster_case())
def test_property_engines_agree_on_every_rule(case: tuple[dict[str, Any], dict[str, Any]]) -> None:
    """(b) every validator-rejected assignment is infeasible when forced into the solver model,
    and the converse; the failing rule IDs and the cost lines must also match exactly."""
    assignment, context = case
    results = validate_assignment(assignment, context, RULES)
    v_fail = sorted({r.rule_id for r in blocking_violations(results)})
    assert compiled_rule_ids_failing(assignment, context, RULES, COMPANY) == v_fail
    assert check_forced(assignment, context, RULES, COMPANY) == (not v_fail)
    if not assignment.get("compelled"):
        cost = compiled_cost(dict(assignment, breaks=None), context, RULES, COMPANY)
        assert cost == cost_breakdown(results)


@settings(derandomize=True, max_examples=60, deadline=None,
          suppress_health_check=[HealthCheck.too_slow])
@given(case=roster_case())
def test_property_every_solver_plan_passes_validator(
    case: tuple[dict[str, Any], dict[str, Any]],
) -> None:
    """(a) every assignment the solver returns passes the validator (solve() raises otherwise)."""
    assignment, context = case
    context = dict(context, now="2026-11-07T00:00:00+08:00")
    try:
        result = solve(context["gap"], context, RULES, COMPANY)
    except PlanDisagreement as exc:  # pragma: no cover - this is the failure being tested for
        pytest.fail(f"P0 solver/validator disagreement: {exc.details}")
    for plan in result.candidates:
        for seg in plan["segments"]:
            assert not blocking_violations(validate_assignment(seg, context, RULES))


# --------------------------------------------------------------------------- determinism


def _demo_context() -> dict[str, Any]:
    _, context = load_fixture("ot_rate_ft_covered", COMPANY)
    base = context["staff"]["stf_t"]
    for i in range(1, 7):
        sid = f"stf_{i:03d}"
        context["staff"][sid] = dict(base, staff_id=sid, display_name=f"Staff {i}",
                                     keyholder=i % 2 == 0)
        context["ledgers"][f"{sid}_202611"] = {
            "ledger_id": f"{sid}_202611", "staff_id": sid, "ot_hours_used": 10 * i,
            "rest_days": ["2026-11-08"], "cover_requests_14d": i % 3, "synthetic": True}
        context["travel"][sid] = {"bugis": 10 + 3 * i}
        for d in range(2, 2 + (i % 5) + 1):
            context["shifts"].append({"staff_id": sid, "outlet": "bugis", "station": "barista",
                                      "start": f"2026-11-0{d}T07:00:00+08:00",
                                      "end": f"2026-11-0{d}T15:00:00+08:00", "breaks": [],
                                      "status": "scheduled", "synthetic": True})
    return context


def test_same_scenario_same_seed_same_ranking_three_runs() -> None:
    context = _demo_context()
    runs = [solve(context["gap"], dict(context, seed=17), RULES, COMPANY).to_dict()
            for _ in range(3)]
    assert runs[0] == runs[1] == runs[2]
    assert len(runs[0]["candidates"]) == COMPANY["top_k_plans"]
    people = [tuple(p["staff_ids"]) for p in runs[0]["candidates"]]
    assert len(set(people)) == len(people), "top-k plans must use distinct people"
    objectives = [p["objective"] for p in runs[0]["candidates"]]
    assert objectives == sorted(objectives)


def test_counter_offer_window_produces_split_plan() -> None:
    context = _demo_context()
    keep = {"stf_001", "stf_002"}
    context["staff"] = {k: v for k, v in context["staff"].items() if k in keep | {"stf_k"}}
    context["windows"] = {"stf_002": ["2026-11-07T09:00:00+08:00", "2026-11-07T15:00:00+08:00"]}
    context["excluded"] = ["stf_k", "stf_t"]
    # stf_001 (a key-holder, 40 h week, 70 OT hours used) can legally add 2 h but not 8 h.
    context["staff"]["stf_001"]["keyholder"] = True
    context["ledgers"]["stf_001_202611"]["ot_hours_used"] = 70
    context["shifts"] = [s for s in context["shifts"] if s["staff_id"] != "stf_001"] + [
        {"staff_id": "stf_001", "outlet": "bugis", "station": "barista",
         "start": f"2026-11-0{d}T07:00:00+08:00", "end": f"2026-11-0{d}T15:00:00+08:00",
         "breaks": [], "status": "scheduled", "synthetic": True} for d in range(2, 7)]
    plan = solve(context["gap"], context, RULES, COMPANY).candidates[0]
    assert [(s["staff_id"], s["start"][11:16], s["end"][11:16]) for s in plan["segments"]] == [
        ("stf_001", "07:00", "09:00"), ("stf_002", "09:00", "15:00")]
