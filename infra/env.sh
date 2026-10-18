#!/usr/bin/env bash
# Shared settings for every infra script. Source it: `source infra/env.sh`.
# All data is synthetic. Nothing here contains a secret; secrets live in Secret Manager only.
set -euo pipefail

: "${PROJECT_ID:?Set PROJECT_ID to your Google Cloud project ID}"
export REGION="${REGION:-asia-southeast1}"          # §13.3: Cloud Run, Firestore, Workflows, BigQuery
export AR_REPO="${AR_REPO:-covercall}"
export SIM_DB_ID="covercall-sim"                   # the "sim" database (IDs need 4-63 chars); = SIM_DATABASE in services/common/store.py
export TIME_SCALE="${TIME_SCALE:-60}"               # demo time compression, shown on /test
export SERVICES=(api solver agent guard persona-sim connectors)
export IMAGE_BASE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPO}"

sa_email() { echo "cc-$1@${PROJECT_ID}.iam.gserviceaccount.com"; }
service_dir() { echo "${1//-/_}"; }
