# Decision 0006: CP-SAT formulation, objective weights and determinism

- **Date:** 2026-10-18
- **PDF sections:** §3.5 (KICKSTART), §6.3, §6.4

## Decision
- **Options.** The gap `[S, E]` is staffed either by one person (`full`) or by two people split at a
  grid point `t` (`first = [S, t]`, `second = [t, E]`). Grid `split_granularity_min = 30` and minimum
  segment `min_segment_min = 120` are design defaults in `policy/company.yaml`. `max_segments = 2` (PDF).
- **Variables.** `x[person, option]` booleans; `split[t]` booleans; `used[person] = Σ x[person, ·] ≤ 1`.
  Coverage: `Σ x[·, full] + Σ split[t] = 1`, and for each `t`, `Σ x[·, first_t] = Σ x[·, second_t] = split[t]`.
- **Rules.** Each hard rule compiles to one or more named constraints `coef · x ≤ bound`
  (for example `(ot_used + ot_added) · x ≤ 72 h` and `day_hours · x ≤ 12 h`, in minutes). `coef` is
  computed from the rule params and the person's facts for that option. Cost rules contribute
  integer-cent objective coefficients. Arrival viability (`now + travel + buffer ≤ start`, §5.2) and
  counter-offer windows are separate constraints named `arrival:` and `window:`, not rules.
- **Objective** (integer cents, lexicographic by scaling):
  `K1 · (w_cost · cost + w_fairness · fairness_excess + w_disruption · [split]) + K2 · tie_rank + option_index`.
  Weights (design defaults, chosen): `cost = 1` per cent; `fairness = 500` cents per cover request
  beyond `fairness.max_covers`; `disruption = 300` cents per extra person in a split (the plan never
  moves other people's shifts, so splitting is the only disruption it can cause).
  Tie-break `tie_rank` = order by (travel minutes, staff_id): among equal-cost plans the nearer
  person is offered first. This is a determinism device, not a cost.
- **Top-k.** After each solve, a cut `Σ used[p] ≤ |P| − 1` over the plan's people `P` forbids the same
  set of people again, so the up to `top_k_plans = 3` plans use distinct people.
- **Determinism.** `num_search_workers = 1`, `random_seed = solver_seed` (or the scenario seed),
  `max_time_in_seconds = solver_time_limit_s`. Scenario labels use `offline_time_limit_s = 10`.
- **Cross-checks inside `solve`.** For every pool member's full-gap assignment, the set of failing
  compiled constraints must equal the validator's blocking rule IDs. For every ranked segment, the
  validator must find no blocking violation and the same cost lines. Any difference raises
  `PlanDisagreement` (P0, `plan.disagreement` → `HELD`).

## Alternatives
- Model the split time as an integer variable with piecewise overtime terms. Rejected for today:
  more surface for compiler bugs, and the 30-minute grid gives at most 25 options per person.
- Tie-break by staff_id only. Rejected: it favours low IDs, which has no operational meaning.
