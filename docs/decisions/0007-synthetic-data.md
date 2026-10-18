# Decision 0007: Synthetic data shape

- **Date:** 2026-10-18
- **PDF sections:** §2.1, §8.1, §8.2, §8.3, §8.4, §8.5

## Decision
- **Staff:** 33 people. 20 full-time (one `manager_executive`) and 13 part-time is 61/39, the closest
  split to the 60/40 design default. Four workmen. Three people are outside Part 4: two
  non-workmen above S$2,600 and one workman above S$4,500. Most part-timers are students aged 17–23
  (polytechnic, ITE, university).
- **Full-time pattern:** 40 contract hours, 8 normal daily hours, five 8-hour shifts a week (AM
  07:00–15:00 or PM 13:00–21:00, with one 45-minute break), one designated rest day and one day off.
  Each person keeps one shift type, so every turnaround is at least 11 hours.
- **Roster window:** 19 Oct to 15 Nov 2026, not just "month to date plus 7 days" (KICKSTART §3.8).
  The longer window lets the engines compute consecutive-day runs (SG-EA4-REST-DAY) from data. It
  includes the §8.2 record of 11 days since the last rest day.
- **Timetables and exam weeks** live in the `sim` personas (`hidden_availability`). They drive
  the part-timers' rostered days and their replies. The planner never sees them (§8.1).
- **Pinned records** (all synthetic): `stf_004` at 70 of 72 overtime hours with a full 40-hour week,
  and `stf_006` with 11 days since the last rest day (her week of 26 Oct has no day off; this is the
  §8.2 trap, not a pattern the planner would create). For `S-017`, `stf_019`, `stf_022` and `stf_008`
  have a light week (leave), so they can cover at no overtime cost, and `stf_011` opens Bugis that day.
- **Base roster legality:** a test checks every shift in the scenario week against every hard rule.
  Where no key-holder opened an outlet on a day, the generator makes that day's first opener a
  key-holder.
- **Travel:** no Routes API key is used (unattended run, no paid APIs). `data/travel_cache.json` is a
  clearly flagged placeholder (`source: placeholder-not-routes-api`, `retrieved_at: null`):
  16 min within the home outlet, outlet to outlet 28/32/48 min.
- **Scenarios:** 60 golden (with `S-017` exactly as §8.4, and `S-002` "Nobody replies" for J3) and 40
  held-out. Every absence is a real rostered shift. `expect` comes from `evals.cascade_sim` with a
  10-second time limit.

## Alternatives
- Exactly 30 staff. Rejected: with 18 shift slots a day, 30 people cannot keep weekly rest days and
  fill the roster.
