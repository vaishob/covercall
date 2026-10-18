# Decision 0005: Rule semantics shared by the solver and the validator

- **Date:** 2026-10-18
- **PDF sections:** §6.1, §6.2, §6.3, §8.1, §15.2
- **Sources re-checked 2026-10-18:** MOM "Hours of work, overtime and rest day" (updated 24 July 2025),
  MOM "Employment Act: who it covers" (24 July 2025), MOM "Overtime for part-time employees"
  (25 July 2025), MOM "Who is a part-time employee" (29 July 2024), MOM "Monthly and daily salary"
  (8 Dec 2025), SFA "WSQ Food Safety Course (FSC) Level 1" (24 Aug 2026).

## Context
§6.3 needs two independent implementations of every rule that share only the YAML specs.
The PDF states each rule in one sentence. To compile one sentence twice and get the same answer,
the facts each rule reads (hours that day, overtime added, consecutive days) must be defined once,
in prose. This file is that definition. `policy/compile_cpsat.py` and `policy/validate.py` each
implement it in their own code. They share no Python.

## Inputs (plain dicts, §8.1 fields)
`staff`, `shifts`, `ledgers`, `outlets`, `travel`, `company` (= `policy/company.yaml`), the `gap`,
and an assignment `{staff_id, start, end, breaks[]}`. Times are ISO 8601 with `+08:00`.

## Common definitions
- **D** = the local calendar date of the assignment start. A shift belongs to the date it starts on.
- **Hours of work** for a shift = `end - start`, *including* its breaks. This is stricter than the
  statute for every limit (12 h, 72 h, 11 h) and charges the same overtime to CoverCall and the baseline.
- **Existing shifts** of a person = their shifts with `status: scheduled`.
- **Rest days** = the union of `rest_days[]` in all of the person's ledgers.
- **Ledger** for the month = `ledgers/{staffId}_{YYYYMM}` of D. A missing ledger is a data error.
- **monthly basic**: `monthly_basic_sgd`; for hourly-rated staff,
  `hourly_basic_sgd × weekly_contract_hours × 52 / 12`.
- **monthly_rated** = `monthly_basic_sgd` is set.
- **part4_covered** (SG-EA4-COVERAGE, computed, never stored): false for the excluded classes;
  workman → monthly basic ≤ 4,500; everyone else → monthly basic ≤ 2,600.
- **is_rest_day** = D is one of the person's rest days.
- **is_opening** = the assignment starts at the outlet's `opening_hours.open` on D.
- **food_handling** = the gap station's `food_handling` flag in the outlet's `stations[]`.
- Missing data (age, salary, ledger, outlet) is a data error and fails closed. Neither engine
  substitutes a default.

