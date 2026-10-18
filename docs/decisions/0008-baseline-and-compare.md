# Decision 0008: Baseline behaviour and the Slice 1 comparison

- **Date:** 2026-10-18
- **PDF sections:** §2.5, §3.9 (KICKSTART), §10.2

## Decision
- **"Free"** means: not the absent person, not the manager, and not on a shift that overlaps the gap.
- **Station skill:** the baseline only asks people who hold the station's skill. A manager would not
  ask a cashier-only person to run the barista station. This makes the baseline stronger and the
  comparison more conservative. It does no cost, overtime, rest-day, certificate or travel reasoning.
- **Counter-offers:** the baseline treats "can do 9 not 7" as a no (it wants the whole shift).
- **Same inputs:** both arms use the same scenario, personas, overrides and seeds
  (`datagen.personas.decide_reply`).
- **Slice 1 cascade (`evals/cascade_sim.py`):** untimed. Silence counts as a timeout, a decline
  excludes the person, and a counter-offer becomes an availability window and a re-solve.
- **No time to fill in Slice 1.** The previous build used invented minute constants (and different
  ones for each arm). Time to fill comes from the timed Slice 2 cascade only.
- **Reported metrics:** gaps filled, median and total overtime cost (SG-EA4-OT-RATE + rest-day pay +
  part-time 1.5× hours), total incremental labour cost, hard-rule violations, solver/validator
  disagreements, and results differing from each scenario's `expect`. Exit 1 if CoverCall has any
  violation or disagreement, or differs from `expect`.

## Known asymmetries (stated plainly)
- The baseline ignores travel and reply time, so it can "fill" a gap with someone who could not
  arrive with the 10-minute buffer. CoverCall refuses those (golden S-013, S-038).
- Staff outside Part 4 cost S$0 in both arms (no statutory overtime). CoverCall's objective prefers
  them when they are free. Their contractual pay is not modelled.
