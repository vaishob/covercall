#!/usr/bin/env bash
# Firestore Native databases (default) and sim in REGION (idempotent), then security rules.
set -euo pipefail
source "$(dirname "$0")/env.sh"

for db in "(default)" "sim"; do
  if gcloud firestore databases describe --database="$db" --project "$PROJECT_ID" >/dev/null 2>&1; then
    echo "Firestore database $db exists"
  else
    gcloud firestore databases create --database="$db" --location="$REGION" \
      --type=firestore-native --project "$PROJECT_ID"
  fi
done

# Security rules (infra/firestore.rules, infra/firestore.sim.rules). Rules are deployed with the
# Firebase CLI; firebase.json maps each database to its rules file.
if command -v firebase >/dev/null 2>&1; then
  firebase deploy --only firestore:rules --project "$PROJECT_ID" --config infra/firebase.json
else
  echo "Install the Firebase CLI, then run:"
  echo "  firebase deploy --only firestore:rules --project $PROJECT_ID --config infra/firebase.json"
fi
