#!/usr/bin/env bash
# Voice (Slice 4) BESIDE production: a tagged api revision with NO traffic, and a Firebase Hosting
# preview channel. Production revisions keep 100% of traffic; the live Hosting site is untouched.
#   bash infra/80_voice_preview.sh build    # api image only, tag voice-<sha>
#   bash infra/80_voice_preview.sh web      # web build -> preview channel "voice" (7 days)
#   bash infra/80_voice_preview.sh api ORIGIN   # api revision, --no-traffic --tag voice, CORS + ORIGIN
# Note: the voice revision uses the production Firestore and workflow (synthetic data); a gap made
# by voice runs its cascade through the production api revision.
set -euo pipefail
source "$(dirname "$0")/env.sh"
PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format 'value(projectNumber)')"
TAG="voice-$(git rev-parse --short HEAD)"
VOICE_URL="https://voice---covercall-api-${PROJECT_NUMBER}.${REGION}.run.app"
HOSTING_ORIGINS="https://${PROJECT_ID}.web.app,https://${PROJECT_ID}.firebaseapp.com"

case "${1:-}" in
  build)
    gcloud builds submit --project "$PROJECT_ID" --region "$REGION" --config infra/build-image.yaml \
      --substitutions "_DOCKERFILE=services/api/Dockerfile,_IMAGE=${IMAGE_BASE}/api:${TAG}" .
    ;;
  web)
    (cd web && VITE_API_BASE_URL="$VOICE_URL" npm run build)
    firebase hosting:channel:deploy voice --expires 7d --project "$PROJECT_ID" --config firebase.json
    ;;
  api)
    ORIGIN="${2:?pass the preview channel origin, e.g. https://PROJECT--voice-xxxx.web.app}"
    gcloud run deploy covercall-api --project "$PROJECT_ID" --region "$REGION" \
      --image "${IMAGE_BASE}/api:${TAG}" --no-traffic --tag voice \
      --update-env-vars "^##^VOICE_ENABLED=1##ALLOWED_ORIGINS=${HOSTING_ORIGINS},${ORIGIN}"
    gcloud run services describe covercall-api --project "$PROJECT_ID" --region "$REGION" \
      --format 'yaml(status.traffic)'
    echo "voice api: ${VOICE_URL}"
    ;;
  *) echo "usage: $0 build | web | api ORIGIN" >&2; exit 2 ;;
esac
