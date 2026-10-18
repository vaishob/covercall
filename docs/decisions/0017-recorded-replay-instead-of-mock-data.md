# Decision 0017: Mock mode plays a recorded replay instead of invented numbers

- **Date:** 2026-10-18
- **Ground rules:** "no invented numbers"; "mock mode stays and stays badged".

## Context
The imported frontend's mock mode (`web/src/mocks/state.ts`) showed hand-written figures
("Wei saves S$40.80", "S$74.00 mock total", a `stf_014` key-holder, a 22:00 closing time) that no
part of the system computed, under a "Mock data — not computed" badge.

## Decision
- When `VITE_API_BASE_URL` is unset, the app plays back the contract fixtures: **real responses
  recorded from the local cascade** (decision 0016), mapped by the same `viewModel.ts` as live data.
- Everything it shows is badged "Recorded replay — not live", with a banner explaining the source.
  Buttons that change state are disabled. The fixtures load lazily, in their own bundle chunks.
- `web/src/mocks/state.ts`, the Firestore data-source stub, `MockDataBadge` and `MockModeBanner` were
  removed. Errors in live mode are shown as errors; there is no fallback to recorded data.
- Mock-only scenarios with no backend data (the "Adversarial" J4 scenario) are no longer shown; see
  `docs/OPEN_ITEMS.md`.
