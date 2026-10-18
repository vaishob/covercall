"""Seeded synthetic data generator (§3.8, §8.1-§8.5): ``python -m datagen build --seed 42``.

All data is synthetic and every record carries ``synthetic: true``. The business is fictional; the
outlet areas are real Singapore place names. No staff under 16 exist: ``load_staff`` enforces
CO-AGE-SCOPE and rejects any such record. Generated staff are 17 or over.

Scenario ``expect`` blocks are computed by the solver and validator (``evals.cascade_sim``) with
the offline time limit, never typed by hand.
"""

from __future__ import annotations

import json
import random
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from datagen.loader import load_staff
from datagen.personas import busy_blocks, make_persona
from policy.compile_cpsat import load_company_config, load_rules

WINDOW_START = date(2026, 10, 19)  # Monday; see docs/decisions/0007-synthetic-data.md
WINDOW_END = date(2026, 11, 15)  # Sunday
SCENARIO_DAYS = [date(2026, 11, 3) + timedelta(days=i) for i in range(5)]  # Tue..Sat
GENERATED_AT = "2026-10-18T00:00:00+08:00"

OUTLETS: list[dict[str, Any]] = [
    # Real area names; coordinates are approximate public area centroids (docs/OPEN_ITEMS.md).
    {"outlet_id": "bugis", "name": "Bugis", "area": "Bugis", "lat": 1.2997, "lng": 103.8555},
    {"outlet_id": "tampines", "name": "Tampines", "area": "Tampines", "lat": 1.3525, "lng": 103.9447},
    {"outlet_id": "jurong_east", "name": "Jurong East", "area": "Jurong East", "lat": 1.3329,
     "lng": 103.7436},
]
STATIONS = [
    {"station": "barista", "skill": "barista", "food_handling": True, "min_count": 1},
    {"station": "kitchen", "skill": "kitchen", "food_handling": True, "min_count": 1},
    {"station": "cashier", "skill": "cashier", "food_handling": False, "min_count": 1},
]
SHIFT_TYPES = {"AM": ("07:00", "15:00", "11:00"), "PM": ("13:00", "21:00", "17:00")}

# One flat pool. Persona style is sampled independently and never reads the name (§8.3 MUST).
NAMES = [
    "Marcus", "Rachel", "Darren", "Priya", "Amir", "Gloria", "Hafiz", "Nadia", "Kelvin", "Wei",
    "Ali", "Siti", "Rohan", "Mei", "Farhan", "Chloe", "Arjun", "Zhi", "Aisha", "Ryan", "Kavitha",
    "Lucas", "Nurul", "Ethan", "Shreya", "Daniel", "Harith", "Fiona", "Vikram", "Hannah", "Joel",
    "Farah", "Sean",
]
PART_TIME = {20, 21, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33}
WORKMEN = {5, 9, 13, 17}
CASHIER_ONLY = {7, 18, 29}
LAPSED_FSC = {14, 27}
KEYHOLDERS = {1, 2, 3, 4, 8, 10, 11, 12, 14, 16, 19, 25, 28}
# Staff outside Part 4: 15 and 16 earn above S$2,600 (non-workmen), 17 above S$4,500 (workman).
SALARY_PINS = {1: 4200, 4: 2400, 6: 2350, 8: 2300, 11: 2400, 15: 2750, 16: 3100, 17: 4700, 19: 2450,
               22: 2500}
SKILL_PINS = {4: ["barista", "cashier"], 8: ["barista", "cashier"], 11: ["barista", "cashier"],
              15: ["kitchen", "cashier"], 16: ["cashier", "kitchen"], 17: ["kitchen"],
              19: ["barista", "cashier"], 22: ["barista", "cashier"], 1: ["barista", "kitchen", "cashier"]}


def _ft_pattern(rng: random.Random, idx: int) -> dict[str, Any]:
    """Weekly pattern for a full-timer: fixed shift type, one rest weekday, one day off."""
    pins = {
        1: ("AM", 6, 5), 4: ("AM", 6, 1), 11: ("AM", 6, 2), 19: ("AM", 6, 1), 22: ("AM", 0, 1),
        8: ("AM", 6, 1), 6: ("AM", 4, 2),
    }
    if idx in pins:
        stype, rest, off = pins[idx]
    else:
        stype = rng.choice(["AM", "PM"]) if idx not in KEYHOLDERS else "AM"
        rest = rng.choice([0, 2, 3, 4, 5, 6])
        off = rng.choice([d for d in range(7) if d != rest])
    return {"type": stype, "rest_weekday": rest, "off_weekday": off}


