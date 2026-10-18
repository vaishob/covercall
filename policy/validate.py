"""Independent plain-Python rule validator (§3.6, §6.3).

CRITICAL ARCHITECTURAL INVARIANT:
This module MUST NOT import `ortools`, `policy.compile_cpsat`, or any shared rule logic.
Only Python stdlib and `yaml` are permitted. An AST test in `tests/test_policy.py`
verifies this invariant on every test run.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class RuleResult:
    rule_id: str
    status: str  # "ok" | "violation" | "not_applicable"
    message: str
    source_url: str
    kind: str = "hard"
    cost_cents: int = 0
    params_filled: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_rules_for_validator(rules_dir: Path = Path("policy/rules")) -> list[dict[str, Any]]:
    rules: list[dict[str, Any]] = []
    for path in sorted(rules_dir.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            rules.append(data)
    return rules


def compute_part4_covered(employee: dict[str, Any], coverage_rule: dict[str, Any] | None = None) -> bool:
    """Compute EA Part 4 coverage from SG-EA4-COVERAGE (§6.2, §8.1). Never stored by hand."""
    emp_class = str(employee.get("employee_class", "non_workman"))
    params = (coverage_rule or {}).get("params", {})
    excluded_classes = set(params.get("exclude_employee_classes", ["manager_executive"]))
    if emp_class in excluded_classes:
        return False

    workman_cap = float(params.get("workman_basic_salary_cap_sgd", 4500))
    non_workman_cap = float(params.get("non_workman_basic_salary_cap_sgd", 2600))

    monthly_basic = employee.get("monthly_basic_sgd")
    if monthly_basic is None:
        hourly = float(employee.get("hourly_basic_sgd") or 0.0)
        # Equivalent full-time monthly basic salary for coverage check
        monthly_basic = (hourly * 44.0 * 52.0) / 12.0
    else:
        monthly_basic = float(monthly_basic)

    if emp_class == "workman":
        return monthly_basic <= workman_cap
    return monthly_basic <= non_workman_cap


def _parse_date(val: Any) -> date | None:
    if not val:
        return None
    s = str(val)
    if "T" in s:
        return datetime.fromisoformat(s).date()
    return date.fromisoformat(s[:10])


def _monthly_hourly_rate_sgd(employee: dict[str, Any], cap_non_workman: bool = True) -> float:
    """Monthly-rated hourly basic rate = (12 * monthly_basic) / (52 * 44)."""
    if employee.get("contract_type") == "part_time" and employee.get("hourly_basic_sgd") is not None:
        rate = float(employee["hourly_basic_sgd"])
    else:
        monthly = float(employee.get("monthly_basic_sgd") or 0.0)
        rate = (12.0 * monthly) / (52.0 * 44.0)
    if cap_non_workman and employee.get("employee_class") == "non_workman":
        return min(rate, 13.60)
    return rate


def _daily_salary_sgd(employee: dict[str, Any]) -> float:
    if employee.get("contract_type") == "part_time":
        hourly = float(employee.get("hourly_basic_sgd") or 0.0)
        normal_day = float(employee.get("normal_daily_hours") or 4.0)
        return hourly * normal_day
    monthly = float(employee.get("monthly_basic_sgd") or 0.0)
    return (12.0 * monthly) / (52.0 * 5.5)


def compute_ot_added_hours(employee: dict[str, Any], shift: dict[str, Any]) -> float:
    """Compute overtime hours added by this shift assignment."""
    work_hours = float(shift.get("work_hours", 8.0))
    prior_today = float(shift.get("hours_worked_today_before_shift", 0.0))
    normal_day = float(employee.get("normal_daily_hours", 8.0))
    if employee.get("contract_type") == "part_time":
        normal_day = 8.0  # Comparable full-timer normal daily hours (§6.2 SG-PT-OT-RATE)

    is_rest_or_ph = bool(shift.get("is_rest_day", False) or shift.get("is_public_holiday", False))
    total_today = prior_today + work_hours
    if is_rest_or_ph:
        # Rest-day and public-holiday work counts toward monthly OT cap only beyond normal daily hours
        before_ot = max(0.0, prior_today - normal_day)
        after_ot = max(0.0, total_today - normal_day)
        return max(0.0, after_ot - before_ot)

    # If the shift is an extra cover shift beyond their contractual schedule, or extends beyond normal_day:
    is_extra_day = bool(shift.get("is_extra_cover_shift", False))
    if is_extra_day:
        return work_hours
    before_ot = max(0.0, prior_today - normal_day)
    after_ot = max(0.0, total_today - normal_day)
    return max(0.0, after_ot - before_ot)


def validate_assignment(
    assignment: dict[str, Any],
    context: dict[str, Any],
    rules: list[dict[str, Any]],
) -> list[RuleResult]:
    """Validate an assignment dictionary against all loaded YAML rules.

    `assignment` contains `employee`, `shift`, and optionally `ledger` (or looked up from `context`).
    """
    employee = dict(assignment.get("employee") or context.get("employee") or {})
    shift = dict(assignment.get("shift") or context.get("shift") or {})
    ledger = dict(assignment.get("ledger") or context.get("ledger") or {})

    rules_by_id = {r["id"]: r for r in rules if isinstance(r, dict) and "id" in r}
    cov_rule = rules_by_id.get("SG-EA4-COVERAGE")
    part4_covered = compute_part4_covered(employee, cov_rule)
    employee["part4_covered"] = part4_covered

    name = str(employee.get("display_name") or employee.get("staff_id") or "Staff")
    work_hours = float(shift.get("work_hours", 8.0))
    prior_today = float(shift.get("hours_worked_today_before_shift", 0.0))
    daily_hours = prior_today + work_hours
    normal_daily_hours = float(employee.get("normal_daily_hours", 8.0))
    ot_used = float(ledger.get("ot_hours_used", 0.0))
    ot_added = compute_ot_added_hours(employee, shift)
    station = str(shift.get("station", "barista"))
    outlet = str(shift.get("outlet", "bugis"))

    results: list[RuleResult] = []

    for rule in rules:
        rid = str(rule["id"])
        kind = str(rule.get("kind", "hard"))
        source_url = str(rule.get("source", {}).get("url", ""))
        params = rule.get("params") or {}
        template = str(rule.get("message", ""))

        if rid == "SG-EA4-COVERAGE":
            status = "ok" if part4_covered else "not_applicable"
            filled = {
                "name": name,
                "part4_status": "covered" if part4_covered else "not covered",
                "employee_class": employee.get("employee_class", "non_workman"),
                "monthly_basic_sgd": employee.get("monthly_basic_sgd") or employee.get("hourly_basic_sgd") or 0,
            }
            results.append(
                RuleResult(
                    rule_id=rid,
                    status=status,
                    message=template.format(**filled),
                    source_url=source_url,
                    kind=kind,
                    params_filled=filled,
                )
            )

        elif rid == "SG-EA4-OT-CAP-72":
            max_ot = float(params.get("max_overtime_hours_per_month", 72))
            ot_used_disp = int(ot_used) if ot_used.is_integer() else round(ot_used, 1)
            ot_added_disp = int(ot_added) if ot_added.is_integer() else round(ot_added, 1)
            max_disp = int(max_ot) if max_ot.is_integer() else max_ot
            filled = {
                "name": name,
                "ot_used": ot_used_disp,
                "max": max_disp,
                "ot_added": ot_added_disp,
            }
            if not part4_covered:
                status = "not_applicable"
            elif (ot_used + ot_added) > max_ot:
                status = "violation"
            else:
                status = "ok"
            results.append(
                RuleResult(
                    rule_id=rid,
                    status=status,
                    message=template.format(**filled),
                    source_url=source_url,
                    kind=kind,
                    params_filled=filled,
                )
            )

        elif rid == "SG-EA4-DAILY-MAX-12H":
            max_daily = float(params.get("max_daily_hours", 12))
            d_disp = int(daily_hours) if daily_hours.is_integer() else round(daily_hours, 1)
            m_disp = int(max_daily) if max_daily.is_integer() else max_daily
            filled = {"name": name, "daily_hours": d_disp, "max_daily_hours": m_disp}
            if not part4_covered:
                status = "not_applicable"
            elif daily_hours > max_daily:
                status = "violation"
            else:
                status = "ok"
            results.append(
                RuleResult(
                    rule_id=rid,
                    status=status,
                    message=template.format(**filled),
                    source_url=source_url,
                    kind=kind,
                    params_filled=filled,
                )
            )

        elif rid == "SG-EA4-NORMAL-HOURS":
            filled = {
                "name": name,
                "work_hours": int(work_hours) if work_hours.is_integer() else round(work_hours, 1),
                "normal_daily_hours": int(normal_daily_hours)
                if normal_daily_hours.is_integer()
                else normal_daily_hours,
                "ot_added": int(ot_added) if ot_added.is_integer() else round(ot_added, 1),
            }
            status = "ok" if part4_covered else "not_applicable"
            results.append(
                RuleResult(
                    rule_id=rid,
                    status=status,
                    message=template.format(**filled),
                    source_url=source_url,
                    kind=kind,
                    params_filled=filled,
                )
            )

        elif rid == "SG-EA4-OT-RATE":
            is_ft = employee.get("contract_type") == "full_time"
            hourly_rate = _monthly_hourly_rate_sgd(employee, cap_non_workman=True)
            mult = float(params.get("ot_multiplier", 1.5))
            # If rest day, rest-day pay rule handles the base rest-day salary; OT beyond normal day is in rest-day or here
            is_rest = bool(shift.get("is_rest_day", False))
            ot_h = ot_added if not is_rest else 0.0
            cost_cents = int(round(ot_h * hourly_rate * mult * 100)) if (part4_covered and is_ft) else 0
            filled = {
                "name": name,
                "ot_hours": int(ot_h) if ot_h.is_integer() else round(ot_h, 1),
                "hourly_rate": f"{hourly_rate:.2f}",
                "ot_cost_sgd": f"{cost_cents / 100.0:.2f}",
            }
            status = "ok" if (part4_covered and is_ft) else "not_applicable"
            results.append(
                RuleResult(
                    rule_id=rid,
                    status=status,
                    message=template.format(**filled),
                    source_url=source_url,
                    kind=kind,
                    cost_cents=cost_cents,
                    params_filled=filled,
                )
            )

        elif rid == "SG-EA4-REST-DAY":
            max_days = int(params.get("max_days_between_rest_days", 12))
            days_since = int(shift.get("days_since_last_rest_day", 2))
            compelled = bool(shift.get("compelled_rest_day_work", False))
            filled = {"name": name, "days_since_rest": days_since, "max_days": max_days}
            if not part4_covered:
                status = "not_applicable"
            elif days_since > max_days or compelled:
                status = "violation"
            else:
                status = "ok"
            results.append(
                RuleResult(
                    rule_id=rid,
                    status=status,
                    message=template.format(**filled),
                    source_url=source_url,
                    kind=kind,
                    params_filled=filled,
                )
            )

        elif rid == "SG-EA4-REST-DAY-PAY":
            is_rest = bool(shift.get("is_rest_day", False))
            if not (part4_covered and is_rest):
                filled = {
                    "name": name,
                    "work_hours": int(work_hours) if work_hours.is_integer() else work_hours,
                    "days_pay": 0,
                    "rest_day_cost_sgd": "0.00",
                }
                results.append(
                    RuleResult(
                        rule_id=rid,
                        status="not_applicable",
                        message=template.format(**filled),
                        source_url=source_url,
                        kind=kind,
                        cost_cents=0,
                        params_filled=filled,
                    )
                )
            else:
                day_sal = _daily_salary_sgd(employee)
                hourly_rate = _monthly_hourly_rate_sgd(employee, cap_non_workman=True)
                if work_hours <= (normal_daily_hours / 2.0):
                    days_pay = 1
                    extra_ot_h = 0.0
                elif work_hours <= normal_daily_hours:
                    days_pay = 2
                    extra_ot_h = 0.0
                else:
                    days_pay = 2
                    extra_ot_h = work_hours - normal_daily_hours
                total_sgd = (days_pay * day_sal) + (extra_ot_h * hourly_rate * 1.5)
                cost_cents = int(round(total_sgd * 100))
                filled = {
                    "name": name,
                    "work_hours": int(work_hours) if work_hours.is_integer() else work_hours,
                    "days_pay": days_pay,
                    "rest_day_cost_sgd": f"{cost_cents / 100.0:.2f}",
                }
                results.append(
                    RuleResult(
                        rule_id=rid,
                        status="ok",
                        message=template.format(**filled),
                        source_url=source_url,
                        kind=kind,
                        cost_cents=cost_cents,
                        params_filled=filled,
                    )
                )

        elif rid == "SG-PT-OT-RATE":
            is_pt = employee.get("contract_type") == "part_time"
            ft_normal = float(params.get("comparable_full_timer_normal_daily_hours", 8.0))
            hourly_basic = float(employee.get("hourly_basic_sgd") or 12.0)
            if not is_pt:
                filled = {
                    "name": name,
                    "work_hours": int(work_hours) if work_hours.is_integer() else work_hours,
                    "hourly_basic_sgd": f"{hourly_basic:.2f}",
                    "pt_cost_sgd": "0.00",
                    "ot_hours": 0,
                    "ft_normal": int(ft_normal),
                }
                results.append(
                    RuleResult(
                        rule_id=rid,
                        status="not_applicable",
                        message=template.format(**filled),
                        source_url=source_url,
                        kind=kind,
                        cost_cents=0,
                        params_filled=filled,
                    )
                )
            else:
                total_today = prior_today + work_hours
                before_ot = max(0.0, prior_today - ft_normal)
                after_ot = max(0.0, total_today - ft_normal)
                pt_ot_h = max(0.0, after_ot - before_ot)
                reg_h = max(0.0, work_hours - pt_ot_h)
                # Incremental labour cost: base part-time hours + 1.5x beyond FT normal hours
                # Note: overtime premium component is 0.5x on pt_ot_h, total shift wage is reg_h*1.0 + pt_ot_h*1.5
                total_pt_sgd = (reg_h * hourly_basic * 1.0) + (pt_ot_h * hourly_basic * 1.5)
                cost_cents = int(round(total_pt_sgd * 100))
                filled = {
                    "name": name,
                    "work_hours": int(work_hours) if work_hours.is_integer() else work_hours,
                    "hourly_basic_sgd": f"{hourly_basic:.2f}",
                    "pt_cost_sgd": f"{cost_cents / 100.0:.2f}",
                    "ot_hours": int(pt_ot_h) if pt_ot_h.is_integer() else round(pt_ot_h, 1),
                    "ft_normal": int(ft_normal),
                }
                results.append(
                    RuleResult(
                        rule_id=rid,
                        status="ok",
                        message=template.format(**filled),
                        source_url=source_url,
                        kind=kind,
                        cost_cents=cost_cents,
                        params_filled=filled,
                    )
                )

        elif rid == "SG-EA4-BREAKS":
            min_break = int(params.get("min_meal_break_min_for_8h_continuous", 45))
            max_consec = float(params.get("max_consecutive_hours_without_break", 6.0))
            breaks_min = int(shift.get("breaks_min", 45))
            filled = {
                "name": name,
                "work_hours": int(work_hours) if work_hours.is_integer() else work_hours,
                "breaks_min": breaks_min,
                "min_break_min": min_break,
            }
            if not part4_covered:
                status = "not_applicable"
            elif (work_hours >= 8.0 and breaks_min < min_break) or (
                work_hours > max_consec and breaks_min <= 0
            ):
                status = "violation"
            else:
                status = "ok"
            results.append(
                RuleResult(
                    rule_id=rid,
                    status=status,
                    message=template.format(**filled),
                    source_url=source_url,
                    kind=kind,
                    params_filled=filled,
                )
            )

        elif rid == "SG-SFA-FSC-L1":
            req_stations = set(params.get("stations_requiring_fsc", ["kitchen", "barista"]))
            refresher_years = int(params.get("fsc_l1_refresher_years", 5))
            if station not in req_stations:
                filled = {"name": name, "cert_status": "not required", "station": station}
                results.append(
                    RuleResult(
                        rule_id=rid,
                        status="not_applicable",
                        message=template.format(**filled),
                        source_url=source_url,
                        kind=kind,
                        params_filled=filled,
                    )
                )
            else:
                passed_date = _parse_date(employee.get("fsc_l1_passed_on"))
                shift_date = _parse_date(shift.get("start")) or date(2026, 11, 3)
                if passed_date is None:
                    status = "violation"
                    cert_status = "missing"
                else:
                    # Valid for up to 5 years from passing date
                    try:
                        expiry_date = date(
                            passed_date.year + refresher_years,
                            passed_date.month,
                            passed_date.day,
                        )
                    except ValueError:
                        expiry_date = date(passed_date.year + refresher_years, 2, 28)
                    if shift_date > expiry_date:
                        status = "violation"
                        cert_status = f"lapsed (passed {passed_date.isoformat()})"
                    else:
                        status = "ok"
                        cert_status = f"valid (passed {passed_date.isoformat()})"
                filled = {"name": name, "cert_status": cert_status, "station": station}
                results.append(
                    RuleResult(
                        rule_id=rid,
                        status=status,
                        message=template.format(**filled),
                        source_url=source_url,
                        kind=kind,
                        params_filled=filled,
                    )
                )

        elif rid == "CO-REST-BETWEEN-SHIFTS":
            min_rest = float(params.get("min_rest_hours_between_shifts", 11.0))
            prev_h = float(shift.get("hours_since_prev_shift_end", 24.0))
            next_h = float(shift.get("hours_until_next_shift_start", 24.0))
            actual_rest = min(prev_h, next_h)
            r_disp = int(actual_rest) if actual_rest.is_integer() else round(actual_rest, 1)
            m_disp = int(min_rest) if min_rest.is_integer() else min_rest
            filled = {"name": name, "rest_hours": r_disp, "min_rest_hours": m_disp}
            status = "violation" if actual_rest < min_rest else "ok"
            results.append(
                RuleResult(
                    rule_id=rid,
                    status=status,
                    message=template.format(**filled),
                    source_url=source_url,
                    kind=kind,
                    params_filled=filled,
                )
            )

        elif rid == "CO-OPENER-KEYHOLDER":
            is_opening = bool(shift.get("is_opening_shift", False))
            has_key = bool(employee.get("keyholder", False))
            other_key = bool(shift.get("other_keyholder_present", False))
            filled = {"name": name, "outlet": outlet}
            if not is_opening:
                status = "not_applicable"
            elif not (has_key or other_key):
                status = "violation"
            else:
                status = "ok"
            results.append(
                RuleResult(
                    rule_id=rid,
                    status=status,
                    message=template.format(**filled),
                    source_url=source_url,
                    kind=kind,
                    params_filled=filled,
                )
            )

        elif rid == "CO-STATION-SKILL":
            skills = list(employee.get("skills") or [])
            filled = {"name": name, "station": station, "skills": ", ".join(skills) or "none"}
            status = "ok" if station in skills else "violation"
            results.append(
                RuleResult(
                    rule_id=rid,
                    status=status,
                    message=template.format(**filled),
                    source_url=source_url,
                    kind=kind,
                    params_filled=filled,
                )
            )

        elif rid == "CO-FAIRNESS":
            max_covers = int(params.get("max_covers_14d", 2))
            covers = int(ledger.get("cover_requests_14d", 0))
            filled = {"name": name, "cover_requests_14d": covers, "max_covers_14d": max_covers}
            status = "violation" if covers > max_covers else "ok"
            results.append(
                RuleResult(
                    rule_id=rid,
                    status=status,
                    message=template.format(**filled),
                    source_url=source_url,
                    kind=kind,
                    params_filled=filled,
                )
            )

        elif rid == "CO-AGE-SCOPE":
            min_age = int(params.get("min_allowed_age", 16))
            age = int(employee.get("age", 18))
            filled = {"name": name, "age": age, "min_allowed_age": min_age}
            status = "violation" if age < min_age else "ok"
            results.append(
                RuleResult(
                    rule_id=rid,
                    status=status,
                    message=template.format(**filled),
                    source_url=source_url,
                    kind=kind,
                    params_filled=filled,
                )
            )

    return results
