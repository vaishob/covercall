# Decision 0026: Parse retries, logged parse errors and a configurable parse backend

- **Date:** 2026-10-21
- **PDF sections:** §7.3 (structured reply parsing), §7.1 (model records)

## Problem
On 21 Oct, gemini-3.8-flash on Vertex `global` failed about 75-90% of calls (504 DEADLINE_EXCEEDED, 429,
500); on 18 and 20 Oct, 18-39%. Each failure was swallowed into `unclear`, which fails closed to a decline,
so S-017 escalated on every revision. Nothing recorded why.

Measured (local, synthetic texts):
- The SDK sends `X-Server-Timeout` = the client timeout (8 s); Vertex returns 504 about 3.4 s earlier
  (4.6 s with 8 s; 26.5 s with 30 s). The 4.5-5 s spike in `/internal/reply` latency is that deadline.
- Thinking is on by default (121-342 thought tokens). `thinking_level=MINIMAL` is refused (400);
  `thinking_budget=0` works but did not help while capacity was short.
- No fixed project quota (dynamic shared quota): the 429s are shared-capacity contention.
- The model is not served on Vertex `asia-southeast1` or `us-central1` (404).
- Interleaved, 12 s timeout, n=12: Vertex global 1/12, Developer API 12/12 (median 3.6 s).

## Decision
- **Retries:** transient codes (429, 500, 503, 504) are retried with 0.5 s then 1.5 s backoff, at most
  3 attempts, and only while the next attempt fits a **30 s total budget** (the workflow allows 60 s per
  call and retries on its own). Other errors are not retried. The single retry on invalid output stays.
- **Attempt timeout:** 9 s on Vertex (about 5.6 s of model time after the server margin; worst case
  29 s). The Developer API refuses deadlines under 10 s (400), so it gets 10 s.
- **Logging:** every failed attempt logs the error class and HTTP code, the attempt and the elapsed time,
  never the staff text. `parse_error`, `parse_attempts` and `parser_backend` are stored with the parse
  and reach the outcome event, so a decline caused by a model error is visible in the trace.
- **Backend:** `PARSER_BACKEND=vertex` (default, unchanged) or `developer` (the same pinned model on the
  Gemini Developer API, `v1beta`, keyed by the existing `GEMINI_API_KEY` secret). Every parse records
  `parser_backend` on its outcome event. persona-sim stays on Vertex; on error it already falls back to
  template text.
- **Unchanged:** an error, an invalid output or confidence below `parse_confidence_min` is `unclear`,
  never an accept. No stub-parser fallback.

## Consequences
- A parse can take up to about 30 s instead of 8 s. The cascade waits for it; deadlines are days away.
- Production uses `developer` (`infra/40_deploy_services.sh` default). `/status` reports the agent role
  as `gemini_developer_api` / `v1beta` when that backend runs, and the evidence page and README say so.
- Tests: `tests/test_gemini.py` (retries, budget, logging, backends, the event payload).
