#!/usr/bin/env bash
# Enable the Google Cloud APIs CoverCall uses (idempotent).
set -euo pipefail
source "$(dirname "$0")/env.sh"

gcloud services enable --project "$PROJECT_ID" \
  run.googleapis.com \
  workflows.googleapis.com \
  workflowexecutions.googleapis.com \
  firestore.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  secretmanager.googleapis.com \
  iam.googleapis.com \
  iamcredentials.googleapis.com \
  aiplatform.googleapis.com \
  cloudtrace.googleapis.com \
  logging.googleapis.com \
  monitoring.googleapis.com \
  bigquery.googleapis.com
