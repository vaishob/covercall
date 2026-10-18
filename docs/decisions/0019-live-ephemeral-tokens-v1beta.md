# Decision 0019: Live API ephemeral tokens use `v1beta`, not `v1alpha`

- **Date:** 2026-10-18
- **Departs from:** design doc §7.2 ("Ephemeral tokens currently work only with the Live API on the
  v1alpha API version") and KICKSTART §1.3. Both are out of date.
- **Source:** https://ai.google.dev/gemini-api/docs/live-api/ephemeral-tokens (updated 2026-09-15)

## What Google's page says
- Ephemeral tokens are a **Preview** feature, for the **Live API only**, on the **`v1beta`** API
  version only. They are minted with `client.auth_tokens.create` on the Gemini Developer API.
- Defaults: `uses: 1`, 1 minute to start a new session (`new_session_expire_time`), 30 minutes of
  messages (`expire_time`). `live_connect_constraints` can lock a token to `gemini-3.8-live`.

## Decision
- `config/models.yaml` `voice`: `gemini-3.8-live`, provider `gemini_developer_api`,
  `api_version: v1beta`, `ephemeral_token_uses: 1`, and the two TTLs above.
- In Slice 4, `api` mints each token with `uses: 1`, the two expiry times, and a
  `live_connect_constraints` lock to the pinned model. The browser connects with that token only.
- `api` reads the key from the Secret Manager entry `GEMINI_API_KEY` (`infra/25_secrets.sh`). The key
  never reaches the browser, a log or the repo.
- `POST /live/token` stays 501 until Slice 4.

## Still open
- Ephemeral tokens are Preview and may change; re-check the page before Slice 4.
- The web client still checks for `v1alpha` (`web/src/voice/voiceProvider.ts`, `apiClient.ts`). It
  changes to `v1beta` when the voice session is built; the route is 501 today, so nothing reaches
  that check.