## Facts (minutes)
- `seg` = assignment length. `day_before` = existing hours on D. `day_after = day_before + seg`.
- `nd` = `normal_daily_hours × 60`. `wn` = `min(weekly_contract_hours, 44) × 60`.
- **Overtime added** `ot`:
  - rest day, or part-timer: `max(0, day_after − nd) − max(0, day_before − nd)`
    (MOM: rest-day hours count only beyond the usual daily hours; part-time overtime is work
    beyond the part-timer's normal daily hours);
  - full-timer on a working day: `daily` as above; `week_before` = existing hours in the
    Monday–Sunday week of D, excluding rest days;
    `weekly = max(0, week_before + seg − wn) − max(0, week_before − wn)`; `ot = min(seg, max(daily, weekly))`.
- **Continuous block** = the assignment merged with existing shifts that touch it end-to-start,
  repeatedly. Breaks in the block = the existing shifts' breaks plus the assignment's breaks.
- **Run** = the longest stretch of consecutive calendar dates containing D on which the person
  works (existing shift dates ∪ {D}). **Week off** = days in D's Monday–Sunday week with no work.

## Rules
| Rule | Status |
|---|---|
| SG-EA4-COVERAGE | `ok` if part4_covered, else `not_applicable` |
| SG-EA4-DAILY-MAX-12H | violation if `day_after > max_daily_hours × 60` |
| SG-EA4-NORMAL-HOURS | cost-only (`ok`); reports `ot` |
| SG-EA4-BREAKS | violation if the longest work stretch in the block (block minus breaks) > 6 h, or the block is longer than 6 h and has < 45 min of breaks |
| SG-EA4-OT-CAP-72 | violation if `ot_hours_used × 60 + ot > 72 × 60` (exactly 72 is allowed) |
| SG-EA4-OT-RATE | cost: `ot × rate × 1.5`, `rate = 12 × monthly / (52 × 44)` per hour; non-workmen capped at S$13.60/h |
| SG-EA4-REST-DAY | violation if `run > 12`, or week off < 1, or the assignment is `compelled` (CoverCall only offers) |
| SG-EA4-REST-DAY-PAY | cost: 1 day's basic pay if `day_after ≤ nd / 2`, else 2 days'; overtime beyond the normal day is charged by SG-EA4-OT-RATE. Day rate = `12 × monthly / (52 × days per week)`, days per week = `weekly_contract_hours / normal_daily_hours` |
| SG-PT-OT-RATE | cost: minutes within the comparable full-timer's day at the basic rate, minutes beyond it at 1.5× |
| SG-SFA-FSC-L1 | violation if `fsc_l1_passed_on` is missing, or D is after `passed_on + 5 years` |
| CO-REST-BETWEEN-SHIFTS | violation if any existing shift overlaps the assignment, or a non-touching shift ends/starts less than `rest_between_shifts_h` from it |
| CO-OPENER-KEYHOLDER | violation if the assignee is not a key-holder and no other key-holder (not the absent person) has a shift at the outlet spanning the opening time |
| CO-STATION-SKILL | violation if the station is not in `skills[]` |
| CO-FAIRNESS | soft violation if `cover_requests_14d + 1 > max_covers`; penalty units = the excess |
| CO-AGE-SCOPE | violation if age is missing or `< min_staff_age` |

`hard` and `data_gate` violations count as rule violations. `soft` violations are penalties only.

## Money
Each cost line is computed as an exact rational number of cents and rounded half up to whole
cents once per line. Breakdown keys: `base_cents` (part-time basic hours), `overtime_cents`
(SG-EA4-OT-RATE plus the part-time 1.5× hours), `rest_day_cents`, `total_cents`.
The headline "overtime cost" is `overtime_cents + rest_day_cents`.

## Planner-owned choices (not legal rules)
- The planner schedules one `meal_break_min` (45 min) break in any segment longer than 6 h, starting
  at the segment's midpoint rounded down to 15 minutes.
- **Candidate pool** (eligibility, not legality): everyone except the absent person, the
  `manager_executive` (the lead; "lead covers" is an escalation fallback in §5.1), and people already
  excluded in this cascade (declined, timed out, flagged).
- **Arrival:** an option is viable only if `now + travel + buffer_min ≤ segment start`.

## Known limits (stated plainly)
- Public holidays are not encoded (§15.2). Demo dates avoid them.
- The shift-worker "continuous 30 hours" rest-day form is not encoded. The weekly day-off check is used.
- Staff outside Part 4 have no statutory overtime cost. Their contractual pay for extra hours is
  not modelled, so the engine sees them as zero incremental cost.
- The ledger's `ot_hours_used` is month to date. Overtime in future rostered shifts is not added.

## Alternatives considered
- Exclude breaks from hours of work. Rejected for now: the MOM page does not say how breaks count
  toward the 12-hour limit, and the stricter count cannot hide a breach.
- Treat a worked rest day as "losing" the rest day for the 12-day interval. Rejected: then any
  rest-day work by a weekly-pattern worker breaches the interval, which contradicts the PDF's
  "CoverCall may only offer it" (rest-day work is allowed when offered).
