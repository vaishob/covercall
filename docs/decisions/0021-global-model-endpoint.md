# Decision 0021: Model calls use the `global` endpoint; services stay in `asia-southeast1`

- **Date:** 2026-10-18
- **PDF sections:** §4.6, §13.3 (region `asia-southeast1`)
- **Source:** https://docs.cloud.google.com/gemini-enterprise-agent-platform/resources/locations
  (updated 2026-10-15); Google Gen AI SDK reference https://googleapis.github.io/python-genai/

## Context
- The locations page lists `gemini-3.8-flash` and `gemini-4-argon` on the **global** endpoint. It
  lists Gemini models for the "Asia Pacific" group as a whole (Mumbai, Singapore, Hong Kong, Taiwan,
  Tokyo, Sydney, Seoul), not per region, so it does not confirm either model in `asia-southeast1`.
- The page notes that the global endpoint can improve availability and reduce 429 errors, but
  gives no data-residency or in-region processing guarantee.

## Decision
- `agent`, `persona_sim` and `eval_judge` call models with `location: global`. All CoverCall data is
  synthetic, so data residency is not a requirement.
- Cloud Run, Firestore, Workflows and BigQuery stay in `asia-southeast1`.
- Clients are built as the SDK reference and the locations page specify:
  `genai.Client(enterprise=True, project=..., location=...)`. The SDK (checked on `google-genai`
  2.31.0) calls `enterprise` the Gemini Enterprise Agent Platform flag, formerly Vertex AI, and keeps
  `vertexai` as its legacy name. `services/common/models.py` `enterprise_client(role)` reads the
  model's location and API version from `config/models.yaml` and the project from
  `GOOGLE_CLOUD_PROJECT`. It is not called while `agent` and `persona_sim` run their `stub-v0`
  implementations.
- `persona-sim` gets `roles/aiplatform.user`, as `agent` already had (`infra/20_iam.sh`).

## Still open
Confirm in the project's console whether these models are served in `asia-southeast1`. If they are
and a reason appears to keep processing in Singapore, switch `location` in `config/models.yaml`.
