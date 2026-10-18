#!/usr/bin/env bash
# Deploy the coverage-cascade workflow under its own service account (idempotent).
set -euo pipefail
source "$(dirname "$0")/env.sh"

gcloud workflows deploy coverage-cascade --project "$PROJECT_ID" --location "$REGION" \
  --source workflows/coverage_cascade.yaml --service-account "$(sa_email workflow)"
# The workflow calls only api's internal routes (OIDC); it needs run.invoker on api and nothing else.
gcloud run services add-iam-policy-binding covercall-api --project "$PROJECT_ID" --region "$REGION" \
  --member "serviceAccount:$(sa_email workflow)" --role roles/run.invoker >/dev/null
