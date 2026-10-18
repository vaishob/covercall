# Decision 0014: Commit re-check, lead cancel, approvals, and cost_saved_sgd

- **Date:** 2026-10-18
- **PDF sections:** §5.1, §5.3, §5.4, §7.2, §8.1

## Decision
- **Commit:** `POST /internal/commit` runs one transaction. It reads the roster inside the transaction,
  re-checks every segment with the validator, writes the cover shifts, marks the absent person's shift
  `absent`, and appends `commit.ok` (FILLED). On any violation it appends `commit.conflict`
  (back to OUTREACH, the person excluded, a courtesy reply sent). A repeated call on a FILLED gap returns
  the same result (safe to retry).
- **Cancel:** the api never changes state for a cancel. `POST /gaps/{id}/cancel` posts `{cancel: true}` to
  every open wait (approval, offers, fallback), and the workflow appends `gap.cancelled`.
  "Only the workflow changes state" holds.
- **Approvals (T2):** `approval-request` issues a nonce and the exact read-back sentence. `POST /approvals`
  needs that nonce. With `channel: voice`, only a clear affirmative at the start of the transcript
  ("yes", "approve", "confirm", "go ahead") counts; anything else is recorded as a reject. `plan.approved`
  is refused unless a matching `approve` record exists. Every staff-facing message (offer, courtesy,
  withdrawal, confirmation) is refused without the gap's covering approval, and the scan
  `unapproved_outbound` re-checks every sent message.
- **Approval or fallback never given:** the workflow waits 12 hours, then appends `gap.cancelled` (no approval)
  or `fallback.chosen: unfilled` (actor `system`), so no gap ends without an outcome.
- **`cost_saved_sgd`:** the overtime cost (overtime + rest-day pay, priced by the validator) of the naive
  first pick (the most reliable free person with the station skill, the baseline's rule, using only
  planner-visible data), minus the committed plan's overtime cost. It can be negative. The PDF does not
  define the comparator.
- **Idempotency:** transitions carry an `idempotency_key` (`applied/{key}`), and offers carry a `key`
  (`offer_keys/{key}`), so the workflow's retry policy cannot append an event or send an offer twice.
