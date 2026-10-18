#!/usr/bin/env bash
# Required Secret Manager entries, and who may read them (idempotent). Never put a value in the repo,
# an image, a log or a command line in shell history; this script only checks and binds.
#
#   GEMINI_API_KEY  Gemini Developer API key. Only api reads it, to mint single-use Live API
#                   ephemeral tokens (v1beta, decision 0019). The browser never sees it.
#
# Create it once, by hand, reading the value from stdin (it is not echoed):
#   gcloud secrets create GEMINI_API_KEY --project "$PROJECT_ID" --replication-policy=automatic
#   read -rs KEY && printf '%s' "$KEY" | gcloud secrets versions add GEMINI_API_KEY --project "$PROJECT_ID" --data-file=- ; unset KEY
set -euo pipefail
source "$(dirname "$0")/env.sh"

require_secret() {  # require_secret <name> <reader-service>...
  local name="$1"; shift
  if ! gcloud secrets describe "$name" --project "$PROJECT_ID" >/dev/null 2>&1; then
    echo "Missing Secret Manager entry $name. Create it as shown at the top of infra/25_secrets.sh." >&2
    exit 1
  fi
  for svc in "$@"; do
    gcloud secrets add-iam-policy-binding "$name" --project "$PROJECT_ID" \
      --member "serviceAccount:$(sa_email "$svc")" --role roles/secretmanager.secretAccessor >/dev/null
  done
}

require_secret GEMINI_API_KEY api
echo "Secrets present; accessor bindings set."
