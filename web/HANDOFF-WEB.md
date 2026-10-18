# CoverCall Frontend Handoff (`web/`) — Slices 3 & 4

All code and files introduced on `gemini/slice-3-frontend` and `gemini/slice-4-web` are restricted exclusively to `web/`. No files outside `web/` were created or modified on either branch.

---

## 1. Branches and Commits

Note: No git remote (`origin`) is configured in the container (`git remote -v` returns empty), so both branches exist as local branches off local `main` (`c3fe4e6`).

- **`main` (base commit, untouched by frontend branches):**
  - `c3fe4e6` — `feat(policy): implement dual CP-SAT compiler, independent validator, and property tests (§3.5-3.7)`
- **`gemini/slice-3-frontend` (branched off `main` at `c3fe4e6`):**
  - `7e80d11` — `feat(web): build Slice 3 Lead View with custom MUI theme and S-017 mock state`
  - `d33aa3e` — `polish(web): refine mobile top bar, compact scenario bar, and sticky approval layout`
- **`gemini/slice-4-web` (branched off `gemini/slice-3-frontend` at `d33aa3e`):**
  - `54d19a8` — `fix(web): step 1 honesty fixes — mock badges, remove S-042/S-058 and policy math, guard stub labels`
  - `4d57ec9` — `feat(web): step 2 data-source seam — types, MockDataSource, FirestoreDataSource, ApiClient, and mock banner`
  - `66a5d99` — `feat(web): step 3 voice provider — LiveVoiceProvider v1alpha ephemeral token, fallback chain, and tool forwarding`
  - `9efa477` — `feat(web): step 4 routes — /evals, /trace/:gapId, and /about bound to DataSource`
  - `6ad00c3` — `test(web): step 5 accessibility & layout polish, .env.example, and honesty assertions`

---

## 2. File Inventory (`web/`)

Every file under `web/` is **new** relative to `main` (`c3fe4e6`):

