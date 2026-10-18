# Decision 0020: Eval judge is `gemini-4-argon`, not a "Pro" model

- **Date:** 2026-10-18
- **PDF sections:** §7.1 (judge "stronger than the model it grades"), §7.5
- **Sources:** https://ai.google.dev/gemini-api/docs/models (updated 2026-10-13);
  https://docs.cloud.google.com/gemini-enterprise-agent-platform/resources/locations (updated 2026-10-15)

## Context
§7.1 names a Gemini "Pro" tier for the judge. Google's current model page lists no Stable Pro model
that this project can use: the 2.5 family, including `gemini-2.5-pro`, is restricted to users who
used it before. It lists `gemini-4-argon` as Stable, described as the flagship reasoning model.

## Decision
- `eval_judge`: `gemini-4-argon` on the Gemini Enterprise Agent Platform, `location: global`
  (decision 0021), called from Cloud Build only.
- It grades the `agent` and `persona_sim` output of `gemini-3.8-flash`. A newer-generation flagship
  reasoning model judging a Flash model still meets §7.1's "stronger than the model it grades".
- The calibration set (§7.5, 30 items) is still required before its scores gate a release.
