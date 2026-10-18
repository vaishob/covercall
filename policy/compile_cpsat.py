"""OR-Tools CP-SAT policy compiler and top-k deterministic solver (§3.5, §6.3, §6.4).

Compiles declarative YAML rule specs into CP-SAT constraints and integer-cent
cost terms, finds up to `top_k_plans` feasible coverage plans (single assignee or
split into at most `max_segments` contiguous segments), and verifies every ranked
plan through `policy.validate.validate_assignment`. Any disagreement raises
`PlanDisagreement` (P0 -> HELD).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import yaml
from ortools.sat.python import cp_model

from policy.validate import RuleResult, validate_assignment


class PlanDisagreement(RuntimeError):
    """Raised when the CP-SAT solver and independent validator disagree (P0)."""


@dataclass
class SegmentAssignment:
    staff_id: str
    display_name: str
    start: str
    end: str
    work_hours: float
    travel_min: int
    arrival: str
    cost_breakdown: dict[str, int]  # integer cents
    rules_checked: list[dict[str, Any]]


@dataclass
class RankedPlan:
    rank: int
    staff_id: str
    display_name: str
    segments: list[dict[str, Any]]
    cost_breakdown: dict[str, int]  # integer cents: base_cents, overtime_cents, rest_day_cents, total_incremental_cents
    total_cost_sgd: float
    overtime_cost_sgd: float
    travel_min: int
    arrival: str
    is_cross_outlet_borrow: bool
    rules_checked: list[dict[str, Any]]
    objective_score: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RejectedCandidate:
    staff_id: str
    display_name: str
    rejected_rules: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PlanResult:
    candidates: list[RankedPlan]
    rejected_candidates: list[RejectedCandidate]
    solver_params: dict[str, Any]
    validator_version: str = "1.0.0"
    disagreement: bool = False
    synthetic: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidates": [c.to_dict() for c in self.candidates],
            "rejected_candidates": [r.to_dict() for r in self.rejected_candidates],
            "solver_params": self.solver_params,
            "validator_version": self.validator_version,
            "disagreement": self.disagreement,
            "synthetic": self.synthetic,
        }


@dataclass
class VarIndex:
    segment_vars: dict[tuple[str, int], cp_model.IntVar] = field(default_factory=dict)
    segments: list[tuple[str, str, float]] = field(default_factory=list)
    candidate_meta: dict[str, dict[str, Any]] = field(default_factory=dict)


def load_rules(rules_dir: str | Path = Path("policy/rules")) -> list[dict[str, Any]]:
    p = Path(rules_dir)
    rules: list[dict[str, Any]] = []
    for path in sorted(p.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            rules.append(data)
    return rules


def load_company_config(path: str | Path = Path("policy/company.yaml")) -> dict[str, Any]:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def _parse_hhmm_or_iso(ts: str, base_date_str: str = "2026-11-03") -> datetime:
    if "T" in ts:
        return datetime.fromisoformat(ts)
    return datetime.fromisoformat(f"{base_date_str}T{ts}:00+08:00")


def _compute_part4_cpsat(emp: dict[str, Any], rules_by_id: dict[str, dict[str, Any]]) -> bool:
    cov = rules_by_id.get("SG-EA4-COVERAGE", {}).get("params", {})
    emp_class = str(emp.get("employee_class", "non_workman"))
    if emp_class in set(cov.get("exclude_employee_classes", ["manager_executive"])):
        return False
    monthly = emp.get("monthly_basic_sgd")
    if monthly is None:
        hourly = float(emp.get("hourly_basic_sgd") or 0.0)
        monthly = (hourly * 44.0 * 52.0) / 12.0
    else:
        monthly = float(monthly)
    if emp_class == "workman":
        return monthly <= float(cov.get("workman_basic_salary_cap_sgd", 4500))
    return monthly <= float(cov.get("non_workman_basic_salary_cap_sgd", 2600))


def _evaluate_candidate_segment_cpsat(
    emp: dict[str, Any],
    ledger: dict[str, Any],
    shift_ctx: dict[str, Any],
    rules_by_id: dict[str, dict[str, Any]],
    cfg: dict[str, Any],
) -> tuple[bool, dict[str, int]]:
    """Compile rule specs for a candidate-segment pair into (is_hard_feasible, cost_breakdown_cents)."""
    part4 = _compute_part4_cpsat(emp, rules_by_id)
    work_h = float(shift_ctx.get("work_hours", 8.0))
    prior_h = float(shift_ctx.get("hours_worked_today_before_shift", 0.0))
    daily_h = prior_h + work_h
    normal_h = float(emp.get("normal_daily_hours", 8.0))
    is_pt = emp.get("contract_type") == "part_time"
    eff_normal_h = 8.0 if is_pt else normal_h

    is_rest = bool(shift_ctx.get("is_rest_day", False))
    is_ph = bool(shift_ctx.get("is_public_holiday", False))
    is_extra_cover = bool(shift_ctx.get("is_extra_cover_shift", False))

    if is_rest or is_ph:
        before_ot = max(0.0, prior_h - eff_normal_h)
        after_ot = max(0.0, daily_h - eff_normal_h)
        ot_added = max(0.0, after_ot - before_ot)
    elif is_extra_cover:
        ot_added = work_h
    else:
        before_ot = max(0.0, prior_h - eff_normal_h)
        after_ot = max(0.0, daily_h - eff_normal_h)
        ot_added = max(0.0, after_ot - before_ot)

    ot_used = float(ledger.get("ot_hours_used", 0.0))

    # 1. CO-AGE-SCOPE
    if "CO-AGE-SCOPE" in rules_by_id:
        min_age = int(rules_by_id["CO-AGE-SCOPE"]["params"].get("min_allowed_age", 16))
        if int(emp.get("age", 18)) < min_age:
            return False, {}

    # 2. CO-STATION-SKILL
    if "CO-STATION-SKILL" in rules_by_id:
        if str(shift_ctx.get("station", "barista")) not in list(emp.get("skills") or []):
            return False, {}

    # 3. CO-OPENER-KEYHOLDER
    if "CO-OPENER-KEYHOLDER" in rules_by_id and bool(shift_ctx.get("is_opening_shift", False)):
        if not (bool(emp.get("keyholder", False)) or bool(shift_ctx.get("other_keyholder_present", False))):
            return False, {}

    # 4. CO-REST-BETWEEN-SHIFTS
    if "CO-REST-BETWEEN-SHIFTS" in rules_by_id:
        min_rest = float(rules_by_id["CO-REST-BETWEEN-SHIFTS"]["params"].get("min_rest_hours_between_shifts", 11.0))
        prev_rest = float(shift_ctx.get("hours_since_prev_shift_end", 24.0))
        next_rest = float(shift_ctx.get("hours_until_next_shift_start", 24.0))
        if min(prev_rest, next_rest) < min_rest:
            return False, {}

    # 5. SG-SFA-FSC-L1
    if "SG-SFA-FSC-L1" in rules_by_id:
        fsc_params = rules_by_id["SG-SFA-FSC-L1"]["params"]
        req_stations = set(fsc_params.get("stations_requiring_fsc", ["kitchen", "barista"]))
        if str(shift_ctx.get("station", "barista")) in req_stations:
            passed_str = emp.get("fsc_l1_passed_on")
            if not passed_str:
                return False, {}
            passed_dt = date.fromisoformat(str(passed_str)[:10])
            shift_start_str = str(shift_ctx.get("start", "2026-11-03"))
            shift_dt = date.fromisoformat(shift_start_str[:10])
            ref_years = int(fsc_params.get("fsc_l1_refresher_years", 5))
            try:
                exp_dt = date(passed_dt.year + ref_years, passed_dt.month, passed_dt.day)
            except ValueError:
                exp_dt = date(passed_dt.year + ref_years, 2, 28)
            if shift_dt > exp_dt:
                return False, {}

    # Statutory Part 4 hard rules
    if part4:
        if "SG-EA4-OT-CAP-72" in rules_by_id:
            max_ot = float(rules_by_id["SG-EA4-OT-CAP-72"]["params"].get("max_overtime_hours_per_month", 72))
            if (ot_used + ot_added) > max_ot:
                return False, {}

        if "SG-EA4-DAILY-MAX-12H" in rules_by_id:
            max_daily = float(rules_by_id["SG-EA4-DAILY-MAX-12H"]["params"].get("max_daily_hours", 12))
            if daily_h > max_daily:
                return False, {}

        if "SG-EA4-REST-DAY" in rules_by_id:
            max_days = int(rules_by_id["SG-EA4-REST-DAY"]["params"].get("max_days_between_rest_days", 12))
            if int(shift_ctx.get("days_since_last_rest_day", 2)) > max_days or bool(
                shift_ctx.get("compelled_rest_day_work", False)
            ):
                return False, {}

        if "SG-EA4-BREAKS" in rules_by_id:
            b_params = rules_by_id["SG-EA4-BREAKS"]["params"]
            min_b = int(b_params.get("min_meal_break_min_for_8h_continuous", 45))
            max_c = float(b_params.get("max_consecutive_hours_without_break", 6.0))
            breaks_min = int(shift_ctx.get("breaks_min", 45))
            if (work_h >= 8.0 and breaks_min < min_b) or (work_h > max_c and breaks_min <= 0):
                return False, {}

    # Cost calculation in integer cents
    base_cents = 0
    overtime_cents = 0
    rest_day_cents = 0

    if is_pt:
        hourly = float(emp.get("hourly_basic_sgd") or 12.0)
        before_pt_ot = max(0.0, prior_h - 8.0)
        after_pt_ot = max(0.0, daily_h - 8.0)
        pt_ot_h = max(0.0, after_pt_ot - before_pt_ot)
        reg_h = max(0.0, work_h - pt_ot_h)
        base_cents = int(round(reg_h * hourly * 100))
        overtime_cents = int(round(pt_ot_h * hourly * 1.5 * 100))
    else:
        monthly = float(emp.get("monthly_basic_sgd") or 2400.0)
        hourly_basic = (12.0 * monthly) / (52.0 * 44.0)
        capped_hourly = (
            min(hourly_basic, 13.60) if emp.get("employee_class") == "non_workman" else hourly_basic
        )
        if part4 and is_rest:
            day_sal = (12.0 * monthly) / (52.0 * 5.5)
            if work_h <= (normal_h / 2.0):
                days_pay = 1
                extra_ot_h = 0.0
            elif work_h <= normal_h:
                days_pay = 2
                extra_ot_h = 0.0
            else:
                days_pay = 2
                extra_ot_h = work_h - normal_h
            rest_day_cents = int(round(days_pay * day_sal * 100))
            overtime_cents = int(round(extra_ot_h * capped_hourly * 1.5 * 100))
        elif part4:
            overtime_cents = int(round(ot_added * capped_hourly * 1.5 * 100))

    fairness_cfg = cfg.get("fairness", {})
    max_covers = int(fairness_cfg.get("max_covers", 2))
    covers_14d = int(ledger.get("cover_requests_14d", 0))
    excess_covers = max(0, covers_14d - max_covers)

    is_borrow = str(emp.get("home_outlet", shift_ctx.get("outlet"))) != str(shift_ctx.get("outlet"))
    travel_min = int(shift_ctx.get("travel_min", 20))

    weights = cfg.get("objective_weights", {"cost": 1, "fairness": 500, "disruption": 300})
    w_cost = int(weights.get("cost", 1))
    w_fair = int(weights.get("fairness", 500))
    w_disr = int(weights.get("disruption", 300))

    total_incremental_cents = base_cents + overtime_cents + rest_day_cents
    fairness_penalty_cents = excess_covers * w_fair
    disruption_penalty_cents = (w_disr if is_borrow else 0) + travel_min * 5

    objective_cents = (
        w_cost * total_incremental_cents + fairness_penalty_cents + disruption_penalty_cents
    )

    return True, {
        "base_cents": base_cents,
        "overtime_cents": overtime_cents,
        "rest_day_cents": rest_day_cents,
        "total_incremental_cents": total_incremental_cents,
        "fairness_penalty_cents": fairness_penalty_cents,
        "disruption_penalty_cents": disruption_penalty_cents,
        "objective_cents": objective_cents,
    }


def _build_shift_context_for_candidate(
    cand: dict[str, Any],
    gap: dict[str, Any],
    context: dict[str, Any],
    seg_start_iso: str,
    seg_end_iso: str,
    seg_hours: float,
    is_opening_seg: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    sid = str(cand["staff_id"])
    ledgers = context.get("ledgers") or {}
    ledger = dict(
        cand.get("ledger")
        or ledgers.get(sid)
        or ledgers.get(f"{sid}_202611")
        or {"ot_hours_used": 0, "rest_days": ["2026-11-01"], "cover_requests_14d": 0}
    )

    overrides = context.get("overrides") or []
    for ov in overrides:
        if isinstance(ov, dict) and ov.get("staff") == sid and "ledger" in ov:
            ledger.update(ov["ledger"])

    shift_State = dict(cand.get("shift_context") or {})
    outlet = str(gap.get("outlet", "bugis"))
    station = str(gap.get("station", "barista"))
    travel_map = context.get("travel_min_by_staff") or {}
    travel_min = int(
        cand.get("travel_min")
        or travel_map.get(sid)
        or (18 if cand.get("home_outlet") == outlet else 28)
    )

    breaks_min = int(shift_State.get("breaks_min", 45 if seg_hours >= 8.0 else 15))
    shift_ctx = {
        "outlet": outlet,
        "station": station,
        "start": seg_start_iso,
        "end": seg_end_iso,
        "work_hours": seg_hours,
        "hours_worked_today_before_shift": float(
            shift_State.get("hours_worked_today_before_shift", 0.0)
        ),
        "breaks_min": breaks_min,
        "is_rest_day": bool(shift_State.get("is_rest_day", False)),
        "is_public_holiday": bool(shift_State.get("is_public_holiday", False)),
        "is_extra_cover_shift": bool(
            shift_State.get("is_extra_cover_shift", cand.get("contract_type") == "full_time")
        ),
        "is_opening_shift": is_opening_seg,
        "other_keyholder_present": bool(shift_State.get("other_keyholder_present", True)),
        "hours_since_prev_shift_end": float(shift_State.get("hours_since_prev_shift_end", 14.0)),
        "hours_until_next_shift_start": float(
            shift_State.get("hours_until_next_shift_start", 14.0)
        ),
        "days_since_last_rest_day": int(shift_State.get("days_since_last_rest_day", 2)),
        "travel_min": travel_min,
    }
    return ledger, shift_ctx


def build_model(
    gap: dict[str, Any],
    candidates: list[dict[str, Any]],
    context: dict[str, Any],
    rules: list[dict[str, Any]],
    cfg: dict[str, Any],
) -> tuple[cp_model.CpModel, VarIndex]:
    """Build the CP-SAT model and variable index for a gap."""
    model = cp_model.CpModel()
    var_index = VarIndex()
    rules_by_id = {r["id"]: r for r in rules if isinstance(r, dict) and "id" in r}

    base_date_str = str(context.get("now", "2026-11-03T06:02:00+08:00"))[:10]
    start_dt = _parse_hhmm_or_iso(str(gap.get("start", "07:00")), base_date_str)
    end_dt = _parse_hhmm_or_iso(str(gap.get("end", "15:00")), base_date_str)
    total_hours = max(1.0, (end_dt - start_dt).total_seconds() / 3600.0)

    # Segment 0 is the full shift [start, end].
    # If counter_split_at (e.g. "09:00") is present and max_segments >= 2, add segments 1 and 2:
    # seg 1: [start, split_dt], seg 2: [split_dt, end].
    var_index.segments.append((start_dt.isoformat(), end_dt.isoformat(), total_hours))
    split_hhmm = context.get("counter_split_at")
    max_segments = int(cfg.get("max_segments", 2))
    has_split = False
    if split_hhmm and max_segments >= 2:
        split_dt = _parse_hhmm_or_iso(str(split_hhmm), base_date_str)
        if start_dt < split_dt < end_dt:
            h1 = (split_dt - start_dt).total_seconds() / 3600.0
            h2 = (end_dt - split_dt).total_seconds() / 3600.0
            var_index.segments.append((start_dt.isoformat(), split_dt.isoformat(), h1))
            var_index.segments.append((split_dt.isoformat(), end_dt.isoformat(), h2))
            has_split = True

    absent_id = str(gap.get("absent") or gap.get("absent_staff_id") or "")
    unavailable_ids = set(context.get("unavailable_staff_ids") or [])
    if absent_id:
        unavailable_ids.add(absent_id)

    obj_terms: list[Any] = []
    split_mode = model.new_bool_var("use_split_segments")
    if not has_split:
        model.add(split_mode == 0)

    for cand in candidates:
        sid = str(cand["staff_id"])
        var_index.candidate_meta[sid] = cand
        for seg_idx, (s_iso, e_iso, s_hours) in enumerate(var_index.segments):
            v = model.new_bool_var(f"assign_{sid}_seg{seg_idx}")
            var_index.segment_vars[(sid, seg_idx)] = v

            if sid in unavailable_ids:
                model.add(v == 0)
                continue

            # Check optional candidate availability window (e.g. from counter-offer)
            avail_win = cand.get("available_window")
            if avail_win and isinstance(avail_win, (list, tuple)) and len(avail_win) == 2:
                w_start = _parse_hhmm_or_iso(str(avail_win[0]), base_date_str)
                w_end = _parse_hhmm_or_iso(str(avail_win[1]), base_date_str)
                seg_s_dt = datetime.fromisoformat(s_iso)
                seg_e_dt = datetime.fromisoformat(e_iso)
                if seg_s_dt < w_start or seg_e_dt > w_end:
                    model.add(v == 0)
                    continue

            is_opening = bool(
                gap.get("is_opening_shift", str(gap.get("start", "07:00")).startswith("07:"))
                and seg_idx in (0, 1)
            )
            ledger, shift_ctx = _build_shift_context_for_candidate(
                cand, gap, context, s_iso, e_iso, s_hours, is_opening
            )
            feasible, cost_dict = _evaluate_candidate_segment_cpsat(
                cand, ledger, shift_ctx, rules_by_id, cfg
            )
            if not feasible:
                model.add(v == 0)
            else:
                # Add disruption penalty if using split segments
                extra_split_pen = int(cfg.get("objective_weights", {}).get("disruption", 300)) if seg_idx > 0 else 0
                obj_terms.append(v * (cost_dict["objective_cents"] + extra_split_pen))

        # A single candidate cannot work both segments of a split in place of a full shift
        if has_split:
            model.add(
                var_index.segment_vars[(sid, 0)]
                + var_index.segment_vars[(sid, 1)]
                + var_index.segment_vars[(sid, 2)]
                <= 1
            )

    # Coverage constraints: either 1 candidate covers seg 0, OR (1 covers seg 1 AND 1 covers seg 2)
    seg0_vars = [var_index.segment_vars[(c["staff_id"], 0)] for c in candidates]
    model.add(sum(seg0_vars) == 1 - split_mode)
    if has_split:
        seg1_vars = [var_index.segment_vars[(c["staff_id"], 1)] for c in candidates]
        seg2_vars = [var_index.segment_vars[(c["staff_id"], 2)] for c in candidates]
        model.add(sum(seg1_vars) == split_mode)
        model.add(sum(seg2_vars) == split_mode)

    model.minimize(sum(obj_terms))
    return model, var_index


def check_forced_assignment(
    assignment: dict[str, Any],
    context: dict[str, Any],
    rules: list[dict[str, Any]],
    cfg: dict[str, Any] | None = None,
) -> bool:
    """Force a single assignment into the CP-SAT model and return True iff feasible.

    Used by Hypothesis property tests (§3.7, §6.3) to verify that every assignment
    rejected by `validate.py` is infeasible in `compile_cpsat.py`.
    """
    if cfg is None:
        cfg = load_company_config()
    emp = dict(assignment.get("employee") or context.get("employee") or {})
    shift = dict(assignment.get("shift") or context.get("shift") or {})
    ledger = dict(assignment.get("ledger") or context.get("ledger") or {})
    emp["staff_id"] = str(emp.get("staff_id", "stf_test"))
    emp["ledger"] = ledger
    emp["shift_context"] = shift

    gap = {
        "outlet": shift.get("outlet", "bugis"),
        "station": shift.get("station", "barista"),
        "start": shift.get("start", "2026-11-03T07:00:00+08:00"),
        "end": shift.get("end", "2026-11-03T15:00:00+08:00"),
        "is_opening_shift": shift.get("is_opening_shift", True),
    }
    work_h = float(shift.get("work_hours", 8.0))
    start_dt = _parse_hhmm_or_iso(str(gap["start"]))
    end_dt = start_dt + timedelta(hours=work_h)
    gap["start"] = start_dt.isoformat()
    gap["end"] = end_dt.isoformat()

    model, var_index = build_model(gap, [emp], context, rules, cfg)
    v = var_index.segment_vars[(emp["staff_id"], 0)]
    model.add(v == 1)

    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = int(cfg.get("solver_seed", 42))
    solver.parameters.max_time_in_seconds = float(cfg.get("solver_time_limit_s", 2.0))
    status = solver.solve(model)
    return status in (cp_model.OPTIMAL, cp_model.FEASIBLE)


def solve(
    gap: dict[str, Any],
    context: dict[str, Any],
    rules: list[dict[str, Any]] | None = None,
    cfg: dict[str, Any] | None = None,
) -> PlanResult:
    """Solve for up to `top_k_plans` ranked legal plans and validate every plan via `validate.py`."""
    if rules is None:
        rules = load_rules()
    if cfg is None:
        cfg = load_company_config()

    rules_by_id = {r["id"]: r for r in rules if isinstance(r, dict) and "id" in r}
    candidates = sorted(
        list(context.get("candidates") or context.get("staff") or []),
        key=lambda c: str(c.get("staff_id", "")),
    )

    base_date_str = str(context.get("now", "2026-11-03T06:02:00+08:00"))[:10]
    now_dt = _parse_hhmm_or_iso(str(context.get("now", "2026-11-03T06:02:00+08:00")), base_date_str)
    start_dt = _parse_hhmm_or_iso(str(gap.get("start", "07:00")), base_date_str)
    end_dt = _parse_hhmm_or_iso(str(gap.get("end", "15:00")), base_date_str)
    total_hours = max(1.0, (end_dt - start_dt).total_seconds() / 3600.0)
    is_opening_gap = bool(
        gap.get("is_opening_shift", str(gap.get("start", "07:00")).startswith("07:"))
    )

    absent_id = str(gap.get("absent") or gap.get("absent_staff_id") or "")
    unavailable_ids = set(context.get("unavailable_staff_ids") or [])
    if absent_id:
        unavailable_ids.add(absent_id)

    # First, collect rejected candidates with their exact validator rule warnings
    rejected_candidates: list[RejectedCandidate] = []
    for cand in candidates:
        sid = str(cand["staff_id"])
        if sid in unavailable_ids:
            continue
        ledger, shift_ctx = _build_shift_context_for_candidate(
            cand, gap, context, start_dt.isoformat(), end_dt.isoformat(), total_hours, is_opening_gap
        )
        val_results = validate_assignment(
            {"employee": cand, "ledger": ledger, "shift": shift_ctx},
            context,
            rules,
        )
        hard_violations = [
            r.to_dict()
            for r in val_results
            if r.status == "violation" and r.kind in ("hard", "data_gate")
        ]
        if hard_violations:
            rejected_candidates.append(
                RejectedCandidate(
                    staff_id=sid,
                    display_name=str(cand.get("display_name", sid)),
                    rejected_rules=hard_violations,
                )
            )

    model, var_index = build_model(gap, candidates, context, rules, cfg)
    top_k = int(cfg.get("top_k_plans", 3))
    seed = int(context.get("seed", cfg.get("solver_seed", 42)))
    time_limit_s = float(cfg.get("solver_time_limit_s", 2.0))

    ranked_plans: list[RankedPlan] = []

    for rank_idx in range(1, top_k + 1):
        solver = cp_model.CpSolver()
        solver.parameters.num_search_workers = 1
        solver.parameters.random_seed = seed
        solver.parameters.max_time_in_seconds = time_limit_s

        status = solver.solve(model)
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            break

        active_pairs: list[tuple[str, int]] = []
        for (sid, seg_idx), var in var_index.segment_vars.items():
            if solver.value(var) == 1:
                active_pairs.append((sid, seg_idx))

        if not active_pairs:
            break

        # Add no-good cut to find next best distinct plan
        chosen_vars = [var_index.segment_vars[p] for p in active_pairs]
        model.add(sum(chosen_vars) <= len(chosen_vars) - 1)

        segments_out: list[dict[str, Any]] = []
        agg_cost = {
            "base_cents": 0,
            "overtime_cents": 0,
            "rest_day_cents": 0,
            "total_incremental_cents": 0,
        }
        all_rules_checked: list[dict[str, Any]] = []
        max_travel = 0
        latest_arrival_str = ""
        any_borrow = False
        primary_staff_id = active_pairs[0][0]
        display_names: list[str] = []

        for sid, seg_idx in sorted(active_pairs, key=lambda x: x[1]):
            cand = var_index.candidate_meta[sid]
            s_iso, e_iso, s_hours = var_index.segments[seg_idx]
            is_open_seg = is_opening_gap and seg_idx in (0, 1)
            ledger, shift_ctx = _build_shift_context_for_candidate(
                cand, gap, context, s_iso, e_iso, s_hours, is_open_seg
            )
            _, cost_dict = _evaluate_candidate_segment_cpsat(
                cand, ledger, shift_ctx, rules_by_id, cfg
            )

            # Independent validator check on every chosen segment!
            seg_val_results: list[RuleResult] = validate_assignment(
                {"employee": cand, "ledger": ledger, "shift": shift_ctx},
                context,
                rules,
            )
            hard_viol = [
                r for r in seg_val_results if r.status == "violation" and r.kind in ("hard", "data_gate")
            ]
            if hard_viol:
                raise PlanDisagreement(
                    f"Solver selected {sid} for segment {seg_idx}, but validator rejected with: "
                    f"{[r.rule_id for r in hard_viol]}"
                )

            for k in ("base_cents", "overtime_cents", "rest_day_cents", "total_incremental_cents"):
                agg_cost[k] += cost_dict.get(k, 0)

            t_min = int(shift_ctx["travel_min"])
            max_travel = max(max_travel, t_min)
            arr_dt = now_dt + timedelta(minutes=t_min)
            arr_hhmm = arr_dt.strftime("%H:%M")
            if not latest_arrival_str or arr_hhmm > latest_arrival_str:
                latest_arrival_str = arr_hhmm

            if str(cand.get("home_outlet", gap.get("outlet"))) != str(gap.get("outlet")):
                any_borrow = True

            d_name = str(cand.get("display_name", sid))
            display_names.append(d_name)
            rules_dicts = [r.to_dict() for r in seg_val_results]
            all_rules_checked.extend(rules_dicts)
            segments_out.append(
                {
                    "staff_id": sid,
                    "display_name": d_name,
                    "start": s_iso,
                    "end": e_iso,
                    "work_hours": s_hours,
                    "travel_min": t_min,
                    "arrival": arr_hhmm,
                    "cost_breakdown": cost_dict,
                    "rules_checked": rules_dicts,
                }
            )

        ranked_plans.append(
            RankedPlan(
                rank=rank_idx,
                staff_id=primary_staff_id if len(active_pairs) == 1 else "+".join(p[0] for p in active_pairs),
                display_name=" + ".join(display_names),
                segments=segments_out,
                cost_breakdown=agg_cost,
                total_cost_sgd=round(agg_cost["total_incremental_cents"] / 100.0, 2),
                overtime_cost_sgd=round(
                    (agg_cost["overtime_cents"] + agg_cost["rest_day_cents"]) / 100.0, 2
                ),
                travel_min=max_travel,
                arrival=latest_arrival_str,
                is_cross_outlet_borrow=any_borrow,
                rules_checked=all_rules_checked,
                objective_score=int(solver.objective_value),
            )
        )

    # Also verify reverse direction: no candidate that validator found 100% hard-feasible was falsely excluded
    # when top_k wasn't exhausted
    if len(ranked_plans) == 0:
        for cand in candidates:
            sid = str(cand["staff_id"])
            if sid in unavailable_ids or cand.get("available_window"):
                continue
            ledger, shift_ctx = _build_shift_context_for_candidate(
                cand, gap, context, start_dt.isoformat(), end_dt.isoformat(), total_hours, is_opening_gap
            )
            val_results = validate_assignment(
                {"employee": cand, "ledger": ledger, "shift": shift_ctx},
                context,
                rules,
            )
            if not any(
                r.status == "violation" and r.kind in ("hard", "data_gate") for r in val_results
            ):
                raise PlanDisagreement(
                    f"Validator accepted {sid}, but CP-SAT solver returned 0 feasible plans."
                )

    return PlanResult(
        candidates=ranked_plans,
        rejected_candidates=rejected_candidates,
        solver_params={
            "num_search_workers": 1,
            "random_seed": seed,
            "max_time_in_seconds": time_limit_s,
            "top_k_plans": top_k,
            "max_segments": int(cfg.get("max_segments", 2)),
        },
    )
