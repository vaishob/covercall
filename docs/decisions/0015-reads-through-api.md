# Decision 0015: The browser reads only through `api`; client-safe projections

- **Date:** 2026-10-18
- **Departs from:** design doc §4.1 ("Reads live state from Firestore with read-only security rules")
  and §11.1 (Firebase JS SDK listeners).
- **Decided by:** the author (task brief for `feat/web-contract`).

## Decision
- The web app has **no Firestore access**. `infra/firestore.rules` is deny-all for clients on
  `(default)` (and `sim` was already deny-all). Services use IAM, which bypasses rules.
- Every read goes through `api` routes that return **projections built server-side, field by field**
  (`services/api/app/views.py`): `GET /status`, `/scenarios`, `/gaps/{id}`, `/gaps/{id}/events`
  (with the `verify_chain` result), `/gaps/{id}/quarantine` (redacted only), `/gaps/{id}/approval`,
  `/evals`.
- No projection contains an approval nonce, a callback URL, raw staff or lead text, or unredacted
  PII. The one exception is `GET /gaps/{id}/approval`, which returns the read-back and nonce only
  while an approval is pending; otherwise it answers `{"pending": false}` (200, so a poll that races
  an approval is not logged as an error).
- The nonce moved out of the readable gap document into the server-only `server/{gapId}` document.
  Raw lead text no longer goes into the `gap.reported` event payload (it stays in `inputs/`, read
  only by the guard).
- CORS allows only the origins in `ALLOWED_ORIGINS` (comma-separated; default
  `http://localhost:3000`). A wildcard is refused at start-up.
- `tests/test_read_routes.py` runs both journeys, calls every read route after every workflow step,
  and asserts that no response contains a nonce (except `/approval` while pending), a callback URL
  or any raw reply or lead text.

## Why
No client security rules to maintain or get wrong; secrets and raw text are unreachable from the
browser by construction; and the whole read path is testable locally.

## Cost
The UI polls every 2 seconds instead of receiving live snapshots, and `api` (min instances 1) serves
every read.
