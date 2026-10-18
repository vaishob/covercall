# Decision 0024: Demo isolation for lead-reported gaps; voice live

- **Date:** 2026-10-19
- **PDF sections:** §7.2 (voice), §8.3

## Demo isolation
- With `DEMO_ISOLATION=1` (set in production), lead-reported gaps (voice and text) commit to
  `overlays/{gapId}` exactly like scenario gaps (decision 0023). Their planner context is the seeded
  roster with every `cover:` shift ignored, plus only their own overlay; absence resolution also
  ignores `cover:` shifts. So every judge who reports "Ali, 7am barista, Bugis, 3 Nov" gets the same
  plan. Without the flag (default, local), lead-reported gaps still change the roster.
- Test: `tests/test_dev_server.py::test_demo_isolation_same_lead_report_twice_gives_identical_plans`.

## Voice live
- `POST /live/token` (decision 0019) mints single-use `v1beta` ephemeral tokens for `gemini-3.8-live`
  with the model, audio, transcriptions, session resumption, system instruction and five tools
  locked; 5 tokens per IP and 60 overall per 10 minutes (429 beyond). Enabled by `VOICE_ENABLED=1`.
- The browser connects with `@google/genai` 2.27.0; every tool call runs on the server.