| File | Status vs `main` | One-line purpose |
| :--- | :--- | :--- |
| `web/.env.example` | New | Documents client-side `VITE_*` environment variables with empty defaults and no secrets. |
| `web/.gitignore` | New | Ignores `node_modules/`, `dist/`, `.vite/`, and `*.tsbuildinfo` inside `web/`. |
| `web/HANDOFF-WEB.md` | New | Frontend handoff specification documenting branches, contracts, env vars, mocks, and build verification. |
| `web/index.html` | New | HTML entry point (`lang="en"`) loading Plus Jakarta Sans and IBM Plex Mono fonts and mounting `/src/main.tsx`. |
| `web/package-lock.json` | New | Locked dependency tree for `web/package.json`. |
| `web/package.json` | New | Package manifest for `covercall-web` (`vite`, `react`, `@mui/material`, `@mui/icons-material`, `typescript`). |
| `web/tsconfig.json` | New | TypeScript compiler configuration for `web/src`. |
| `web/vite.config.ts` | New | Vite configuration serving on port `3000`, host `0.0.0.0`, `hmr: false`. |
| `web/src/main.tsx` | New | React DOM entry point mounting `<App />`. |
| `web/src/App.tsx` | New | Root application shell routing `/`, `/evals`, `/trace/:gapId`, and `/about`, binding `DataSource`, `ApiClient`, and `VoiceProvider`. |
| `web/src/theme.ts` | New | Custom Material UI theme with light/dark `CoverCallColorTokens`, 8 px spacing grid, 48×48 px touch targets, and `prefers-reduced-motion` support. |
| `web/src/components/VoiceStateBar.tsx` | New | Sticky top bar showing `Listening`, `Thinking`, `Speaking`, `Muted`, or `Offline` with icon + text and `hands-free` / `push-to-talk` / `text` switcher. |
| `web/src/components/MockModeBanner.tsx` | New | Persistent banner displayed whenever `DataSource.isMock` or `ApiClient.isMockMode` is true. |
| `web/src/components/MockDataBadge.tsx` | New | Renders the visible `"Mock data — not computed"` pill with warning icon alongside mock figures. |
| `web/src/components/ScenarioLauncher.tsx` | New | Empty state and compact scenario bar for `"6:02am sick call"` (`S-017`), `"Nobody replies"`, and `"Adversarial"`. |
| `web/src/components/CaptionsPanel.tsx` | New | High-contrast, large-type live captions panel (`aria-live="polite"`) displaying the last exchanges. |
| `web/src/components/GapCard.tsx` | New | Displays outlet, station, shift window, must-fill-by countdown, and throttled `aria-live` announcements. |
| `web/src/components/CandidateList.tsx` | New | Renders up to 3 ranked feasible candidate cards with rule checks, connector channel toggle, and `RuleWarningCard` list. |
| `web/src/components/RuleWarningCard.tsx` | New | Greyed-out rejected candidate card showing severity icon + text label, staff name, plain-English rule message, rule ID, and MOM source link (§11.4). |
| `web/src/components/RosterMiniGrid.tsx` | New | Multi-outlet by hour coverage grid that animates (`<= 200ms`) when the plan re-solves. |
| `web/src/components/CascadeTimeline.tsx` | New | Displays sequential/fan-out offers, reply windows, replies, guard status (`Guard (stub)` when `guardImpl` is null), and quarantined message review. |
| `web/src/components/ApprovalCard.tsx` | New | Sticky bottom card with exact Tier T2 read-back sentence, `approval_nonce`, and two 48 px+ action buttons (`Approve Plan (Yes)` / `No / Edit`). |
| `web/src/components/EvidenceModalViews.tsx` | New | Implements `/evals` (§11.5), `/trace/:gapId` (§12.3), and `/about` (§11.2) reading through `DataSource`. |
| `web/src/data/types.ts` | New | Canonical TypeScript interfaces mirroring §8.1 Firestore collections and §10.4 `covercall_evals` read model. |
| `web/src/data/dataSource.ts` | New | `DataSource` interface with `MockDataSource` and `FirestoreDataSource` implementations plus `createDataSourceFromEnv`. |
| `web/src/data/apiClient.ts` | New | `ApiClient` wrapping `api` HTTP endpoints (`POST /gaps`, `POST /approvals`, `POST /gaps/:gapId/fallback`, `GET /gaps/:gapId`, `POST /gaps/:gapId/cancel`, `GET /status`, `POST /voice/token`). |
| `web/src/data/dataLayer.test.ts` | New | Node unit tests (`node:test`) for `DataSource`, `ApiClient`, and mock-mode honesty invariants. |
| `web/src/voice/voiceProvider.ts` | New | `VoiceProvider` interface, `LiveVoiceProvider`, `PushToTalkProvider`, `TextProvider`, 5 tool declarations (§7.2), and `isClearAffirmativeTranscript`. |
| `web/src/voice/voiceProvider.test.ts` | New | Node unit tests (`node:test`) for the 5 voice tool declarations, fallback order, clear-affirmative check, and tool forwarding. |
| `web/src/utils/formatters.ts` | New | Pure formatters (`formatTime12h`, `formatCurrencySGD`, `formatRuleWarningText`, `getThrottledAriaCountdown`). |
| `web/src/utils/formatters.test.ts` | New | Node unit tests (`node:test`) for time, SGD currency, rule warning text, and `aria-live` countdown throttling. |
| `web/src/mocks/state.ts` | New | Decoupled mock state for `S-017`, `"Nobody replies"`, and `"Adversarial"` with `is_mock: true` and `guardImpl: null`. |

---

## 3. Backend Contract the Frontend Expects

### 3.1 HTTP Calls Made by `ApiClient` (`web/src/data/apiClient.ts`)

Base URL: `import.meta.env.VITE_API_BASE_URL` (trailing slash stripped). When unset, `apiClient.isMockMode === true`.

