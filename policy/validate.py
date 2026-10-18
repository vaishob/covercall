"""Independent plain-Python rule validator (§3.6, §6.3).

Re-implements every rule in ``policy/rules/*.yaml`` directly from the spec and the semantics in
``docs/decisions/0005-rule-semantics.md``, on plain dicts.

INVARIANT: this module imports only the standard library and ``yaml``. It MUST NOT import
``ortools``, ``policy.compile_cpsat`` or any shared rule logic. ``tests/test_policy.py`` parses
this file's AST and fails on any other import.
"""

from __future__ import annotations

import ast
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from fractions import Fraction
from pathlib import Path
from typing import Any

import yaml

VALIDATOR_VERSION = "2.0.0"
BLOCKING_KINDS = ("hard", "data_gate")


class ValidationDataError(ValueError):
    """Input data is missing or malformed. The validator fails closed instead of guessing."""


@dataclass(frozen=True)
class RuleResult:
    rule_id: str
    status: str  # ok | violation | not_applicable
    message: str
    source_url: str
    kind: str
    params: dict[str, Any] = field(default_factory=dict)
    cost: dict[str, int] = field(default_factory=dict)

    @property
    def blocking(self) -> bool:
        return self.status == "violation" and self.kind in BLOCKING_KINDS

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# --------------------------------------------------------------------------- loading


def load_rules(rules_dir: str | Path = "policy/rules") -> list[dict[str, Any]]:
    rules = []
    for path in sorted(Path(rules_dir).glob("*.yaml")):
        spec = yaml.safe_load(path.read_text(encoding="utf-8"))
        if isinstance(spec, dict):
            rules.append(spec)
    return rules


def load_company(path: str | Path = "policy/company.yaml") -> dict[str, Any]:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValidationDataError(f"{path} is not a mapping")
    return data


def resolve_params(rule: dict[str, Any], company: dict[str, Any]) -> dict[str, Any]:
    """Return the rule's params with every ``company:<dotted.key>`` reference resolved."""
    out: dict[str, Any] = {}
    for key, value in (rule.get("params") or {}).items():
        if isinstance(value, str) and value.startswith("company:"):
            node: Any = company
            for part in value.removeprefix("company:").split("."):
                if not isinstance(node, dict) or part not in node:
                    raise ValidationDataError(f"{rule['id']}: {value} not found in company.yaml")
                node = node[part]
            out[key] = node
        else:
            out[key] = value
    return out


# --------------------------------------------------------------------------- applies_when


_LITERALS = {"true": True, "false": False, "null": None}


def eval_applies_when(expr: str, env: dict[str, Any]) -> bool:
    """Evaluate a spec's ``applies_when`` over ``env`` with a whitelisted expression grammar."""
    tree = ast.parse(str(expr).strip(), mode="eval")
    return bool(_eval_node(tree.body, env))


def _eval_node(node: ast.AST, env: dict[str, Any]) -> Any:
    if isinstance(node, ast.BoolOp):
        values = [_eval_node(v, env) for v in node.values]
        return all(values) if isinstance(node.op, ast.And) else any(values)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return not _eval_node(node.operand, env)
    if isinstance(node, ast.Compare) and len(node.ops) == 1:
        left = _eval_node(node.left, env)
        right = _eval_node(node.comparators[0], env)
        op = node.ops[0]
        if isinstance(op, ast.Eq):
            return left == right
        if isinstance(op, ast.NotEq):
            return left != right
        if isinstance(op, ast.In):
            return left in right
        if isinstance(op, ast.NotIn):
            return left not in right
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, (ast.List, ast.Tuple)):
        return [_eval_node(e, env) for e in node.elts]
    if isinstance(node, ast.Name):
        if node.id in _LITERALS:
            return _LITERALS[node.id]
        if node.id in env:
            return env[node.id]
        raise ValidationDataError(f"applies_when: unknown name {node.id!r}")
    if isinstance(node, ast.Attribute):
        base = _eval_node(node.value, env)
        if not isinstance(base, dict) or node.attr not in base:
            raise ValidationDataError(f"applies_when: unknown field {node.attr!r}")
        return base[node.attr]
    raise ValidationDataError(f"applies_when: unsupported syntax {ast.dump(node)}")


