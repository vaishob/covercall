#!/usr/bin/env bash
# Deploy the six Cloud Run services and the service-to-service invoker bindings (idempotent:
# `gcloud run deploy` creates or updates). Only api is public (no sign-in, §1.2); api keeps
# min instances 1 during judging (§13.3).
set -euo pipefail
source "$(dirname "$0")/env.sh"
TAG="${TAG:-$(cat infra/.last_tag)}"

deploy() {  # deploy <service> <public|private> <min-instances> [extra gcloud args...]
  local svc="$1" access="$2" min="$3"; shift 3
  local auth=(--no-allow-unauthenticated)
  if [[ "$access" == public ]]; then auth=(--allow-unauthenticated); fi
  gcloud run deploy "covercall-$svc" --project "$PROJECT_ID" --region "$REGION" \
    --image "${IMAGE_BASE}/${svc}:${TAG}" --service-account "$(sa_email "$svc")" \
    --min-instances "$min" "${auth[@]}" --set-env-vars "COVERCALL_ENV=cloud,REGION=${REGION}" "$@"
}
url() { gcloud run services describe "covercall-$1" --project "$PROJECT_ID" --region "$REGION" --format 'value(status.url)'; }
invoker() {  # invoker <service> <caller-sa>
  gcloud run services add-iam-policy-binding "covercall-$1" --project "$PROJECT_ID" --region "$REGION" \
    --member "serviceAccount:$(sa_email "$2")" --role roles/run.invoker >/dev/null
}

deploy solver private 0
deploy guard private 1
deploy agent private 1 --update-env-vars "AGENT_IMPL=stub-v0,GOOGLE_CLOUD_PROJECT=${PROJECT_ID}"
deploy connectors private 0
# GEMINI_API_KEY: required Secret Manager entry (infra/25_secrets.sh checks it exists); api only.
deploy api public 1 --update-secrets "GEMINI_API_KEY=GEMINI_API_KEY:latest"
API_URL="$(url api)"
deploy persona-sim private 1 --no-cpu-throttling --update-env-vars "API_URL=${API_URL},TIME_SCALE=${TIME_SCALE},GOOGLE_CLOUD_PROJECT=${PROJECT_ID}"
deploy api public 1 --update-secrets "GEMINI_API_KEY=GEMINI_API_KEY:latest" --update-env-vars "API_URL=${API_URL},TIME_SCALE=${TIME_SCALE},GOOGLE_CLOUD_PROJECT=${PROJECT_ID},WORKFLOW_SA_EMAIL=$(sa_email workflow),SOLVER_URL=$(url solver),GUARD_URL=$(url guard),PERSONA_SIM_URL=$(url persona-sim)"

invoker solver api
invoker guard api
invoker agent api
invoker persona-sim api
echo "api: ${API_URL}  (test page: ${API_URL}/test)"
