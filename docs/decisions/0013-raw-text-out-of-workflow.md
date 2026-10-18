# Decision 0013: Raw text stays out of the workflow; api proxies guard and parse_reply

- **Date:** 2026-10-18
- **PDF sections:** §4.2 and §4.4 (KICKSTART), §7.3, §7.4, §12.1, §12.2

## Decision
- Staff and lead text is stored only in server-side collections (`replies_raw`, `inputs`) that clients
  cannot read (`infra/firestore.rules`). Callbacks carry only `{offer_id, message_id}`.
- The workflow calls `api` (`/internal/guard-input`, `/internal/reply`), which reads the text server-side,
  runs the guard first, quarantines flagged text (redacted) for the lead, and only then runs `parse_reply`.
  The workflow receives labels and the typed §7.3 schema, never the text. So the execution history,
  logs and traces cannot hold raw replies.
- Internal endpoints beyond the three KICKSTART names (`transition`, `solve`, `next-offers`):
  `guard-input`, `approval-request`, `offers`, `reply`, `offer-outcome`, `accept`, `counter`,
  `counter-resolve`, `commit`, `escalation-request`. All require the workflow's OIDC identity.
  Self-loop outcomes (`reply.decline`, `offer.timeout`, `reply.flagged`) go through `offer-outcome`, which
  appends the event only if the gap is still in OUTREACH and the offer is open. A reply that races a winner
  is recorded on the offer, and no illegal transition is attempted.
- Guard failure on a staff reply fails closed: the reply is quarantined as `guard_unavailable` and that
  candidate is skipped (`reply.flagged`). Guard failure on the lead's input sends the gap to HELD.
- `parse_reply` intent `unclear` (or `question`) is treated as a decline for Slice 2. §7.3's pre-approved
  clarifying template is not built yet.
- On Cloud Run the api runs the `stub-v0` parser in-process. The `agent` service is deployable with
  `AGENT_IMPL=stub-v0` but not yet called; it refuses to start with a `TODO-VERIFY` model.
