#!/usr/bin/env bash
# One service account per service plus one for the workflow, least privilege (§4.2, §12.1).
# roles/workflows.invoker (includes workflows.callbacks.send) goes ONLY to api and connectors.
# Only persona-sim may use the sim database; api may use only (default). Idempotent.
set -euo pipefail
source "$(dirname "$0")/env.sh"

for name in api solver agent guard persona-sim connectors workflow; do
  if ! gcloud iam service-accounts describe "$(sa_email "$name")" --project "$PROJECT_ID" >/dev/null 2>&1; then
    gcloud iam service-accounts create "cc-$name" --display-name "CoverCall $name" --project "$PROJECT_ID"
  fi
done

bind() {  # bind <member-sa> <role> [condition]
  local cond=(--condition=None)
  if [[ $# -ge 3 ]]; then cond=(--condition="$3"); fi
  gcloud projects add-iam-policy-binding "$PROJECT_ID" --member "serviceAccount:$(sa_email "$1")" \
    --role "$2" "${cond[@]}" >/dev/null
}

DEFAULT_DB="expression=resource.name==\"projects/${PROJECT_ID}/databases/(default)\",title=default-db-only"
SIM_DB="expression=resource.name==\"projects/${PROJECT_ID}/databases/${SIM_DB_ID}\",title=sim-db-only"

bind api roles/datastore.user "$DEFAULT_DB"
bind api roles/workflows.invoker
bind connectors roles/workflows.invoker
bind persona-sim roles/datastore.user "$SIM_DB"
bind agent roles/aiplatform.user
bind api roles/aiplatform.user   # parse_reply runs in api (Gemini Flash, once enabled)
bind persona-sim roles/aiplatform.user   # Gemini Flash persona text, once enabled
for name in api solver agent guard persona-sim connectors workflow; do
  bind "$name" roles/logging.logWriter
  bind "$name" roles/cloudtrace.agent
done
echo "Service-to-service run.invoker bindings are added by 40_deploy_services.sh after deploy."