| Method & Path | Request Body Shape | Response Shape | Component / Caller | Status |
| :--- | :--- | :--- | :--- | :--- |
| `GET {baseUrl}/status` | None | `ApiStatusResponse`: `{ status: 'ok' \| 'mock_mode' \| 'degraded', guard_impl: string \| null, live_model_id: string \| null, mock_mode: boolean }` | `ApiClient.getStatus()` (tested in `dataLayer.test.ts`; not yet polled on mount in `App.tsx`) | **not yet called** (implemented on `ApiClient`, ready to wire on app init) |
| `POST {baseUrl}/gaps` | `CreateGapPayload`: `{ outlet: string, shift_start: string, station: string, staff_name?: string, scenario_id?: string }` | `{ gap_id: string, mock: boolean, gap?: GapDoc }` | `forwardVoiceToolCallToApi` (`report_absence` tool in `web/src/voice/voiceProvider.ts`) | **required now** (called by `VoiceProvider.forwardToolCall('report_absence', ...)`) |
| `POST {baseUrl}/approvals` | `SubmitApprovalPayload`: `{ gap_id: string, plan_id: string, decision: 'approved' \| 'rejected', approval_nonce: string, transcript?: string, channel: 'voice' \| 'tap' }` | `{ approval_id: string, mock: boolean, approval?: ApprovalDoc }` | `forwardVoiceToolCallToApi` (`approve` tool in `web/src/voice/voiceProvider.ts`) | **required now** (called by `VoiceProvider.forwardToolCall('approve', ...)`; tap button in `App.tsx` currently updates local state in mock mode) |
| `POST {baseUrl}/gaps/{gap_id}/fallback` | `ChooseFallbackPayload`: `{ gap_id: string, option: string }` | `{ ok: boolean, mock: boolean }` | `forwardVoiceToolCallToApi` (`choose_fallback` tool in `web/src/voice/voiceProvider.ts`) | **required now** (called by `VoiceProvider.forwardToolCall('choose_fallback', ...)`) |
| `GET {baseUrl}/gaps/{gapId}` | None | `{ gap_id: string, state: string, mock: boolean }` | `forwardVoiceToolCallToApi` (`get_status` tool in `web/src/voice/voiceProvider.ts`) | **required now** (called by `VoiceProvider.forwardToolCall('get_status', ...)`) |
| `POST {baseUrl}/gaps/{gapId}/cancel` | None | `{ gap_id: string, state: 'CANCELLED', mock: boolean }` | `forwardVoiceToolCallToApi` (`cancel_gap` tool in `web/src/voice/voiceProvider.ts`) | **required now** (called by `VoiceProvider.forwardToolCall('cancel_gap', ...)`) |
| `POST {baseUrl}/voice/token` | None (`headers: { 'Content-Type': 'application/json' }`) | `LiveTokenResponse`: `{ ephemeral_token: string, expires_at: string, model_id: string, api_version: 'v1alpha' }` | `LiveVoiceProvider.connect()` and `PushToTalkProvider.connect()` (triggered by `App.tsx` `handleVoiceModeRequest`) | **stub** on backend / **required now** when switching to `hands-free` or `push-to-talk` |

### 3.2 Data Queries Made by `FirestoreDataSource` (`web/src/data/dataSource.ts`)

Note: Because the `firebase` npm package is not yet installed in `web/package.json`, `FirestoreDataSource` currently fetches read-only snapshots over HTTP from `this.config.apiBaseUrl` (configured via `VITE_API_BASE_URL` + `VITE_FIREBASE_PROJECT_ID`) and falls back to `MockDataSource` on error:

| Method | Current Read Path | Logical §8.1 Firestore Collection / §10.4 Dataset | Fields Read by UI |
| :--- | :--- | :--- | :--- |
| `subscribeScenarioBundle(scenarioKey, onUpdate)` | `GET {apiBaseUrl}/scenarios/{scenarioKey}` | Composite view of `gaps`, `plans`, `offers`, `approvals`, `quarantine` | `gap`, `candidates`, `rejectedCandidates`, `rosterGrid`, `cascadeOffers`, `quarantinedMessage`, `approval`, `escalationOptions`, `traceEvents`, `guardImpl`, `chainVerified` |
| `subscribeGap(gapId, onUpdate)` | `GET {apiBaseUrl}/gaps/{gapId}` | `gaps/{gapId}` | `id`, `outlet`, `station`, `start`, `end`, `absent_staff_id`, `state`, `version`, `plan_id`, `outcome`, `cost_saved_sgd`, `workflow_execution_id`, `must_fill_by`, `synthetic` |
| `subscribeGapEvents(gapId, onUpdate)` | `GET {apiBaseUrl}/gaps/{gapId}/events` (expects `{ events: GapEventDoc[], chain_verified: boolean \| null }`) | `gaps/{gapId}/events/{seq}` | `seq`, `type`, `from_state`, `to_state`, `actor`, `model_ids`, `rule_ids`, `trace_id`, `payload` (`payload.summary`), `prev_hash`, `hash`, `ts`, `chain_verified` |
| `subscribePlan(planId, onUpdate)` | `GET {apiBaseUrl}/plans/{planId}` | `plans/{planId}` | `id`, `gap_id`, `candidates[]` (`staff_id`, `segments[]`, `cost_breakdown`, `travel_min`, `arrival`, `rules_checked[]`, `rejected_rules[]`), `solver_params`, `validator_version`, `synthetic` |
| `subscribeQuarantine(gapId, onUpdate)` | `GET {apiBaseUrl}/quarantine?gap_id={gapId}` | `quarantine/{id}` | `id`, `gap_id`, `staff_id`, `guard_labels[]`, `guard_impl`, `redacted_text`, `synthetic` |
| `getOutlets()` | Delegates to `fallbackMock.getOutlets()` | `outlets/{outletId}` | `id`, `name`, `area`, `lat`, `lng`, `opening_hours`, `stations[]`, `keyholders[]`, `synthetic` |
| `getStaff()` | Delegates to `fallbackMock.getStaff()` | `staff/{staffId}` | `id`, `display_name`, `age`, `is_student`, `home_area`, `home_outlet`, `contract_type`, `employee_class`, `monthly_basic_sgd`, `hourly_basic_sgd`, `weekly_contract_hours`, `normal_daily_hours`, `skills[]`, `fsc_l1_passed_on`, `keyholder`, `channel`, `synthetic` |
| `getEvalsReadModel()` | `GET {apiBaseUrl}/evals` | BigQuery `covercall_evals` (`runs`, `metrics`, `cases`) | `isMock`, `latestRun`, `buildHistory`, `p0Metrics`, `p1Metrics`, `p2Metrics`, `sliceTables` (`parseAccuracyBySlice`, `guardComparisonBySlice`), `headlineVsBaseline`, `cases` |

