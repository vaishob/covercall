# Decision 0025: A constant demo-clock offset for deadlines

- **Date:** 2026-10-21
- **PDF sections:** §5.2 (timing), §11.3 (demo journeys)

## Problem
The demo roster's shifts are fixed on 3-8 Nov 2026 and production runs on the real clock. From
3 Nov 06:19 SGT (07:00 minus travel, the 10 min buffer and the 15 min escalation lead), S-017 and
the voice report for "Tuesday, 3 November" escalate the moment they are approved, and never fill.
From 4 Nov 06:19, "Nobody replies" escalates without sending an offer. Judging runs to 6 Nov.

## Decision
- `DEMO_CLOCK_OFFSET_DAYS` (whole days, 0-30; unset = 0 = the real clock) moves the api's
  **decision clock** back: `Api.decision_now() = clock.now() - offset`. Production sets 7, so up
  to 6 Nov 23:59 the decision clock reads at most 30 Oct 23:59, more than 3 days before the first
  demo deadline. Every journey then behaves as it did on 20-21 Oct: single offers, countdowns in
  days, the same plans.
- The decision clock is used only where "now" decides something: the solver's arrival check and
  `arrival` (`planner_context`), the t_esc lock at approval, `next_offers` (windows, fan-out,
  escalation) and the countdown in `GET /gaps/{id}`.
- Everything else stays on the real clock: event `ts` (so trace replay shows real times),
  `reported_at`, `filled_at`, offers' `sent_at`, approvals, `clock.now` in the gap view, live-token
  expiry, a voice report given as "HH:MM" (still today's real date), persona-sim and the workflow
  (neither reads the time; waits are `window_s_real`). Whole days keep every time of day unchanged,
  and the screen shows times only.
- Each gap records `clock_offset_s`. `escalation_late` and the local driver's late-arrival count
  subtract it, because they compare a real timestamp with a decision-clock deadline.
- Month logic (the overtime ledger month, the Part 4 checks) keys on the gap's shift date, never on
  "now", so the decision clock falling in October changes nothing.

## Rejected
- A per-gap scenario clock (`scenario.now + (real - reported_at)`): it brings fan-out and minute
  countdowns, which never ran in production, and it does not fix the voice report. With `x60`
  compression it would also escalate S-017 before a judge can tap Approve.
- Regenerating the data with later dates: a large data diff, possible changes to eval numbers,
  and a production re-seed.

## Limits
- With offset 7 the demo works until 10 Nov 06:19 SGT. Unset it, or regenerate the data, after
  judging.
- Tests: `tests/test_demo_clock.py`.