# --------------------------------------------------------------------------- helpers


def _ts(value: Any) -> datetime:
    dt = datetime.fromisoformat(str(value))
    if dt.tzinfo is None:
        raise ValidationDataError(f"timestamp without offset: {value}")
    return dt


def _minutes(a: datetime, b: datetime) -> int:
    return int((b - a).total_seconds() // 60)


def _hours_text(minutes: int | Fraction) -> str:
    value = Fraction(minutes) / 60
    if value.denominator == 1:
        return str(value.numerator)
    return f"{float(value):.2f}".rstrip("0").rstrip(".")


def _round_cents(x: Fraction) -> int:
    # Half up, x >= 0.
    return int((x + Fraction(1, 2)) // 1)


def _sgd(cents: int) -> str:
    return f"{cents / 100:.2f}"


def _as_map(items: Any, key: str) -> dict[str, dict[str, Any]]:
    if isinstance(items, dict):
        return items
    return {str(item[key]): item for item in items or []}


def _require(record: dict[str, Any], name: str, what: str) -> Any:
    if record.get(name) is None:
        raise ValidationDataError(f"{what}: missing {name}")
    return record[name]


def monthly_basic_sgd(employee: dict[str, Any]) -> Fraction:
    if employee.get("monthly_basic_sgd") is not None:
        return Fraction(str(employee["monthly_basic_sgd"]))
    sid = employee.get("staff_id", "?")
    hourly = Fraction(str(_require(employee, "hourly_basic_sgd", f"staff {sid}")))
    weekly = Fraction(str(_require(employee, "weekly_contract_hours", f"staff {sid}")))
    return hourly * weekly * 52 / 12


def compute_part4_covered(employee: dict[str, Any], coverage_rule: dict[str, Any]) -> bool:
    """SG-EA4-COVERAGE. Computed from the spec's params, never stored on the record."""
    params = coverage_rule.get("params") or {}
    emp_class = _require(employee, "employee_class", f"staff {employee.get('staff_id')}")
    if emp_class in params["excluded_employee_classes"]:
        return False
    salary = monthly_basic_sgd(employee)
    if emp_class == "workman":
        return salary <= Fraction(str(params["workman_max_monthly_basic_sgd"]))
    return salary <= Fraction(str(params["non_workman_max_monthly_basic_sgd"]))


# --------------------------------------------------------------------------- facts


@dataclass
class _Facts:
    name: str
    employee: dict[str, Any]
    ledger: dict[str, Any]
    outlet: dict[str, Any]
    station: str
    start: datetime
    end: datetime
    day: date
    seg: int
    day_before: int
    week_before: int
    is_rest_day: bool
    is_opening: bool
    food_handling: bool
    open_time: str
    existing: list[dict[str, Any]]
    breaks: list[tuple[datetime, datetime]]
    compelled: bool


def _facts(assignment: dict[str, Any], context: dict[str, Any]) -> _Facts:
    staff = _as_map(context.get("staff"), "staff_id")
    outlets = _as_map(context.get("outlets"), "outlet_id")
    ledgers = _as_map(context.get("ledgers"), "ledger_id")
    gap = context.get("gap") or {}
    sid = str(_require(assignment, "staff_id", "assignment"))
    if sid not in staff:
        raise ValidationDataError(f"unknown staff {sid}")
    employee = staff[sid]
    outlet_id = str(_require(gap, "outlet", "gap"))
    if outlet_id not in outlets:
        raise ValidationDataError(f"unknown outlet {outlet_id}")
    outlet = outlets[outlet_id]
    station = str(_require(gap, "station", "gap"))
    start = _ts(_require(assignment, "start", "assignment"))
    end = _ts(_require(assignment, "end", "assignment"))
    if end <= start:
        raise ValidationDataError("assignment ends before it starts")
    day = start.date()

    ledger_id = f"{sid}_{day.strftime('%Y%m')}"
    if ledger_id not in ledgers:
        raise ValidationDataError(f"missing ledger {ledger_id}")
    ledger = ledgers[ledger_id]

    rest_days: set[date] = set()
    for led in ledgers.values():
        if led.get("staff_id") == sid:
            rest_days.update(date.fromisoformat(str(d)) for d in led.get("rest_days") or [])

    existing = [
        s for s in context.get("shifts") or []
        if s.get("staff_id") == sid and s.get("status", "scheduled") == "scheduled"
    ]
    day_before = 0
    week_before = 0
    monday = day - timedelta(days=day.weekday())
    for s in existing:
        s_start, s_end = _ts(s["start"]), _ts(s["end"])
        s_day = s_start.date()
        if s_day == day:
            day_before += _minutes(s_start, s_end)
        if monday <= s_day < monday + timedelta(days=7) and s_day not in rest_days:
            week_before += _minutes(s_start, s_end)

    stations = {st["station"]: st for st in outlet.get("stations") or []}
    if station not in stations:
        raise ValidationDataError(f"station {station} not at outlet {outlet_id}")
    open_time = str(_require(_require(outlet, "opening_hours", outlet_id), "open", outlet_id))
    open_dt = datetime.combine(day, datetime.strptime(open_time, "%H:%M").time(), start.tzinfo)

    breaks = []
    for b in assignment.get("breaks") or []:
        b_start = _ts(b["start"])
        breaks.append((b_start, b_start + timedelta(minutes=int(b["duration_min"]))))

    return _Facts(
        name=str(employee.get("display_name") or sid),
        employee=employee,
        ledger=ledger,
        outlet=outlet,
        station=station,
        start=start,
        end=end,
        day=day,
        seg=_minutes(start, end),
        day_before=day_before,
        week_before=week_before,
        is_rest_day=day in rest_days,
        is_opening=start == open_dt,
        food_handling=bool(stations[station].get("food_handling")),
        open_time=open_time,
        existing=existing,
        breaks=breaks,
        compelled=bool(assignment.get("compelled", False)),
    )


def _overtime_added(f: _Facts) -> int:
    nd = int(_require(f.employee, "normal_daily_hours", f.name)) * 60
    after = f.day_before + f.seg
    daily = max(0, after - nd) - max(0, f.day_before - nd)
    if f.is_rest_day or f.employee.get("contract_type") == "part_time":
        return daily
    wn = min(int(_require(f.employee, "weekly_contract_hours", f.name)), 44) * 60
    weekly = max(0, f.week_before + f.seg - wn) - max(0, f.week_before - wn)
    return min(f.seg, max(daily, weekly))


def _block_with_breaks(f: _Facts) -> tuple[datetime, datetime, list[tuple[datetime, datetime]]]:
    lo, hi = f.start, f.end
    breaks = list(f.breaks)
    merged: set[int] = set()
    changed = True
    while changed:
        changed = False
        for idx, s in enumerate(f.existing):
            if idx in merged:
                continue
            s_start, s_end = _ts(s["start"]), _ts(s["end"])
            if s_end == lo or s_start == hi:
                merged.add(idx)
                lo, hi = min(lo, s_start), max(hi, s_end)
                for b in s.get("breaks") or []:
                    b_start = _ts(b["start"])
                    breaks.append((b_start, b_start + timedelta(minutes=int(b["duration_min"]))))
                changed = True
    return lo, hi, breaks


def _work_dates(f: _Facts) -> set[date]:
    dates = {_ts(s["start"]).date() for s in f.existing}
    dates.add(f.day)
    return dates


# --------------------------------------------------------------------------- validation


def validate_assignment(
    assignment: dict[str, Any],
    context: dict[str, Any],
    rules: list[dict[str, Any]],
) -> list[RuleResult]:
    """Check one assignment against every rule. Returns one ``RuleResult`` per rule."""
    company = context.get("company")
    if not isinstance(company, dict):
        raise ValidationDataError("context.company (policy/company.yaml) is required")
    by_id = {r["id"]: r for r in rules}
    coverage_rule = by_id.get("SG-EA4-COVERAGE")
    if coverage_rule is None:
        raise ValidationDataError("SG-EA4-COVERAGE spec is required to compute part4_covered")

    f = _facts(assignment, context)
    part4 = compute_part4_covered(f.employee, coverage_rule)
    env = {
        "employee": {
            "part4_covered": part4,
            "contract_type": f.employee.get("contract_type"),
            "employee_class": f.employee.get("employee_class"),
            "monthly_rated": f.employee.get("monthly_basic_sgd") is not None,
        },
        "shift": {
            "station": f.station,
            "is_rest_day": f.is_rest_day,
            "is_opening": f.is_opening,
            "food_handling": f.food_handling,
        },
        "company": company,
    }

    results = []
    for rule in rules:
        params = resolve_params(rule, company)
        applies = eval_applies_when(rule.get("applies_when", "true"), env)
        checker = _CHECKERS.get(rule["id"])
        if checker is None:
            raise ValidationDataError(f"no validator implementation for {rule['id']}")
        if rule["id"] == "SG-EA4-COVERAGE":
            applies = part4
        if not applies:
            results.append(
                RuleResult(
                    rule_id=rule["id"],
                    status="not_applicable",
                    message=f"{f.name}: not applicable ({rule.get('applies_when')}).",
                    source_url=str(rule["source"]["url"]),
                    kind=str(rule["kind"]),
                )
            )
            continue
        violated, fill, cost = checker(f, params, context)
        # A breach template is only shown for a breach. Cost rules always explain their numbers.
        if violated or rule["kind"] == "cost":
            message = str(rule["message"]).format(name=f.name, **fill)
        else:
            message = f"{f.name}: {rule['title']}: ok."
        results.append(
            RuleResult(
                rule_id=rule["id"],
                status="violation" if violated else "ok",
                message=message,
                source_url=str(rule["source"]["url"]),
                kind=str(rule["kind"]),
                params=fill,
                cost=cost,
            )
        )
    return results


_Check = tuple[bool, dict[str, Any], dict[str, int]]


def _check_coverage(f: _Facts, p: dict[str, Any], ctx: dict[str, Any]) -> _Check:
    return False, {
        "coverage": "covered",
        "employee_class": f.employee.get("employee_class"),
        "monthly_basic_sgd": f"{float(monthly_basic_sgd(f.employee)):.2f}",
    }, {}


def _check_daily_max(f: _Facts, p: dict[str, Any], ctx: dict[str, Any]) -> _Check:
    after = f.day_before + f.seg
    limit = int(p["max_daily_hours"]) * 60
    return after > limit, {
        "day_hours": _hours_text(after),
        "date": f.day.isoformat(),
        "max_daily_hours": p["max_daily_hours"],
    }, {}


def _check_normal_hours(f: _Facts, p: dict[str, Any], ctx: dict[str, Any]) -> _Check:
    ot = _overtime_added(f)
    return False, {
        "ot_added": _hours_text(ot),
        "day_hours": _hours_text(f.day_before + f.seg),
        "normal_daily_hours": f.employee["normal_daily_hours"],
        "week_hours": _hours_text(f.week_before + (0 if f.is_rest_day else f.seg)),
        "normal_weekly_hours": min(int(f.employee["weekly_contract_hours"]),
                                   int(p["max_normal_weekly_hours"])),
    }, {}


def _check_breaks(f: _Facts, p: dict[str, Any], ctx: dict[str, Any]) -> _Check:
    lo, hi, breaks = _block_with_breaks(f)
    inside = sorted((max(b0, lo), min(b1, hi)) for b0, b1 in breaks if b1 > lo and b0 < hi)
    longest = 0
    total_break = 0
    cursor = lo
    for b0, b1 in inside:
        if b0 > cursor:
            longest = max(longest, _minutes(cursor, b0))
        if b1 > cursor:
            total_break += _minutes(max(cursor, b0), b1)
            cursor = b1
    longest = max(longest, _minutes(cursor, hi))
    block = _minutes(lo, hi)
    max_stretch = int(p["max_consecutive_hours_without_break"]) * 60
    violated = longest > max_stretch or (
        block > max_stretch and total_break < int(p["min_total_break_min"])
    )
    return violated, {
        "longest_stretch_h": _hours_text(longest),
        "break_min": total_break,
        "block_h": _hours_text(block),
        "max_consecutive_h": p["max_consecutive_hours_without_break"],
        "min_break_min": p["min_total_break_min"],
    }, {}


def _check_ot_cap(f: _Facts, p: dict[str, Any], ctx: dict[str, Any]) -> _Check:
    used = Fraction(str(_require(f.ledger, "ot_hours_used", f.ledger.get("ledger_id", "ledger"))))
    ot = _overtime_added(f)
    cap = Fraction(str(p["max_overtime_hours_per_month"]))
    return used * 60 + ot > cap * 60, {
        "ot_used": _hours_text(used * 60),
        "max": _hours_text(cap * 60),
        "ot_added": _hours_text(ot),
    }, {}


def _hourly_rate_cents(f: _Facts, p: dict[str, Any]) -> Fraction:
    monthly = Fraction(str(f.employee["monthly_basic_sgd"])) * 100
    rate = (int(p["hourly_rate_numerator_months"]) * monthly) / (
        int(p["hourly_rate_denominator_weeks"]) * int(p["hourly_rate_denominator_hours"])
    )
    if f.employee.get("employee_class") == "non_workman":
        rate = min(rate, Fraction(str(p["non_workman_hourly_rate_cap_sgd"])) * 100)
    return rate


def _check_ot_rate(f: _Facts, p: dict[str, Any], ctx: dict[str, Any]) -> _Check:
    ot = _overtime_added(f)
    rate = _hourly_rate_cents(f, p)
    cents = _round_cents(Fraction(ot, 60) * rate * Fraction(str(p["ot_multiplier"])))
    return False, {
        "ot_hours": _hours_text(ot),
        "hourly_rate": _sgd(_round_cents(rate)),
        "ot_cost_sgd": _sgd(cents),
    }, {"overtime_cents": cents}


def _check_rest_day(f: _Facts, p: dict[str, Any], ctx: dict[str, Any]) -> _Check:
    dates = _work_dates(f)
    run = 1
    d = f.day - timedelta(days=1)
    while d in dates:
        run += 1
        d -= timedelta(days=1)
    d = f.day + timedelta(days=1)
    while d in dates:
        run += 1
        d += timedelta(days=1)
    monday = f.day - timedelta(days=f.day.weekday())
    worked_in_week = sum(1 for i in range(7) if monday + timedelta(days=i) in dates)
    week_off = 7 - worked_in_week
    violated = (
        run > int(p["max_days_between_rest_days"])
        or week_off < int(p["min_rest_days_per_week"])
        or (f.compelled and not p["rest_day_work_may_be_compelled"])
    )
    return violated, {
        "date": f.day.isoformat(),
        "run_days": run,
        "max_days": p["max_days_between_rest_days"],
        "week_rest_days": week_off,
    }, {}


def _check_rest_day_pay(f: _Facts, p: dict[str, Any], ctx: dict[str, Any]) -> _Check:
    nd_hours = int(f.employee["normal_daily_hours"])
    worked = f.day_before + f.seg
    days = (
        int(p["days_pay_up_to_half_normal_day"])
        if worked * 2 <= nd_hours * 60
        else int(p["days_pay_more_than_half_normal_day"])
    )
    days_per_week = Fraction(int(f.employee["weekly_contract_hours"]), nd_hours)
    monthly = Fraction(str(f.employee["monthly_basic_sgd"])) * 100
    day_rate = 12 * monthly / (52 * days_per_week)
    cents = _round_cents(days * day_rate)
    return False, {
        "day_hours": _hours_text(worked),
        "days_pay": days,
        "rest_day_cost_sgd": _sgd(cents),
    }, {"rest_day_cents": cents}


def _check_pt_ot_rate(f: _Facts, p: dict[str, Any], ctx: dict[str, Any]) -> _Check:
    hourly = Fraction(str(_require(f.employee, "hourly_basic_sgd", f.name))) * 100
    ftn = int(p["comparable_full_timer_normal_daily_hours"]) * 60
    after = f.day_before + f.seg
    beyond = max(0, after - ftn) - max(0, f.day_before - ftn)
    within = f.seg - beyond
    base = _round_cents(Fraction(within, 60) * hourly
                        * Fraction(str(p["within_full_timer_normal_hours_multiplier"])))
    extra = _round_cents(Fraction(beyond, 60) * hourly
                         * Fraction(str(p["beyond_full_timer_normal_hours_multiplier"])))
    return False, {
        "seg_hours": _hours_text(f.seg),
        "hourly_basic": _sgd(_round_cents(hourly)),
        "beyond_ft_hours": _hours_text(beyond),
        "ft_normal_hours": p["comparable_full_timer_normal_daily_hours"],
        "pt_cost_sgd": _sgd(base + extra),
    }, {"base_cents": base, "overtime_cents": extra}


def _check_fsc(f: _Facts, p: dict[str, Any], ctx: dict[str, Any]) -> _Check:
    passed = f.employee.get("fsc_l1_passed_on")
    if not passed:
        return True, {"cert_status": "missing", "station": f.station}, {}
    passed_on = date.fromisoformat(str(passed)[:10])
    years = int(p["first_refresher_within_years"])
    try:
        valid_until = passed_on.replace(year=passed_on.year + years)
    except ValueError:  # 29 Feb
        valid_until = date(passed_on.year + years, 2, 28)
    if f.day > valid_until:
        return True, {"cert_status": f"lapsed (passed {passed_on.isoformat()})",
                      "station": f.station}, {}
    return False, {"cert_status": f"valid (passed {passed_on.isoformat()})",
                   "station": f.station}, {}


def _check_rest_between(f: _Facts, p: dict[str, Any], ctx: dict[str, Any]) -> _Check:
    min_rest = Fraction(str(p["min_rest_hours"])) * 60
    shortest: int | None = None
    for s in f.existing:
        s_start, s_end = _ts(s["start"]), _ts(s["end"])
        if s_start < f.end and s_end > f.start:
            shortest = 0 if shortest is None else min(shortest, 0)
            continue
        if s_end == f.start or s_start == f.end:
            continue
        gap = _minutes(s_end, f.start) if s_end <= f.start else _minutes(f.end, s_start)
        shortest = gap if shortest is None else min(shortest, gap)
    violated = shortest is not None and shortest < min_rest
    shown = shortest if shortest is not None else 0
    return violated, {"rest_hours": _hours_text(shown), "min_rest_hours": p["min_rest_hours"]}, {}


def _check_opener(f: _Facts, p: dict[str, Any], ctx: dict[str, Any]) -> _Check:
    fill = {"outlet": f.outlet.get("name") or f.outlet.get("outlet_id"), "open_time": f.open_time}
    if f.employee.get("keyholder"):
        return False, fill, {}
    staff = _as_map(ctx.get("staff"), "staff_id")
    gap = ctx.get("gap") or {}
    absent = gap.get("absent_staff_id")
    sid = f.employee.get("staff_id")
    present = 0
    for s in ctx.get("shifts") or []:
        other = s.get("staff_id")
        if other in (sid, absent) or s.get("status", "scheduled") != "scheduled":
            continue
        if s.get("outlet") != gap.get("outlet") or not staff.get(other, {}).get("keyholder"):
            continue
        if _ts(s["start"]) <= f.start < _ts(s["end"]):
            present += 1
    return present < int(p["min_keyholders_at_opening"]), fill, {}


def _check_skill(f: _Facts, p: dict[str, Any], ctx: dict[str, Any]) -> _Check:
    skills = list(f.employee.get("skills") or [])
    return f.station not in skills, {"station": f.station,
                                     "skills": ", ".join(skills) or "none"}, {}


def _check_fairness(f: _Facts, p: dict[str, Any], ctx: dict[str, Any]) -> _Check:
    covers = int(_require(f.ledger, "cover_requests_14d", f.ledger.get("ledger_id", "ledger")))
    request_number = covers + 1
    excess = max(0, request_number - int(p["max_covers"]))
    return excess > 0, {
        "cover_requests_14d": covers,
        "window_days": p["window_days"],
        "request_number": request_number,
        "max_covers": p["max_covers"],
        "penalty_units": excess,
    }, {}


def _check_age(f: _Facts, p: dict[str, Any], ctx: dict[str, Any]) -> _Check:
    age = f.employee.get("age")
    return age is None or int(age) < int(p["min_age"]), {"age": age, "min_age": p["min_age"]}, {}


_CHECKERS = {
    "SG-EA4-COVERAGE": _check_coverage,
    "SG-EA4-DAILY-MAX-12H": _check_daily_max,
    "SG-EA4-NORMAL-HOURS": _check_normal_hours,
    "SG-EA4-BREAKS": _check_breaks,
    "SG-EA4-OT-CAP-72": _check_ot_cap,
    "SG-EA4-OT-RATE": _check_ot_rate,
    "SG-EA4-REST-DAY": _check_rest_day,
    "SG-EA4-REST-DAY-PAY": _check_rest_day_pay,
    "SG-PT-OT-RATE": _check_pt_ot_rate,
    "SG-SFA-FSC-L1": _check_fsc,
    "CO-REST-BETWEEN-SHIFTS": _check_rest_between,
    "CO-OPENER-KEYHOLDER": _check_opener,
    "CO-STATION-SKILL": _check_skill,
    "CO-FAIRNESS": _check_fairness,
    "CO-AGE-SCOPE": _check_age,
}


def blocking_violations(results: list[RuleResult]) -> list[RuleResult]:
    return [r for r in results if r.blocking]


def cost_breakdown(results: list[RuleResult]) -> dict[str, int]:
    out = {"base_cents": 0, "overtime_cents": 0, "rest_day_cents": 0}
    for r in results:
        for key, cents in r.cost.items():
            out[key] += cents
    out["total_cents"] = out["base_cents"] + out["overtime_cents"] + out["rest_day_cents"]
    return out


def check_staff_age(employee: dict[str, Any], rules: list[dict[str, Any]],
                    company: dict[str, Any]) -> RuleResult:
    """CO-AGE-SCOPE as a data-load gate (no assignment needed)."""
    rule = next(r for r in rules if r["id"] == "CO-AGE-SCOPE")
    params = resolve_params(rule, company)
    age = employee.get("age")
    violated = age is None or int(age) < int(params["min_age"])
    fill = {"age": age, "min_age": params["min_age"]}
    name = str(employee.get("display_name") or employee.get("staff_id"))
    return RuleResult(
        rule_id=rule["id"],
        status="violation" if violated else "ok",
        message=str(rule["message"]).format(name=name, **fill),
        source_url=str(rule["source"]["url"]),
        kind=str(rule["kind"]),
        params=fill,
    )