def _staff(rng: random.Random, cfg: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    institutions = ["polytechnic", "ITE", "university"]
    for idx in range(1, 34):
        sid = f"stf_{idx:03d}"
        home = OUTLETS[(idx - 1) % 3]["outlet_id"]
        if idx in (1, 11):
            home = "bugis"
        pt = idx in PART_TIME
        if idx == 1:
            emp_class = "manager_executive"
        elif idx in WORKMEN:
            emp_class = "workman"
        else:
            emp_class = "non_workman"
        if idx in CASHIER_ONLY:
            skills = ["cashier"]
        elif idx in SKILL_PINS:
            skills = SKILL_PINS[idx]
        else:
            skills = rng.choice([["barista", "cashier"], ["kitchen", "cashier"],
                                 ["barista", "kitchen", "cashier"]])
        if "barista" not in skills and "kitchen" not in skills:
            fsc = None
        elif idx in LAPSED_FSC:
            fsc = f"20{rng.choice([19, 20])}-0{rng.randint(1, 9)}-15"
        else:
            fsc = f"202{rng.randint(2, 5)}-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}"
        student = pt and idx not in (20, 25)
        rec: dict[str, Any] = {
            "staff_id": sid,
            "display_name": NAMES[idx - 1],
            "age": rng.randint(int(cfg["generated_staff_min_age"]), 23) if student
            else rng.randint(22, 52),
            "is_student": student,
            "institution": institutions[idx % 3] if student else None,
            "home_area": next(o["area"] for o in OUTLETS if o["outlet_id"] == home),
            "home_outlet": home,
            "contract_type": "part_time" if pt else "full_time",
            "employee_class": emp_class,
            "monthly_basic_sgd": None if pt else SALARY_PINS.get(
                idx, rng.choice([2600, 2800, 3200, 3800]) if emp_class == "workman"
                else rng.choice([2200, 2300, 2400, 2500, 2600])),
            "hourly_basic_sgd": float(rng.choice([11.5, 12.0, 12.5, 13.0, 13.5, 14.0])) if pt else None,
            "weekly_contract_hours": rng.choice([16, 24]) if pt else 40,
            "normal_daily_hours": 8,
            "skills": skills,
            "fsc_l1_passed_on": fsc,
            "keyholder": idx in KEYHOLDERS,
            "channel": "sim",
            "past_acceptance_rate": 0.98 if idx == 4 else round(rng.uniform(0.55, 0.93), 2),
            "synthetic": True,
        }
        out.append(rec)
    return out


def _shift(sid: str, outlet: str, station: str, day: date, stype: str, n: int) -> dict[str, Any]:
    a, b, brk = SHIFT_TYPES[stype]
    d = day.isoformat()
    return {
        "shift_id": f"shf_{n:05d}", "outlet": outlet, "station": station, "staff_id": sid,
        "start": f"{d}T{a}:00+08:00", "end": f"{d}T{b}:00+08:00",
        "breaks": [{"start": f"{d}T{brk}:00+08:00", "duration_min": 45}],
        "status": "scheduled", "synthetic": True,
    }


def _roster(rng: random.Random, staff: list[dict[str, Any]],
            personas: dict[str, dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, set[date]]]:
    shifts: list[dict[str, Any]] = []
    rest_days: dict[str, set[date]] = {}
    days = [WINDOW_START + timedelta(days=i) for i in range((WINDOW_END - WINDOW_START).days + 1)]
    # Light weeks (leave) for three full-timers in the week of 2 Nov: they have spare hours.
    leave = {
        "stf_019": {date(2026, 11, 5), date(2026, 11, 6)},
        "stf_022": {date(2026, 11, 7), date(2026, 11, 2)},
        "stf_008": {date(2026, 11, 5), date(2026, 11, 6)},
    }
    for rec in staff:
        sid, idx = rec["staff_id"], int(rec["staff_id"][4:])
        home = rec["home_outlet"]
        fsc = rec["fsc_l1_passed_on"]
        fsc_ok = bool(fsc) and date.fromisoformat(fsc).replace(year=int(fsc[:4]) + 5) >= WINDOW_END
        primary = [s for s in ("barista", "kitchen", "cashier")
                   if s in rec["skills"] and (fsc_ok or s == "cashier")]
        rest_days[sid] = set()
        if rec["contract_type"] == "full_time":
            pat = _ft_pattern(rng, idx)
            for day in days:
                if idx == 6:
                    worked = _gloria_works(day)
                    if not worked and day in (date(2026, 10, 23), date(2026, 11, 6), date(2026, 11, 15)):
                        rest_days[sid].add(day)
                else:
                    if day.weekday() == pat["rest_weekday"]:
                        rest_days[sid].add(day)
                        continue
                    worked = day.weekday() != pat["off_weekday"] and day not in leave.get(sid, set())
                if worked:
                    station = primary[(day.toordinal() + idx) % len(primary)]
                    if sid == "stf_011" and day == date(2026, 11, 3):
                        station = "barista"
                    shifts.append(_shift(sid, home, station, day, pat["type"], 0))
        else:
            n_days = int(rec["weekly_contract_hours"]) // 8
            stype = rng.choice(["AM", "PM"])
            a, b, _ = SHIFT_TYPES[stype]
            week = WINDOW_START
            while week <= WINDOW_END:
                candidates = []
                for i in range(7):
                    day = week + timedelta(days=i)
                    start = datetime.fromisoformat(f"{day.isoformat()}T{a}:00+08:00")
                    end = datetime.fromisoformat(f"{day.isoformat()}T{b}:00+08:00")
                    if not any(b0 < end and b1 > start for b0, b1 in busy_blocks(personas[sid], start)):
                        candidates.append(day)
                for day in sorted(rng.sample(candidates, k=min(n_days, len(candidates)))):
                    station = primary[(day.toordinal() + idx) % len(primary)]
                    shifts.append(_shift(sid, home, station, day, stype, 0))
                week += timedelta(days=7)
    shifts.sort(key=lambda s: (s["start"], s["outlet"], s["station"], s["staff_id"]))
    for n, s in enumerate(shifts, start=1):
        s["shift_id"] = f"shf_{n:05d}"
    return shifts, rest_days


def _gloria_works(day: date) -> bool:
    """stf_006: 11 days since the last rest day on 3 Nov (§8.2 step 5).

    Rest day 23 Oct, then worked 24 Oct - 2 Nov, off 3 Nov, works 4-5 Nov, rest day 6 Nov.
    Covering 3 Nov would make 13 consecutive days (SG-EA4-REST-DAY).
    """
    return day not in GLORIA_DAYS_OFF


# Rest days 23 Oct, 6 Nov, 15 Nov; days off 3, 7, 8, 14 Nov. The week of 26 Oct has no day off:
# that historical irregularity is what the §8.2 "11 days since the last rest day" record implies.
GLORIA_DAYS_OFF = {date(2026, 10, 23), date(2026, 11, 3), date(2026, 11, 6), date(2026, 11, 7),
                   date(2026, 11, 8), date(2026, 11, 14), date(2026, 11, 15)}


def _ledgers(rng: random.Random, staff: list[dict[str, Any]],
             rest_days: dict[str, set[date]]) -> dict[str, dict[str, Any]]:
    out = {}
    for rec in staff:
        sid = rec["staff_id"]
        for month in ("202610", "202611"):
            if rec["contract_type"] == "full_time":
                ot = rng.randint(0, 36) if month == "202610" else rng.randint(0, 10)
            else:
                ot = 0
            if sid == "stf_004" and month == "202611":
                ot = 70  # §8.2 step 5: one person at 70 of 72 overtime hours
            if sid == "stf_006" and month == "202610":
                ot = 36
            lid = f"{sid}_{month}"
            out[lid] = {
                "ledger_id": lid, "staff_id": sid, "month": f"{month[:4]}-{month[4:]}",
                "ot_hours_used": ot,
                "rest_days": sorted(d.isoformat() for d in rest_days[sid]
                                    if d.strftime("%Y%m") == month),
                "cover_requests_14d": rng.choice([0, 0, 1, 1, 2, 3]) if month == "202611" else 0,
                "synthetic": True,
            }
    return out


def _travel() -> dict[str, Any]:
    # Placeholder minutes, NOT Routes API data (§3.8 step 7, docs/OPEN_ITEMS.md).
    o2o = {("bugis", "tampines"): 28, ("bugis", "jurong_east"): 32, ("tampines", "jurong_east"): 48}
    matrix = {}
    for a in OUTLETS:
        for b in OUTLETS:
            x, y = a["outlet_id"], b["outlet_id"]
            matrix[f"{x}->{y}"] = 0 if x == y else o2o.get((x, y), o2o.get((y, x)))
    return {"source": "placeholder-not-routes-api", "retrieved_at": None, "generated_at": GENERATED_AT,
            "note": "Placeholder travel minutes. Not Google Maps Routes API data. See docs/OPEN_ITEMS.md.",
            "outlet_to_outlet_min": matrix, "synthetic": True}


def build_synthetic_dataset(
    seed: int = 42,
    data_dir: Path = Path("data"),
    golden_dir: Path = Path("evals/datasets/golden"),
    heldout_dir: Path = Path("evals/datasets/heldout"),
    golden_count: int = 60,
    heldout_count: int = 40,
    with_scenarios: bool = True,
) -> dict[str, Any]:
    cfg = load_company_config()
    rules = load_rules()
    rng = random.Random(seed)

    outlets = [dict(o, opening_hours={"open": "07:00", "close": "21:00"}, stations=STATIONS,
                    keyholders=[], synthetic=True) for o in OUTLETS]
    staff = load_staff(_staff(rng, cfg), rules, cfg)
    personas = {s["staff_id"]: make_persona(s, random.Random(f"{seed}:persona:{s['staff_id']}"),
                                            seed * 1000 + int(s["staff_id"][4:]))
                for s in staff}
    shifts, rest_days = _roster(rng, staff, personas)
    # CO-OPENER-KEYHOLDER must hold for the base roster: if nobody opening an outlet on a day
    # holds a key, the first opener that day becomes a key-holder.
    by_id = {s["staff_id"]: s for s in staff}
    for o in OUTLETS:
        for s in shifts:
            if s["outlet"] != o["outlet_id"] or not s["start"].endswith("T07:00:00+08:00"):
                continue
            openers = [x for x in shifts if x["outlet"] == s["outlet"] and x["start"] == s["start"]]
            if not any(by_id[x["staff_id"]]["keyholder"] for x in openers):
                by_id[openers[0]["staff_id"]]["keyholder"] = True
    for o in outlets:
        o["keyholders"] = [s["staff_id"] for s in staff
                           if s["keyholder"] and s["home_outlet"] == o["outlet_id"]]
    ledgers = _ledgers(rng, staff, rest_days)
    travel = _travel()
    staff_to_outlet = {
        s["staff_id"]: {o["outlet_id"]: 16 if o["outlet_id"] == s["home_outlet"]
                        else travel["outlet_to_outlet_min"][f"{s['home_outlet']}->{o['outlet_id']}"]
                        for o in OUTLETS}
        for s in staff
    }
    travel["staff_to_outlet_min"] = staff_to_outlet

    data_dir.mkdir(parents=True, exist_ok=True)
    files = {"outlets.json": outlets, "staff.json": staff, "shifts.json": shifts,
             "ledgers.json": ledgers, "sim_personas.json": personas, "travel_cache.json": travel}
    for name, payload in files.items():
        (data_dir / name).write_text(json.dumps(payload, indent=1, ensure_ascii=False) + "\n",
                                     encoding="utf-8", newline="\n")

    summary: dict[str, Any] = {
        "outlets": len(outlets), "staff": len(staff), "shifts": len(shifts), "ledgers": len(ledgers),
        "personas": len(personas), "travel_source": travel["source"],
    }
    if with_scenarios:
        from datagen.scenarios import write_scenarios

        summary.update(write_scenarios(seed, data_dir, golden_dir, heldout_dir, golden_count,
                                       heldout_count, cfg, rules))
    return summary