### 3.3 TypeScript Types in `web/src/data/types.ts` Mapping to §8.1 Collections

Exact field names in `web/src/data/types.ts`:

- **`OutletDoc` (`outlets/{outletId}`)**:
  - `id: string`
  - `name: string`
  - `area: 'Bugis' | 'Tampines' | 'Jurong East' | string`
  - `lat: number`
  - `lng: number`
  - `opening_hours: { open: string; close: string }`
  - `stations: OutletStationSpec[]` (`{ station: 'barista' | 'kitchen' | 'cashier' | string; skill: string; food_handling: boolean; min_count: number }`)
  - `keyholders: string[]`
  - `synthetic: true`
- **`StaffDoc` (`staff/{staffId}`)**:
  - `id: string`
  - `display_name: string`
  - `age: number`
  - `is_student: boolean`
  - `home_area: string`
  - `home_outlet: string`
  - `contract_type: 'full_time' | 'part_time'`
  - `employee_class: 'workman' | 'non_workman' | 'manager_executive'`
  - `monthly_basic_sgd?: number`
  - `hourly_basic_sgd?: number`
  - `weekly_contract_hours: number`
  - `normal_daily_hours: number`
  - `skills: string[]`
  - `fsc_l1_passed_on: string | null`
  - `keyholder: boolean`
  - `channel: 'sim' | 'telegram'`
  - `synthetic: true`
- **`ShiftDoc` (`shifts/{shiftId}`)**:
  - `id: string`
  - `outlet: string`
  - `station: string`
  - `staff_id: string`
  - `start: string`
  - `end: string`
  - `breaks: Array<{ start: string; end: string }>`
  - `status: 'scheduled' | 'absent' | 'covered' | 'cancelled'`
  - `synthetic: true`
- **`LedgerDoc` (`ledgers/{staffId_YYYYMM}`)**:
  - `id: string`
  - `staff_id: string`
  - `month: string`
  - `ot_hours_used: number`
  - `rest_days: string[]`
  - `cover_requests_14d: number`
  - `synthetic: true`
- **`GapDoc` (`gaps/{gapId}`)**:
  - `id: string`
  - `outlet: string`
  - `station: string`
  - `start: string`
  - `end: string`
  - `absent_staff_id: string`
  - `state: GapState` (`'REPORTED' | 'GUARDED' | 'HELD' | 'SOLVED' | 'OUTREACH' | 'COMMITTING' | 'FILLED' | 'ESCALATED' | 'RESOLVED' | 'CANCELLED'`)
  - `version: number`
  - `plan_id: string | null`
  - `outcome: string | null`
  - `cost_saved_sgd: number | null`
  - `workflow_execution_id: string | null`
  - `must_fill_by?: string`
  - `synthetic: true`
- **`GapEventDoc` (`gaps/{gapId}/events/{seq}`)**:
  - `seq: number`
  - `type: string`
  - `from_state: string`
  - `to_state: string`
  - `actor: string`
  - `model_ids: string[]`
  - `rule_ids: string[]`
  - `trace_id: string`
  - `payload: Record<string, unknown>`
  - `prev_hash: string`
  - `hash: string`
  - `ts: string`
  - `chain_verified?: boolean | null`
