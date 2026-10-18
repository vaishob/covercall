# CoverCall web app (`web/`) — handoff

Owner: Claude Code (see the first line of `docs/HANDOFF.md`). This replaces the Slice 3–4 import
handoff; that history is in git (`f42c748` and earlier) and in `docs/HANDOFF.md`.

## 1. Architecture

- The browser reads **only** through the `api` service's client-safe routes (decision 0015). It has
  no Firestore access; `infra/firestore.rules` is deny-all.
- The backend's §8.1 shapes are canonical (decision 0016). `src/data/backendTypes.ts` mirrors the
  responses exactly; `src/data/viewModel.ts` is the **only** place that maps them for display.
  There is no legality, cost, deadline or ranking logic in the browser: every number shown is a
  field the server computed (cents, `saves_vs_naive_cents`, `seconds_to_escalation`, rule results).
- `src/data/source.ts`:
  - `LiveSource` polls `GET /gaps/{id}` (plus `/approval` and `/quarantine`) every 2 s and stops on
    a terminal state (`FILLED`, `RESOLVED`, `CANCELLED`). Errors go to `onError` and are shown as
    errors; there is no fallback to recorded data.
  - `ReplaySource` (when `VITE_API_BASE_URL` is unset) plays the contract fixtures — real responses
    recorded from the local cascade — badged "Recorded replay — not live". `canAct` is false and
    every state-changing action is refused (decision 0017).

## 2. Routes the client calls (`src/data/apiClient.ts`)

| Method | Path | Used for |
|---|---|---|
| GET | `/status` | guard and parser implementation, model IDs, time scale |
| GET | `/scenarios` | the scenario launcher (S-017, S-002) |
| POST | `/gaps` `{scenario_id}` | start a scenario |
| POST | `/gaps` (lead input) | voice `report_absence`; may answer `{status: "clarify", question, candidates}` |
| GET | `/gaps/{id}` | the lead view model (gap, clock, plan, offers, committed cover) |
| GET | `/gaps/{id}/events` | trace view: events plus the server's `verify_chain` result |
| GET | `/gaps/{id}/quarantine` | redacted quarantined replies |
| GET | `/gaps/{id}/approval` | read-back and nonce, only while pending (`{pending: false}` otherwise; mapped to `null`) |
| POST | `/approvals` `{gap_id, plan_id, nonce, decision, channel, transcript?}` | approve / reject |
| POST | `/fallbacks` `{gap_id, option}` | escalation choice: `borrow`, `reduced_service`, `lead_covers`, `agency`, `unfilled` |
| POST | `/gaps/{id}/cancel` | cancel; the UI shows "cancel requested" until the state is `CANCELLED` |
| GET | `/evals` | currently `no_eval_run` (BigQuery is Slice 6) |
| POST | `/live/token` | voice; the server answers 501 until Slice 4, and the UI falls back to text |

## 3. Files

| Path | Purpose |
|---|---|
| `src/App.tsx` | Routes `/`, `/evals`, `/trace/:gapId`, `/about`; wires every tap path to the source |
| `src/data/backendTypes.ts` | Exact response DTOs and `TERMINAL_STATES` |
| `src/data/viewModel.ts` | `toLeadView`, `toTraceView`, cents to SGD text, rule-kind and fallback labels, split plans, breaks as start plus duration |
| `src/data/source.ts` | `LiveSource`, `ReplaySource`, `createSource` |
| `src/data/apiClient.ts` | `ApiClient`, `ApiError`, `apiBaseUrlFromEnv` |
| `src/data/__fixtures__/s017.json`, `s002.json` | Contract fixtures (one recorded snapshot per workflow step) |
| `src/voice/` | Voice provider interface, the five §7.2 tools forwarded to `ApiClient`, fallback chain hands-free → push-to-talk → text |
| `src/components/` | Lead view components; `ReplayBadge` / `ReplayBanner` mark replay data |
| `src/utils/formatters.ts` | Pure display formatting (times, SGD text, throttled countdown announcements) |
| `e2e/lead.spec.ts`, `playwright.config.ts` | End-to-end check, tap only, against the local api and Vite |

## 4. Environment

| Variable | Effect |
|---|---|
| `VITE_API_BASE_URL` | The `api` URL. Locally `http://127.0.0.1:8080`. Unset → recorded replay, badged, actions disabled. |

No other client variables. No secrets go to the browser. Model IDs come from `GET /status`, which
reads `config/models.yaml` (pinned 2026-10-18 except `guard`; voice tokens are `v1beta`, decision 0019).

## 5. Tests

```
npm test             # node --test: view model over the fixtures, sources, api client, voice tools, formatters (27 tests)
npm run build        # tsc --noEmit && vite build
npx playwright test  # starts python -m evals.runners.dev_server and Vite itself (2 tests)
```

The Playwright run checks, by tapping only: S-017 reaches FILLED with no replay badge; Nobody
replies reaches ESCALATED, then RESOLVED after a fallback tap; no console errors; axe-core reports no
serious or critical issue on `/`, `/trace/:gapId` and `/evals`.

After an intended backend shape change, regenerate the fixtures from the repo root with
`python -m evals.runners.capture_fixtures`; `tests/test_read_routes.py` fails if they drift.

## 6. Open

- Voice (Slice 4): no audio session yet; `/live/token` is 501.
- `/evals` shows "no eval run" until BigQuery results exist (Slice 6).
- The adversarial scenario (J4) is not offered: there is no backend scenario or guard model yet.
- Polling every 2 s, not live listeners (decision 0015).
- Not deployed. Hosting needs `VITE_API_BASE_URL` at build time, and `api` needs the Hosting origin
  in `ALLOWED_ORIGINS`.
