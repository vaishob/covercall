"""OR-Tools CP-SAT compiler and solver for coverage plans (§3.5, §6.3, §6.4).

The rule specs in ``policy/rules/*.yaml`` are compiled into constraints over boolean decision
variables ``x[staff, option]`` ("this person works this segment of the gap"). An option is the
full gap or one half of a split at a grid point, so a counter-offer such as "can do 9 not 7" can be
combined with another person (at most ``max_segments`` segments). Every hard rule becomes a named
linear constraint ``coef * x <= bound``; cost rules become integer-cent objective terms.

Facts are derived here, in minute integers, from the raw roster dicts. This file shares no code
with ``policy/validate.py``. The two meet only in ``solve``, which checks every ranked plan with the
validator and raises ``PlanDisagreement`` (P0, ``plan.disagreement`` -> HELD) on any difference in
legality or cost. Semantics: docs/decisions/0005-rule-semantics.md. Formulation:
docs/decisions/0006-solver-formulation.md.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from fractions import Fraction
from pathlib import Path
from typing import Any

import yaml
from ortools.sat.python import cp_model

from policy.validate import (
    VALIDATOR_VERSION,
    blocking_violations,
    cost_breakdown,
    validate_assignment,
)

COMPILER_VERSION = "2.0.0"


class PlanDisagreement(RuntimeError):
    """The solver and the independent validator disagree. P0: the gap goes to HELD."""

    def __init__(self, message: str, details: list[dict[str, Any]]):
        super().__init__(message)
        self.details = details


class SolverDataError(ValueError):
    """Input data is missing or malformed. The solver fails closed instead of guessing."""


# --------------------------------------------------------------------------- loading


def load_rules(rules_dir: str | Path = "policy/rules") -> list[dict[str, Any]]:
    out = []
    for path in sorted(Path(rules_dir).glob("*.yaml")):
        spec = yaml.safe_load(path.read_text(encoding="utf-8"))
        if isinstance(spec, dict):
            out.append(spec)
    return out


def load_company_config(path: str | Path = "policy/company.yaml") -> dict[str, Any]:
    cfg = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(cfg, dict):
        raise SolverDataError(f"{path} is not a mapping")
    return cfg


def _params(rule: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    resolved = {}
    for key, value in (rule.get("params") or {}).items():
        if isinstance(value, str) and value.startswith("company:"):
            node: Any = cfg
            for part in value[len("company:"):].split("."):
                try:
                    node = node[part]
                except (KeyError, TypeError) as exc:
                    raise SolverDataError(f"{rule['id']}: {value} missing in company.yaml") from exc
            resolved[key] = node
        else:
            resolved[key] = value
    return resolved


# --------------------------------------------------------------------------- applies_when
# A small recursive-descent parser, written separately from the validator's evaluator.

_TOKEN = re.compile(r'\s*(==|!=|\(|\)|\[|\]|,|"[^"]*"|\'[^\']*\'|-?\d+(?:\.\d+)?|[A-Za-z_][\w.]*)')


class _Cond:
    def __init__(self, text: str, env: dict[str, Any]):
        self.tokens: list[str] = []
        pos = 0
        text = str(text).strip()
        while pos < len(text):
            m = _TOKEN.match(text, pos)
            if not m or m.end() == pos:
                raise SolverDataError(f"applies_when: cannot parse {text!r} at {pos}")
            self.tokens.append(m.group(1))
            pos = m.end()
        self.i = 0
        self.env = env

    def value(self) -> bool:
        result = self._or()
        if self.i != len(self.tokens):
            raise SolverDataError(f"applies_when: trailing tokens {self.tokens[self.i:]}")
        return bool(result)

    def _peek(self) -> str | None:
        return self.tokens[self.i] if self.i < len(self.tokens) else None

    def _take(self) -> str:
        tok = self.tokens[self.i]
        self.i += 1
        return tok

    def _or(self) -> Any:
        left = self._and()
        while self._peek() == "or":
            self._take()
            right = self._and()
            left = bool(left) or bool(right)
        return left

    def _and(self) -> Any:
        left = self._not()
        while self._peek() == "and":
            self._take()
            right = self._not()
            left = bool(left) and bool(right)
        return left

    def _not(self) -> Any:
        if self._peek() == "not":
            self._take()
            return not self._not()
        return self._cmp()

    def _cmp(self) -> Any:
        left = self._atom()
        op = self._peek()
        if op in ("==", "!="):
            self._take()
            right = self._atom()
            return (left == right) if op == "==" else (left != right)
        if op == "in":
            self._take()
            return left in self._atom()
        return left

    def _atom(self) -> Any:
        tok = self._take()
        if tok == "(":
            inner = self._or()
            self._take()  # ")"
            return inner
        if tok == "[":
            items = []
            while self._peek() != "]":
                items.append(self._atom())
                if self._peek() == ",":
                    self._take()
            self._take()
            return items
        if tok[0] in "\"'":
            return tok[1:-1]
        if tok in ("true", "false"):
            return tok == "true"
        if re.fullmatch(r"-?\d+(?:\.\d+)?", tok):
            return float(tok) if "." in tok else int(tok)
        node: Any = self.env
        for part in tok.split("."):
            if not isinstance(node, dict) or part not in node:
                raise SolverDataError(f"applies_when: unknown name {tok}")
            node = node[part]
        return node


# --------------------------------------------------------------------------- time helpers

_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def _mins(iso: str) -> int:
    dt = datetime.fromisoformat(str(iso))
    if dt.tzinfo is None:
        raise SolverDataError(f"timestamp without offset: {iso}")
    return int((dt - _EPOCH).total_seconds()) // 60


def _local_date(iso: str) -> date:
    return datetime.fromisoformat(str(iso)).date()


def _iso(minutes: int, tz: Any) -> str:
    return (_EPOCH + timedelta(minutes=minutes)).astimezone(tz).isoformat()


def _cents(x: Fraction) -> int:
    return int((x + Fraction(1, 2)) // 1)


def _index(items: Any, key: str) -> dict[str, dict[str, Any]]:
    if isinstance(items, dict):
        return items
    return {str(item[key]): item for item in items or []}


# --------------------------------------------------------------------------- data classes


@dataclass(frozen=True)
class Option:
    """One way to staff part of the gap: the full gap, or one side of a split at ``split``."""

    idx: int
    role: str  # full | first | second
    start: int  # epoch minutes
    end: int
    split: int | None


@dataclass
class OptionFacts:
    """Compiler-side facts for one (person, option) pair, in minutes and cents."""

    applies: dict[str, bool]
    constraints: list[tuple[str, int, int]]  # (rule_id, coef, bound): coef * x <= bound
    cost: dict[str, int]
    fairness_units: int
    breaks: list[tuple[int, int]]


@dataclass
class VarIndex:
    options: list[Option] = field(default_factory=list)
    x: dict[tuple[str, int], cp_model.IntVar] = field(default_factory=dict)
    used: dict[str, cp_model.IntVar] = field(default_factory=dict)
    split_vars: dict[int, cp_model.IntVar] = field(default_factory=dict)
    facts: dict[tuple[str, int], OptionFacts] = field(default_factory=dict)
    pool: list[str] = field(default_factory=list)
    tz: Any = None


@dataclass
class PlanResult:
    candidates: list[dict[str, Any]]
    rejected_candidates: list[dict[str, Any]]
    solver_params: dict[str, Any]
    validator_version: str = VALIDATOR_VERSION
    compiler_version: str = COMPILER_VERSION
    synthetic: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidates": self.candidates,
            "rejected_candidates": self.rejected_candidates,
            "solver_params": self.solver_params,
            "validator_version": self.validator_version,
            "compiler_version": self.compiler_version,
            "synthetic": self.synthetic,
        }


# --------------------------------------------------------------------------- facts


class _Roster:
    """Per-person view of the roster: shifts as (start, end, local date, breaks) in minutes."""

    def __init__(self, context: dict[str, Any]):
        self.by_staff: dict[str, list[tuple[int, int, date, list[tuple[int, int]]]]] = {}
        self.at_outlet: list[tuple[str, str, int, int]] = []
        for s in context.get("shifts") or []:
            if s.get("status", "scheduled") != "scheduled":
                continue
            start, end = _mins(s["start"]), _mins(s["end"])
            brk = [(_mins(b["start"]), _mins(b["start"]) + int(b["duration_min"]))
                   for b in s.get("breaks") or []]
            self.by_staff.setdefault(str(s["staff_id"]), []).append(
                (start, end, _local_date(s["start"]), brk)
            )
            self.at_outlet.append((str(s["outlet"]), str(s["staff_id"]), start, end))
        self.rest_days: dict[str, set[date]] = {}
        for led in _index(context.get("ledgers"), "ledger_id").values():
            days = {date.fromisoformat(str(d)) for d in led.get("rest_days") or []}
            self.rest_days.setdefault(str(led["staff_id"]), set()).update(days)


def _monthly_basic(emp: dict[str, Any]) -> Fraction:
    if emp.get("monthly_basic_sgd") is not None:
        return Fraction(str(emp["monthly_basic_sgd"]))
    if emp.get("hourly_basic_sgd") is None or emp.get("weekly_contract_hours") is None:
        raise SolverDataError(f"staff {emp.get('staff_id')}: no salary data")
    return Fraction(str(emp["hourly_basic_sgd"])) * int(emp["weekly_contract_hours"]) * 52 / 12


def _covered(emp: dict[str, Any], cov: dict[str, Any]) -> bool:
    cls = emp.get("employee_class")
    if cls is None:
        raise SolverDataError(f"staff {emp.get('staff_id')}: no employee_class")
    if cls in cov["excluded_employee_classes"]:
        return False
    cap = cov["workman_max_monthly_basic_sgd"] if cls == "workman" \
        else cov["non_workman_max_monthly_basic_sgd"]
    return _monthly_basic(emp) <= Fraction(str(cap))


def planned_breaks(start: int, end: int, cfg: dict[str, Any]) -> list[tuple[int, int]]:
    """Planner choice (decision 0005): one meal break mid-segment when longer than 6 h."""
    length = end - start
    if length <= 6 * 60:
        return []
    begin = start + (length // 2) // 15 * 15
    return [(begin, begin + int(cfg["meal_break_min"]))]


def _option_facts(
    sid: str,
    opt: Option,
    ctx: dict[str, Any],
    roster: _Roster,
    rules: list[dict[str, Any]],
    cfg: dict[str, Any],
    compelled: bool = False,
    breaks: list[tuple[int, int]] | None = None,
) -> OptionFacts:
    staff = _index(ctx.get("staff"), "staff_id")
    outlets = _index(ctx.get("outlets"), "outlet_id")
    ledgers = _index(ctx.get("ledgers"), "ledger_id")
    gap = ctx["gap"]
    emp = staff[sid]
    outlet = outlets.get(str(gap["outlet"]))
    if outlet is None:
        raise SolverDataError(f"unknown outlet {gap['outlet']}")
    tz = datetime.fromisoformat(str(gap["start"])).tzinfo
    day = (_EPOCH + timedelta(minutes=opt.start)).astimezone(tz).date()
    ledger = ledgers.get(f"{sid}_{day.year:04d}{day.month:02d}")
    if ledger is None:
        raise SolverDataError(f"missing ledger {sid}_{day.year:04d}{day.month:02d}")
    mine = roster.by_staff.get(sid, [])
    rests = roster.rest_days.get(sid, set())

    seg = opt.end - opt.start
    before = sum(e - s for s, e, d, _ in mine if d == day)
    after = before + seg
    week0 = day - timedelta(days=day.weekday())
    week_before = sum(e - s for s, e, d, _ in mine
                      if week0 <= d <= week0 + timedelta(days=6) and d not in rests)
    rest_day = day in rests
    nd = int(emp["normal_daily_hours"]) * 60

    def excess(total: int, limit: int) -> int:
        return total - limit if total > limit else 0

    ot = excess(after, nd) - excess(before, nd)
    if not rest_day and emp.get("contract_type") != "part_time":
        wn = min(int(emp["weekly_contract_hours"]), 44) * 60
        weekly = excess(week_before + seg, wn) - excess(week_before, wn)
        ot = min(seg, max(ot, weekly))

    stations = {st["station"]: st for st in outlet["stations"]}
    station = str(gap["station"])
    open_hhmm = str(outlet["opening_hours"]["open"])
    open_dt = datetime.combine(day, datetime.strptime(open_hhmm, "%H:%M").time(), tz)
    opening = opt.start == int((open_dt - _EPOCH).total_seconds()) // 60

    rules_by_id = {r["id"]: r for r in rules}
    covered = _covered(emp, _params(rules_by_id["SG-EA4-COVERAGE"], cfg))
    env = {
        "employee": {
            "part4_covered": covered,
            "contract_type": emp.get("contract_type"),
            "employee_class": emp.get("employee_class"),
            "monthly_rated": emp.get("monthly_basic_sgd") is not None,
        },
        "shift": {
            "station": station,
            "is_rest_day": rest_day,
            "is_opening": opening,
            "food_handling": bool(stations[station].get("food_handling")),
        },
        "company": cfg,
    }

    seg_breaks = planned_breaks(opt.start, opt.end, cfg) if breaks is None else breaks
    applies: dict[str, bool] = {}
    cons: list[tuple[str, int, int]] = []
    cost = {"base_cents": 0, "overtime_cents": 0, "rest_day_cents": 0}
    fairness_units = 0

    for rule in rules:
        rid = rule["id"]
        on = covered if rid == "SG-EA4-COVERAGE" else _Cond(rule["applies_when"], env).value()
        applies[rid] = on
        if not on:
            continue
        p = _params(rule, cfg)
        if rid == "SG-EA4-DAILY-MAX-12H":
            cons.append((rid, after, int(p["max_daily_hours"]) * 60))
        elif rid == "SG-EA4-OT-CAP-72":
            used = Fraction(str(ledger["ot_hours_used"])) * 60
            if used.denominator != 1:
                raise SolverDataError(f"{sid}: ot_hours_used is not a whole number of minutes")
            # (used + added) * x <= cap, all in minutes. Exactly 72 h is allowed.
            cons.append((rid, int(used) + ot, int(p["max_overtime_hours_per_month"]) * 60))
        elif rid == "SG-EA4-BREAKS":
            cons.extend(_breaks_constraints(rid, opt, mine, seg_breaks, p))
        elif rid == "SG-EA4-REST-DAY":
            worked = {d for _, _, d, _ in mine} | {day}
            run, d = 1, day - timedelta(days=1)
            while d in worked:
                run, d = run + 1, d - timedelta(days=1)
            d = day + timedelta(days=1)
            while d in worked:
                run, d = run + 1, d + timedelta(days=1)
            off = sum(1 for i in range(7) if week0 + timedelta(days=i) not in worked)
            cons.append((rid, run, int(p["max_days_between_rest_days"])))
            cons.append((rid, int(p["min_rest_days_per_week"]) - off, 0))
            if not p["rest_day_work_may_be_compelled"]:
                cons.append((rid, 1 if compelled else 0, 0))
        elif rid == "SG-SFA-FSC-L1":
            passed = emp.get("fsc_l1_passed_on")
            bad = 1
            if passed:
                p_on = date.fromisoformat(str(passed)[:10])
                yrs = int(p["first_refresher_within_years"])
                limit = date(p_on.year + yrs, p_on.month, 28 if (p_on.month, p_on.day) == (2, 29)
                             else p_on.day)
                bad = 1 if day > limit else 0
            cons.append((rid, bad, 0))
        elif rid == "CO-REST-BETWEEN-SHIFTS":
            need = int(Fraction(str(p["min_rest_hours"])) * 60)
            for s, e, _, _ in mine:
                if s < opt.end and e > opt.start:
                    cons.append((rid, 1, 0))  # double-booked
                elif e == opt.start or s == opt.end:
                    continue  # touching shifts form one block
                else:
                    rest = opt.start - e if e <= opt.start else s - opt.end
                    cons.append((rid, need - rest, 0))
        elif rid == "CO-OPENER-KEYHOLDER":
            holders = 1 if emp.get("keyholder") else 0
            absent = gap.get("absent_staff_id")
            for o_id, other, s, e in roster.at_outlet:
                if o_id == gap["outlet"] and other not in (sid, absent) \
                        and staff.get(other, {}).get("keyholder") and s <= opt.start < e:
                    holders += 1
            cons.append((rid, int(p["min_keyholders_at_opening"]) - holders, 0))
        elif rid == "CO-STATION-SKILL":
            cons.append((rid, 0 if station in (emp.get("skills") or []) else 1, 0))
        elif rid == "CO-AGE-SCOPE":
            age = emp.get("age")
            cons.append((rid, 1 if age is None or int(age) < int(p["min_age"]) else 0, 0))
        elif rid == "CO-FAIRNESS":
            fairness_units = max(0, int(ledger["cover_requests_14d"]) + 1 - int(p["max_covers"]))
        elif rid == "SG-EA4-OT-RATE":
            rate = Fraction(int(p["hourly_rate_numerator_months"])) * _monthly_basic(emp) * 100 / (
                int(p["hourly_rate_denominator_weeks"]) * int(p["hourly_rate_denominator_hours"]))
            if emp.get("employee_class") == "non_workman":
                rate = min(rate, Fraction(str(p["non_workman_hourly_rate_cap_sgd"])) * 100)
            cost["overtime_cents"] += _cents(rate * ot / 60 * Fraction(str(p["ot_multiplier"])))
        elif rid == "SG-EA4-REST-DAY-PAY":
            n_days = (int(p["days_pay_up_to_half_normal_day"]) if 2 * after <= nd
                      else int(p["days_pay_more_than_half_normal_day"]))
            per_week = Fraction(int(emp["weekly_contract_hours"]), int(emp["normal_daily_hours"]))
            day_rate = Fraction(12) * _monthly_basic(emp) * 100 / (52 * per_week)
            cost["rest_day_cents"] += _cents(n_days * day_rate)
        elif rid == "SG-PT-OT-RATE":
            hourly = Fraction(str(emp["hourly_basic_sgd"])) * 100
            ft = int(p["comparable_full_timer_normal_daily_hours"]) * 60
            beyond = excess(after, ft) - excess(before, ft)
            cost["base_cents"] += _cents(hourly * (seg - beyond) / 60
                                         * Fraction(str(p["within_full_timer_normal_hours_multiplier"])))
            cost["overtime_cents"] += _cents(hourly * beyond / 60
                                             * Fraction(str(p["beyond_full_timer_normal_hours_multiplier"])))
    cost["total_cents"] = cost["base_cents"] + cost["overtime_cents"] + cost["rest_day_cents"]
    return OptionFacts(applies, cons, cost, fairness_units, seg_breaks)


def _breaks_constraints(
    rid: str,
    opt: Option,
    mine: list[tuple[int, int, date, list[tuple[int, int]]]],
    seg_breaks: list[tuple[int, int]],
    p: dict[str, Any],
) -> list[tuple[str, int, int]]:
    lo, hi = opt.start, opt.end
    pauses = list(seg_breaks)
    joined: set[int] = set()
    grew = True
    while grew:
        grew = False
        for i, (s, e, _, brk) in enumerate(mine):
            if i not in joined and (e == lo or s == hi):
                joined.add(i)
                lo, hi = min(lo, s), max(hi, e)
                pauses.extend(brk)
                grew = True
    # Walk the block minute ranges: work = block minus pauses.
    clipped = sorted((max(a, lo), min(b, hi)) for a, b in pauses if b > lo and a < hi)
    longest, paused, t = 0, 0, lo
    for a, b in clipped:
        longest = max(longest, a - t) if a > t else longest
        if b > t:
            paused += b - max(t, a)
            t = b
    longest = max(longest, hi - t)
    limit = int(p["max_consecutive_hours_without_break"]) * 60
    out = [(rid, longest, limit)]
    if hi - lo > limit:
        out.append((rid, int(p["min_total_break_min"]) - paused, 0))
    return out


# --------------------------------------------------------------------------- model


def _pool(context: dict[str, Any]) -> list[str]:
    staff = _index(context.get("staff"), "staff_id")
    gap = context["gap"]
    excluded = set(context.get("excluded") or [])
    excluded.add(str(gap.get("absent_staff_id")))
    return sorted(
        sid for sid, rec in staff.items()
        if sid not in excluded and rec.get("employee_class") != "manager_executive"
    )


def _options(gap: dict[str, Any], cfg: dict[str, Any]) -> list[Option]:
    s, e = _mins(gap["start"]), _mins(gap["end"])
    opts = [Option(0, "full", s, e, None)]
    if int(cfg["max_segments"]) >= 2:
        step = int(cfg["split_granularity_min"])
        shortest = int(cfg["min_segment_min"])
        t = s + step
        while t < e:
            if t - s >= shortest and e - t >= shortest:
                opts.append(Option(len(opts), "first", s, t, t))
                opts.append(Option(len(opts), "second", t, e, t))
            t += step
    return opts


def _travel(context: dict[str, Any], sid: str, outlet: str) -> int:
    try:
        return int(context["travel"][sid][outlet])
    except (KeyError, TypeError) as exc:
        raise SolverDataError(f"no travel time for {sid} -> {outlet}") from exc


def build_model(
    gap: dict[str, Any],
    candidates: list[str],
    context: dict[str, Any],
    rules: list[dict[str, Any]],
    cfg: dict[str, Any],
) -> tuple[cp_model.CpModel, VarIndex]:
    """Compile the specs into a CP-SAT model over the candidate pool."""
    ctx = dict(context, gap=gap)
    model = cp_model.CpModel()
    vi = VarIndex(options=_options(gap, cfg), pool=list(candidates),
                  tz=datetime.fromisoformat(str(gap["start"])).tzinfo)
    roster = _Roster(ctx)
    now = _mins(ctx["now"])
    buffer = int(cfg["buffer_min"])
    windows = {sid: (_mins(w[0]), _mins(w[1])) for sid, w in (ctx.get("windows") or {}).items()}
    order = sorted(candidates, key=lambda c: (_travel(ctx, c, gap["outlet"]), c))
    rank = {sid: i for i, sid in enumerate(order)}
    k2 = len(vi.options) + 1
    k1 = (2 * len(candidates) + 2) * k2
    weights = cfg["objective_weights"]
    terms = []

    for sid in candidates:
        travel = _travel(ctx, sid, gap["outlet"])
        mine = []
        for opt in vi.options:
            x = model.new_bool_var(f"x[{sid},{opt.idx}]")
            vi.x[(sid, opt.idx)] = x
            mine.append(x)
            facts = _option_facts(sid, opt, ctx, roster, rules, cfg)
            vi.facts[(sid, opt.idx)] = facts
            for rid, coef, bound in facts.constraints:
                model.add(coef * x <= bound).with_name(f"{rid}:{sid}:{opt.idx}")
            # Viability (§5.2), not a legal rule: the person must be able to arrive in time.
            late = 1 if now + travel + buffer > opt.start else 0
            model.add(late * x <= 0).with_name(f"arrival:{sid}:{opt.idx}")
            if sid in windows:
                w0, w1 = windows[sid]
                outside = 1 if opt.start < w0 or opt.end > w1 else 0
                model.add(outside * x <= 0).with_name(f"window:{sid}:{opt.idx}")
            main = (int(weights["cost"]) * facts.cost["total_cents"]
                    + int(weights["fairness"]) * facts.fairness_units)
            terms.append(x * (main * k1 + rank[sid] * k2 + opt.idx))
        used = model.new_bool_var(f"used[{sid}]")
        model.add(sum(mine) == used)
        vi.used[sid] = used

    full = [vi.x[(sid, 0)] for sid in candidates]
    splits = sorted({o.split for o in vi.options if o.split is not None})
    for t in splits:
        y = model.new_bool_var(f"split[{t}]")
        vi.split_vars[t] = y
        firsts = [o.idx for o in vi.options if o.split == t and o.role == "first"]
        seconds = [o.idx for o in vi.options if o.split == t and o.role == "second"]
        model.add(sum(vi.x[(sid, i)] for sid in candidates for i in firsts) == y)
        model.add(sum(vi.x[(sid, i)] for sid in candidates for i in seconds) == y)
        terms.append(y * int(weights["disruption"]) * k1)
    model.add(sum(full) + sum(vi.split_vars.values()) == 1)
    model.minimize(sum(terms))
    return model, vi


def _solver(cfg: dict[str, Any], seed: int, time_limit: float) -> cp_model.CpSolver:
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = seed
    solver.parameters.max_time_in_seconds = time_limit
    return solver


def check_forced(
    assignment: dict[str, Any],
    context: dict[str, Any],
    rules: list[dict[str, Any]],
    cfg: dict[str, Any],
) -> bool:
    """Force one assignment into a model built from the specs. True iff every rule constraint holds.

    Timing and counter-offer windows are left out: this is the legality check used to compare
    against the validator (§3.7 property (b), §6.3).
    """
    sid = str(assignment["staff_id"])
    opt = Option(0, "full", _mins(assignment["start"]), _mins(assignment["end"]), None)
    breaks = None
    if "breaks" in assignment:
        breaks = [(_mins(b["start"]), _mins(b["start"]) + int(b["duration_min"]))
                  for b in assignment["breaks"] or []]
    facts = _option_facts(sid, opt, context, _Roster(context), rules, cfg,
                          compelled=bool(assignment.get("compelled")), breaks=breaks)
    model = cp_model.CpModel()
    x = model.new_bool_var("x")
    for rid, coef, bound in facts.constraints:
        model.add(coef * x <= bound).with_name(rid)
    model.add(x == 1)
    status = _solver(cfg, int(cfg["solver_seed"]), float(cfg["solver_time_limit_s"])).solve(model)
    return status in (cp_model.OPTIMAL, cp_model.FEASIBLE)


def compiled_rule_ids_failing(
    assignment: dict[str, Any],
    context: dict[str, Any],
    rules: list[dict[str, Any]],
    cfg: dict[str, Any],
) -> list[str]:
    """Rule IDs whose compiled constraint is violated for this assignment (diagnostics)."""
    sid = str(assignment["staff_id"])
    opt = Option(0, "full", _mins(assignment["start"]), _mins(assignment["end"]), None)
    breaks = None
    if "breaks" in assignment:
        breaks = [(_mins(b["start"]), _mins(b["start"]) + int(b["duration_min"]))
                  for b in assignment["breaks"] or []]
    facts = _option_facts(sid, opt, context, _Roster(context), rules, cfg,
                          compelled=bool(assignment.get("compelled")), breaks=breaks)
    return sorted({rid for rid, coef, bound in facts.constraints if coef > bound})


def compiled_cost(
    assignment: dict[str, Any],
    context: dict[str, Any],
    rules: list[dict[str, Any]],
    cfg: dict[str, Any],
) -> dict[str, int]:
    sid = str(assignment["staff_id"])
    opt = Option(0, "full", _mins(assignment["start"]), _mins(assignment["end"]), None)
    return _option_facts(sid, opt, context, _Roster(context), rules, cfg).cost


# --------------------------------------------------------------------------- solve


def _assignment(sid: str, opt: Option, facts: OptionFacts, tz: Any) -> dict[str, Any]:
    return {
        "staff_id": sid,
        "start": _iso(opt.start, tz),
        "end": _iso(opt.end, tz),
        "breaks": [{"start": _iso(a, tz), "duration_min": b - a} for a, b in facts.breaks],
    }


def solve(
    gap: dict[str, Any],
    context: dict[str, Any],
    rules: list[dict[str, Any]] | None = None,
    cfg: dict[str, Any] | None = None,
    time_limit_s: float | None = None,
) -> PlanResult:
    """Rank up to ``top_k_plans`` legal plans and cross-check each one with the validator."""
    rules = load_rules() if rules is None else rules
    cfg = load_company_config() if cfg is None else cfg
    ctx = dict(context, gap=gap, company=cfg)
    staff = _index(ctx.get("staff"), "staff_id")
    pool = _pool(ctx)
    seed = int(ctx.get("seed", cfg["solver_seed"]))
    limit = float(time_limit_s if time_limit_s is not None else cfg["solver_time_limit_s"])
    model, vi = build_model(gap, pool, ctx, rules, cfg)
    disagreements: list[dict[str, Any]] = []

    # Every pool member's full-gap assignment: compiled legality must equal the validator's.
    rejected = []
    for sid in pool:
        if sid in (ctx.get("windows") or {}):
            continue
        facts = vi.facts[(sid, 0)]
        asg = _assignment(sid, vi.options[0], facts, vi.tz)
        results = validate_assignment(asg, ctx, rules)
        v_block = blocking_violations(results)
        c_fail = sorted({rid for rid, coef, bound in facts.constraints if coef > bound})
        if sorted({r.rule_id for r in v_block}) != c_fail:
            disagreements.append({"staff_id": sid, "validator": [r.rule_id for r in v_block],
                                  "compiler": c_fail})
        if v_block:
            rejected.append({
                "staff_id": sid,
                "display_name": staff[sid].get("display_name", sid),
                "rejected_rules": [
                    {"rule_id": r.rule_id, "message": r.message, "source_url": r.source_url,
                     "params": r.params}
                    for r in v_block
                ],
            })

    plans: list[dict[str, Any]] = []
    for rank in range(1, int(cfg["top_k_plans"]) + 1):
        solver = _solver(cfg, seed, limit)
        status = solver.solve(model)
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            break
        chosen = sorted(((sid, vi.options[i]) for (sid, i), var in vi.x.items()
                         if solver.value(var)), key=lambda p: p[1].start)
        people = [sid for sid, _ in chosen]
        model.add(sum(vi.used[sid] for sid in people) <= len(people) - 1)

        segments = []
        total = {"base_cents": 0, "overtime_cents": 0, "rest_day_cents": 0, "total_cents": 0}
        for sid, opt in chosen:
            facts = vi.facts[(sid, opt.idx)]
            asg = _assignment(sid, opt, facts, vi.tz)
            results = validate_assignment(asg, ctx, rules)
            v_cost = cost_breakdown(results)
            if blocking_violations(results) or v_cost != facts.cost:
                disagreements.append({
                    "staff_id": sid, "segment": [asg["start"], asg["end"]],
                    "validator": [r.rule_id for r in blocking_violations(results)],
                    "validator_cost": v_cost, "compiler_cost": facts.cost,
                })
            travel = _travel(ctx, sid, gap["outlet"])
            for key in total:
                total[key] += facts.cost[key]
            segments.append(dict(
                asg,
                display_name=staff[sid].get("display_name", sid),
                home_outlet=staff[sid].get("home_outlet"),
                travel_min=travel,
                arrival=_iso(_mins(ctx["now"]) + travel, vi.tz),
                cost_breakdown=facts.cost,
                fairness_penalty_units=facts.fairness_units,
                rules_checked=[{"rule_id": r.rule_id, "status": r.status, "kind": r.kind,
                                "message": r.message, "source_url": r.source_url}
                               for r in results],
            ))
        plans.append({
            "rank": rank,
            "staff_ids": people,
            "segments": segments,
            "cost_breakdown": total,
            "overtime_cost_cents": total["overtime_cents"] + total["rest_day_cents"],
            "travel_min": max(s["travel_min"] for s in segments),
            "arrival": max(s["arrival"] for s in segments),
            "is_cross_outlet_borrow": any(s["home_outlet"] != gap["outlet"] for s in segments),
            "objective": int(solver.objective_value),
            "solver_status": solver.status_name(status),
        })

    if disagreements:
        raise PlanDisagreement(
            f"solver and validator disagree on {len(disagreements)} assignment(s)", disagreements
        )
    return PlanResult(
        candidates=plans,
        rejected_candidates=rejected,
        solver_params={
            "num_search_workers": 1,
            "random_seed": seed,
            "max_time_in_seconds": limit,
            "top_k_plans": int(cfg["top_k_plans"]),
            "max_segments": int(cfg["max_segments"]),
            "split_granularity_min": int(cfg["split_granularity_min"]),
            "pool_size": len(pool),
        },
    )