- **`PlanDoc` (`plans/{planId}`)**:
  - `id: string`
  - `gap_id: string`
  - `candidates: PlanCandidateEntry[]` (`{ staff_id: string; segments: Array<{ start: string; end: string }>; cost_breakdown: { incremental_cost_sgd: number; saves_vs_overtime_sgd: number; basis?: string }; travel_min: number; arrival: string; rules_checked: string[]; rejected_rules: Array<{ rule_id: string; severity: 'P0' | 'P1' | 'P2'; message: string; source_url: string; source_publisher: string; source_section: string }> }`)
  - `solver_params: Record<string, unknown>`
  - `validator_version: string`
  - `synthetic: true`
- **`OfferDoc` (`offers/{offerId}`)**:
  - `id: string`
  - `gap_id: string`
  - `staff_id: string`
  - `sent_at: string`
  - `window_s: number`
  - `status: 'sent' | 'accepted' | 'declined' | 'counter' | 'timeout' | 'withdrawn'`
  - `synthetic: true`
- **`ApprovalDoc` (`approvals/{approvalId}`)**:
  - `id: string`
  - `gap_id: string`
  - `tier: 'T0' | 'T1' | 'T2' | 'T3'`
  - `nonce: string`
  - `readback_text: string`
  - `transcript: string`
  - `decision: 'approved' | 'rejected' | 'pending'`
  - `channel: 'voice' | 'tap'`
  - `ts: string`
  - `synthetic: true`
- **`QuarantineDoc` (`quarantine/{id}`)**:
  - `id: string`
  - `gap_id: string`
  - `staff_id: string`
  - `guard_labels: Array<'injection' | 'pii' | 'abuse' | 'ok'>`
  - `guard_impl?: string | null`
  - `redacted_text: string`
  - `synthetic: true`

### 3.4 Voice Token Endpoint & `LiveVoiceProvider` Contract

- **Endpoint:** `POST {VITE_API_BASE_URL}/voice/token`
- **Response interface (`LiveTokenResponse`):**
  ```ts
  export interface LiveTokenResponse {
    ephemeral_token: string;
    expires_at: string;
    model_id: string;
    api_version: 'v1alpha';
  }
  ```
- **Validation in `LiveVoiceProvider.connect()`:**
  - Checks `tokenResp.api_version === 'v1alpha'` and non-empty `tokenResp.ephemeral_token`.
  - Resolves model ID from `this.modelId || tokenResp.model_id` (where `this.modelId` comes from `import.meta.env.VITE_GEMINI_LIVE_MODEL_ID`).
  - If `apiClient.isMockMode` is `true` or `POST /voice/token` fails, `LiveVoiceProvider` transitions voice state to `'Offline'` and invokes `onModeFallback` along `hands-free` → `push-to-talk` → `text`.

---

## 4. Environment Variables

| Variable | Read Location | Purpose | Behavior When Unset |
| :--- | :--- | :--- | :--- |
| `VITE_API_BASE_URL` | `web/src/data/apiClient.ts`, `web/src/data/dataSource.ts` | Base HTTP URL for the `api` Cloud Run service. | `ApiClient.isMockMode` is `true`; `createDataSourceFromEnv()` returns `MockDataSource`; `MockModeBanner` is shown; voice modes fall back to `text`. |
| `VITE_FIREBASE_PROJECT_ID` | `web/src/data/dataSource.ts` | GCP / Firebase project ID required alongside `VITE_API_BASE_URL` to select `FirestoreDataSource`. | `createDataSourceFromEnv()` returns `MockDataSource`. |
| `VITE_FIREBASE_API_KEY` | `web/src/data/dataSource.ts` | Passed into `FirestoreEnvConfig.apiKey`. | `undefined` in `FirestoreEnvConfig`. |
| `VITE_FIREBASE_APP_ID` | `web/src/data/dataSource.ts` | Passed into `FirestoreEnvConfig.appId`. | `undefined` in `FirestoreEnvConfig`. |
| `VITE_FIRESTORE_DATABASE_ID` | `web/src/data/dataSource.ts` | Firestore database ID passed into `FirestoreEnvConfig.databaseId`. | Defaults to `'(default)'`. |
| `VITE_GEMINI_LIVE_MODEL_ID` | `web/src/App.tsx` (line 138) | Pinned Gemini Live model ID passed to `LiveVoiceProvider` and `PushToTalkProvider`. | `null` passed to provider constructor; provider falls back to `tokenResp.model_id` from `POST /voice/token` or errors if neither is set. |

---

## 5. Remaining Mocks and Their Badges / Labels

