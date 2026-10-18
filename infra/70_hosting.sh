#!/usr/bin/env bash
# Build the web app against the deployed api and publish it to Firebase Hosting (default site,
# https://PROJECT_ID.web.app). api's ALLOWED_ORIGINS already lists that origin (40_deploy_services.sh).
# Firestore rules use infra/firebase.json; Hosting uses the root firebase.json (public: web/dist).
set -euo pipefail
source "$(dirname "$0")/env.sh"
PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format 'value(projectNumber)')"
API_URL="https://covercall-api-${PROJECT_NUMBER}.${REGION}.run.app"

(cd web && npm ci && VITE_API_BASE_URL="$API_URL" npm run build)
firebase deploy --only hosting --project "$PROJECT_ID" --config firebase.json
echo "web: https://${PROJECT_ID}.web.app  (api: ${API_URL})"
