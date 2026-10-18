# Decision 0011: Fan-out with one callback endpoint per offer

- **Date:** 2026-10-18
- **PDF sections:** §5.2, §5.4; KICKSTART §4.4

## Context
KICKSTART asks to check whether one callback endpoint can receive several requests. The Workflows page
"Create callback endpoints" (docs.cloud.google.com/workflows/docs/creating-callback-endpoints, last updated
2026-10-13) says "a single callback slot is available to the workflow"; for requests sent before
`await_callback` "only the first request is accepted and returned", and a second callback can get
HTTP 429 or be stored and never processed.

## Decision
- Every round of offers (one offer, or `fanout_n` at once) runs in a `parallel` for-loop. Each branch creates
  its own callback endpoint, registers its offer, and awaits it. Shared variables: `winner`, `cancelled_flag`.
- "First valid yes wins" is decided in `api` (`POST /internal/accept`), in one transaction: the first complete
  acceptance moves the gap to COMMITTING and withdraws the other open offers. `api` then posts
  `{withdrawn: true}` to their callback endpoints so those branches end at once, and sends courtesy
  withdrawals (covered by the plan's approval).
- A branch that loses the race gets `{won: false}`; a reply that arrives after the outcome gets a courtesy
  message from `api` without touching state.
- `HttpCallbacks` retries on HTTP 429 (single slot busy).

## Not verified
`next: continue` inside a `parallel` for-loop and the exact parallel semantics are from the Workflows syntax
as I know it, not from a run. The first deploy will validate the YAML (TODO-VERIFY in docs/OPEN_ITEMS.md).