While `isMockMode` is `true` (`VITE_API_BASE_URL` unset), the UI displays the persistent top `MockModeBanner`:
> `"Mock mode active (MockDataSource) — VITE_API_BASE_URL is unset (none). All displayed costs, travel times, OT hours, and rankings are mock fixtures, not computed by the backend solver."`

Every hard-coded fixture in `web/src/mocks/state.ts` carries the following explicit badge or label:

| Component / Route | Hard-coded Mock Values Shown | Visible Badge / Label |
| :--- | :--- | :--- |
| `CaptionsPanel.tsx` (`/`) | Mock dialogue transcripts (`6:02am` exchanges for `S-017`, `Nobody replies`, `Adversarial`) | `<MockDataBadge />` → `"Mock data — not computed"` |
| `GapCard.tsx` (`/`) | `must_fill_by` (`6:22am` / `6:07am`), `cost_saved_sgd` (`S$40.80` / `S$35.40`) | `<MockDataBadge />` → `"Mock data — not computed"` on both Must-Fill-By and Overtime Cost Avoided |
| `CandidateList.tsx` (`/`) | Candidate `arrival_iso` (`6:52am`, `6:44am`, `6:49am`), `travel_min` (`28 min`, `19 min`, `24 min`), `incremental_cost_sgd` (`S$68.00`, `S$73.40`, `S$78.20`), `saves_vs_overtime_sgd` (`S$40.80`, `S$35.40`, `S$30.60`), `ot_hours_used` (`12/72h`, `28/72h`, `34/72h`, `0/72h`) | `<MockDataBadge />` → `"Mock data — not computed"` in section header and inside each candidate's arrival/travel, cost/savings, and OT ledger cells |
| `RuleWarningCard.tsx` (`/`) | Rejected candidates: Priya (`70 of 72` OT hours + `3`), Hafiz (`8.5h` rest vs `11h`), Mei Ling (`FSC L1` passed `2019-08-14`), Ali (`14h` double shift vs `12h`) | `<MockDataBadge />` → `"Mock data — not computed"` |
| `RosterMiniGrid.tsx` (`/`) | Hourly cells (`7am`–`2pm`) for Bugis, Tampines, Jurong East | `<MockDataBadge />` → `"Mock data — not computed"` |
| `CascadeTimeline.tsx` (`/`) | Offers (`off_s017_1`, `off_s017_2`, `off_s017_3`), reply windows (`420s`, `360s`, `180s`), Singlish replies, quarantined injection text | `<MockDataBadge />` → `"Mock data — not computed"`, plus guard status badge `"Guard (stub)"` and `"Flagged for review · Guard (stub)"` |
| `ApprovalCard.tsx` (`/`) | Read-back text (`nonce: nnc_s017_mock`, `nnc_esc_mock`, `nnc_adv_mock`) and escalation fallback cost deltas (`S$68.00`, `S$0.00`, `S$132.00`) | `<MockDataBadge />` → `"Mock data — not computed"` |
| `EvidenceModalViews.tsx` (`/evals`) | None (no numeric metrics invented; all 8 P0, 6 P1, 2 P2, and 7 slice rows have `value: null`) | Release gate badge `"Release Gate: No eval run yet"` and `"No eval run yet"` on every metric tile and table cell |
| `EvidenceModalViews.tsx` (`/trace/:gapId`) | Mock event sequence (`seq #1`–`#6`), `mock-wf-s017-not-executed` | `"Hash Chain: Not verified (mock mode)"` badge and `<MockDataBadge label="External links inactive in mock mode" />` with disabled external buttons |
| `EvidenceModalViews.tsx` (`/about`) | Scenario summaries and model registry status | `"No eval run yet — pinned model IDs load from config/models.yaml via the backend API."` and `"All data is synthetic (synthetic: true)"` |

---

## 6. Build and Test Verification (Fresh Run)

### 6.1 Commands
```bash
npm --prefix /app/applet/web ci --legacy-peer-deps
npm --prefix /app/applet/web test
npm --prefix /app/applet/web run build
```

