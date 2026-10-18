# Decision 0018: Local dev server for end-to-end runs

- **Date:** 2026-10-18
- **Related:** decision 0010 (local verification)

## Decision
- `python -m evals.runners.dev_server --port 8080` serves the real `api` app on the memory store,
  with every golden scenario seeded. Each `POST /gaps` starts `coverage-cascade` in a background
  thread using the local driver with an **external lead**: the workflow waits on its callback queue
  for the browser's approval and fallback taps (as Cloud Workflows waits on callback endpoints), and
  times out to the YAML's own timeout paths (`cancel_no_approval`, `resolve_unfilled`).
- Simulated time jumps to the next reply or timeout, paced by `--pace` real seconds per step so a
  viewer can follow it. A new scenario resets the simulated clock to its `now`.
- Internal routes are open on this server (no workflow identity locally), so it binds to 127.0.0.1.
- Limits: one shared roster in memory. Since decision 0023, scenario gaps commit to their own overlay,
  so re-running a scenario gives the same plan; lead-reported gaps still change the roster.
- `web/playwright.config.ts` starts this server and the Vite dev server for the end-to-end check.
