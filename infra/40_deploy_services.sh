#!/usr/bin/env bash
# Deploy the six Cloud Run services and the service-to-service invoker bindings (idempotent:
# `gcloud run deploy` creates or updates). Only api is public (no sign-in, §1.2); api keeps
# min instances 1 during judging (§13.3).
#
# Every service is deployed once, with all of its settings. api reads GUARD_URL, SOLVER_URL and
# PERSONA_SIM_URL at start-up, and persona-sim needs API_URL, so URLs are the deterministic Cloud
# Run form https://SERVICE-PROJECT_NUMBER.REGION.run.app, known before anything is deployed.
set -euo pipefail
source "$(dirname "$0")/env.sh"
TAG="${TAG:-$(cat infra/.last_tag)}"
PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format 'value(projectNumber)')"
run_url() { echo "https://covercall-$1-${PROJECT_NUMBER}.${REGION}.run.app"; }
API_URL="$(run_url api)"
# The web app's origins (Firebase Hosting default site). Comma-separated; never "*".
HOSTING_ORIGINS="${HOSTING_ORIGINS:-https://${PROJECT_ID}.web.app,https://${PROJECT_ID}.firebaseapp.com}"

deploy() {  # deploy <service> <public|private> <min-instances> <extra env, "##"-separated> [gcloud args...]
  local svc="$1" access="$2" min="$3" env="$4"; shift 4
  local auth=(--no-allow-unauthenticated)
  if [[ "$access" == public ]]; then auth=(--allow-unauthenticated); fi
  # --update-env-vars only (gcloud refuses it together with --set-env-vars). "^##^" makes "##" the
  # separator, so values may contain commas (ALLOWED_ORIGINS).
  gcloud run deploy "covercall-$svc" --project "$PROJECT_ID" --region "$REGION" \
    --image "${IMAGE_BASE}/${svc}:${TAG}" --service-account "$(sa_email "$svc")" \
    --min-instances "$min" "${auth[@]}" \
    --update-env-vars "^##^COVERCALL_ENV=cloud##REGION=${REGION}${env:+##${env}}" "$@"
}
invoker() {  # invoker <service> <caller-sa>
  gcloud run services add-iam-policy-binding "covercall-$1" --project "$PROJECT_ID" --region "$REGION" \
    --member "serviceAccount:$(sa_email "$2")" --role roles/run.invoker >/dev/null
}

deploy solver private 0 ""
deploy guard private 1 ""
deploy agent private 1 "AGENT_IMPL=stub-v0##GOOGLE_CLOUD_PROJECT=${PROJECT_ID}"
deploy connectors private 0 ""
deploy persona-sim private 1 "API_URL=${API_URL}##TIME_SCALE=${TIME_SCALE}##GOOGLE_CLOUD_PROJECT=${PROJECT_ID}##PERSONA_TEXT_IMPL=${PERSONA_TEXT_IMPL:-gemini}" \
  --no-cpu-throttling
# GEMINI_API_KEY: required Secret Manager entry (infra/25_secrets.sh checks it exists); api only.
deploy api public 1 "API_URL=${API_URL}##TIME_SCALE=${TIME_SCALE}##GOOGLE_CLOUD_PROJECT=${PROJECT_ID}##WORKFLOW_SA_EMAIL=$(sa_email workflow)##SOLVER_URL=$(run_url solver)##GUARD_URL=$(run_url guard)##PERSONA_SIM_URL=$(run_url persona-sim)##ALLOWED_ORIGINS=${HOSTING_ORIGINS}##PARSER_IMPL=${PARSER_IMPL:-gemini}##PERSONA_TEXT_IMPL=${PERSONA_TEXT_IMPL:-gemini}##VOICE_ENABLED=${VOICE_ENABLED:-1}##DEMO_ISOLATION=${DEMO_ISOLATION:-1}##DEMO_CLOCK_OFFSET_DAYS=${DEMO_CLOCK_OFFSET_DAYS:-7}" \
  --update-secrets "GEMINI_API_KEY=GEMINI_API_KEY:latest"

invoker solver api
invoker guard api
invoker agent api
invoker persona-sim api
echo "api: ${API_URL}  (test page: ${API_URL}/test)"