### 6.2 Raw Output
```text
added 133 packages, and audited 134 packages in 12s

24 packages are looking for funding
  run `npm fund` for details

found 0 vulnerabilities

> covercall-web@0.3.0 test
> node --test src/utils/*.test.ts src/data/*.test.ts src/voice/*.test.ts

TAP version 13
# Subtest: createDataSourceFromEnv defaults to MockDataSource when env is unset
ok 1 - createDataSourceFromEnv defaults to MockDataSource when env is unset
  ---
  duration_ms: 1.77407
  type: 'test'
  ...
# Subtest: MockDataSource.subscribeGapEvents never reports chainVerified as true in mock mode
ok 2 - MockDataSource.subscribeGapEvents never reports chainVerified as true in mock mode
  ---
  duration_ms: 0.46314
  type: 'test'
  ...
# Subtest: Honesty checks: only S-017 scenario ID exists, guardImpl is null in mock mode, and rule URLs cite MOM URL
ok 3 - Honesty checks: only S-017 scenario ID exists, guardImpl is null in mock mode, and rule URLs cite MOM URL
  ---
  duration_ms: 0.283187
  type: 'test'
  ...
# Subtest: ApiClient enters mock mode when VITE_API_BASE_URL is unset and refuses to fake Live tokens
ok 4 - ApiClient enters mock mode when VITE_API_BASE_URL is unset and refuses to fake Live tokens
  ---
  duration_ms: 1.217974
  type: 'test'
  ...
# Subtest: ApiClient.submitApproval requires a non-empty approval_nonce
ok 5 - ApiClient.submitApproval requires a non-empty approval_nonce
  ---
  duration_ms: 0.577088
  type: 'test'
  ...
# Subtest: formatTime12h converts ISO 8601 +08:00 and 24h strings to 12h format (§11.6)
ok 6 - formatTime12h converts ISO 8601 +08:00 and 24h strings to 12h format (§11.6)
  ---
  duration_ms: 3.47241
  type: 'test'
  ...
# Subtest: formatCurrencySGD formats SGD amounts with currency symbol (§11.6)
ok 7 - formatCurrencySGD formats SGD amounts with currency symbol (§11.6)
  ---
  duration_ms: 0.263003
  type: 'test'
  ...
# Subtest: formatRuleWarningText produces canonical S-017 Priya warning from server-supplied fields (§11.4)
ok 8 - formatRuleWarningText produces canonical S-017 Priya warning from server-supplied fields (§11.4)
  ---
  duration_ms: 0.254427
  type: 'test'
  ...
# Subtest: getThrottledAriaCountdown buckets screen reader updates to avoid flooding (§11.7)
ok 9 - getThrottledAriaCountdown buckets screen reader updates to avoid flooding (§11.7)
  ---
  duration_ms: 0.347199
  type: 'test'
  ...
# Subtest: VOICE_TOOL_DECLARATIONS exposes the exact 5 tools from §7.2
ok 10 - VOICE_TOOL_DECLARATIONS exposes the exact 5 tools from §7.2
  ---
  duration_ms: 2.930975
  type: 'test'
  ...
# Subtest: FIXED_FALLBACK_ORDER enforces hands-free -> push-to-talk -> text (§7.2)
ok 11 - FIXED_FALLBACK_ORDER enforces hands-free -> push-to-talk -> text (§7.2)
  ---
  duration_ms: 0.285159
  type: 'test'
  ...
# Subtest: isClearAffirmativeTranscript accepts only a clear yes and treats anything else as no (§5.3, §7.2)
ok 12 - isClearAffirmativeTranscript accepts only a clear yes and treats anything else as no (§5.3, §7.2)
  ---
  duration_ms: 1.110683
  type: 'test'
  ...
# Subtest: LiveVoiceProvider refuses to fake a voice session in mock mode and falls back to text
ok 13 - LiveVoiceProvider refuses to fake a voice session in mock mode and falls back to text
  ---
  duration_ms: 0.595606
  type: 'test'
  ...
# Subtest: PushToTalkProvider falls back to text when API is unset in mock mode
ok 14 - PushToTalkProvider falls back to text when API is unset in mock mode
  ---
  duration_ms: 0.413384
  type: 'test'
  ...
# Subtest: forwardToolCall approve requires approval_nonce and downgrades ambiguous transcript to rejected
ok 15 - forwardToolCall approve requires approval_nonce and downgrades ambiguous transcript to rejected
  ---
  duration_ms: 0.881674
  type: 'test'
  ...
1..15
# tests 15
# suites 0
# pass 15
# fail 0
# cancelled 0
# skipped 0
# todo 0
# duration_ms 308.249089

> covercall-web@0.3.0 build
> tsc --noEmit && vite build

vite v6.4.4 building for production...
transforming...
✓ 990 modules transformed.
rendering chunks...
computing gzip size...
dist/index.html                  1.11 kB │ gzip:   0.59 kB
dist/assets/index-BBMSE-Mr.js  856.44 kB │ gzip: 247.29 kB
(!) Some chunks are larger than 500 kB after minification. Consider:
- Using dynamic import() to code-split the application
- Use build.rollupOptions.output.manualChunks to improve chunking: https://rollupjs.org/configuration-options/#output-manualchunks
- Adjust chunk size limit for this warning via build.chunkSizeWarningLimit.
✓ built in 4.79s
```

