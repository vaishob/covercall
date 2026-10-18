# Decision 0016: Backend shapes are the source of truth; one mapping layer; contract fixtures

- **Date:** 2026-10-18
- **PDF sections:** §8.1 (canonical names), §11.3, §11.4

## Decision
- The §8.1 field names and shapes the backend writes are canonical. The frontend adapts.
- `web/src/data/backendTypes.ts` mirrors the read-route responses exactly. `web/src/data/viewModel.ts`
  is the only place that maps them for display: cents to SGD text, `gap_id`/`plan_id` IDs, split plans
  (every segment with its own person, times, breaks and arrival), rule checks as objects, rejected
  rules with rule ID, message, source URL, publisher and section from the rule spec, and the rule
  **kind** (hard rule, data gate, soft) instead of P0/P1/P2 (those are eval-metric severities, §10.1).
  Breaks are start plus duration. It contains no legality, cost, deadline or ranking logic.
- Where the UI needed something the backend did not have, the backend adds it:
  `saves_vs_naive_cents` per ranked plan (decision 0014's comparator: the naive first pick, priced by
  the validator; can be negative; shown as "vs the usual first pick", synthetic wages), display
  names, `t_esc_locked` as the countdown target and `seconds_to_escalation` computed by the server.
- **Contract fixtures:** `python -m evals.runners.capture_fixtures` runs S-017 and S-002 locally and
  records the real responses after every step into `web/src/data/__fixtures__/`. Frontend tests map
  them and assert the lead view model; `tests/test_read_routes.py` asserts the backend still produces
  them byte for byte. A shape change on either side breaks a test.
