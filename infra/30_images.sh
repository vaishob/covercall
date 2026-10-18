#!/usr/bin/env bash
# Artifact Registry repo (idempotent) and one image per service, built by Cloud Build.
set -euo pipefail
source "$(dirname "$0")/env.sh"

if ! gcloud artifacts repositories describe "$AR_REPO" --location "$REGION" --project "$PROJECT_ID" >/dev/null 2>&1; then
  gcloud artifacts repositories create "$AR_REPO" --repository-format=docker --location "$REGION" \
    --project "$PROJECT_ID"
fi
TAG="${TAG:-$(git rev-parse --short HEAD)}"
gcloud builds submit --project "$PROJECT_ID" --region "$REGION" --config infra/build-images.yaml \
  --substitutions "_IMAGE_BASE=${IMAGE_BASE},_TAG=${TAG}" .
echo "$TAG" > infra/.last_tag