---

## 7. Package Setup

### 7.1 Contents of `web/package.json`
```json
{
  "name": "covercall-web",
  "private": true,
  "version": "0.3.0",
  "type": "module",
  "scripts": {
    "dev": "vite --port 3000 --host 0.0.0.0",
    "build": "tsc --noEmit && vite build",
    "lint": "tsc --noEmit",
    "preview": "vite preview --port 3000 --host 0.0.0.0",
    "test": "node --test src/utils/*.test.ts src/data/*.test.ts src/voice/*.test.ts"
  },
  "dependencies": {
    "@emotion/react": "^11.14.0",
    "@emotion/styled": "^11.14.0",
    "@mui/icons-material": "^6.4.6",
    "@mui/material": "^6.4.6",
    "react": "^19.0.0",
    "react-dom": "^19.0.0"
  },
  "devDependencies": {
    "@types/node": "^22.13.9",
    "@types/react": "^19.0.10",
    "@types/react-dom": "^19.0.4",
    "@vitejs/plugin-react": "^4.3.4",
    "typescript": "~5.8.2",
    "vite": "^6.2.0"
  }
}
```

### 7.2 Root-Level Scaffold Files Status on `gemini/slice-4-web`
- **Tracked in git on `gemini/slice-4-web`:** **None.** (`package.json`, `index.html`, `vite.config.ts`, `tsconfig.json`, `metadata.json`, and `src/` are not tracked in git on `main` or `gemini/slice-4-web` because they are listed in root `.gitignore` from `aa0fc01`).
- **Present on disk (untracked/ignored by root `.gitignore` from the initial container scaffold):**
  - `/package.json`: EXISTS on disk (untracked/ignored in git)
  - `/index.html`: EXISTS on disk (untracked/ignored in git)
  - `/vite.config.ts`: EXISTS on disk (untracked/ignored in git)
  - `/tsconfig.json`: EXISTS on disk (untracked/ignored in git)
  - `/metadata.json`: EXISTS on disk (untracked/ignored in git)
  - `/src`: EXISTS on disk (untracked/ignored in git)

---

## 8. Known Gaps & Approximations (Steps 1–5)

1. **Firebase JS SDK & `@google/genai` SDK packages not yet installed in `web/package.json`:**
   - `FirestoreDataSource` (`web/src/data/dataSource.ts`) currently uses `fetch` against `VITE_API_BASE_URL` REST endpoints (`/gaps/:gapId`, `/gaps/:gapId/events`, `/plans/:planId`, `/quarantine`, `/evals`) rather than importing `firebase/firestore` `onSnapshot` directly. Once Firestore security rules and client config are provisioned, `FirestoreDataSource` can be switched from `fetch` to `onSnapshot`.
   - `LiveVoiceProvider` (`web/src/voice/voiceProvider.ts`) calls `POST /voice/token` on `ApiClient` and validates the `v1alpha` ephemeral token and `VITE_GEMINI_LIVE_MODEL_ID`, but does not yet open a WebRTC/WebSocket audio stream via `@google/genai` `ai.live.connect`.
2. **Lead View (`App.tsx`) tap handlers in non-mock mode:**
   - While `VoiceProvider.forwardToolCall` calls `apiClient.createGap`, `apiClient.submitApproval`, `apiClient.chooseFallback`, `apiClient.getGapStatus`, and `apiClient.cancelGap` directly, the tap buttons in `App.tsx` (`handleApprovePlan`, `handleSelectEscalationOption`, `handleSelectScenario`) currently update React state from `SCENARIO_MAP` and do not yet invoke `apiClient.submitApproval` / `dataSource.subscribeScenarioBundle` when `isMockMode` is `false`.
3. **Automated axe-core Playwright test file (`@axe-core/playwright`):**
   - Visual and DOM checks (48×48 px touch target audit across all 25 buttons, zero horizontal overflow at `360×800` and `390×844`, and zero console errors across `/`, `/evals`, `/trace/:gapId`, and `/about`) were executed via `playwright-cli`, but a standalone `@axe-core/playwright` test runner script has not yet been added to `web/package.json`.
4. **Git remote push:**
   - No git remote (`origin`) is configured in this workspace (`git remote -v` is empty), so commits reside on local branches `gemini/slice-3-frontend` and `gemini/slice-4-web` and could not be pushed to a remote server.
