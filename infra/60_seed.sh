#!/usr/bin/env bash
# Seed the synthetic data into Firestore (default) and sim, then the demo scenarios.
# Uses Application Default Credentials (gcloud auth application-default login).
set -euo pipefail
source "$(dirname "$0")/env.sh"
export GOOGLE_CLOUD_PROJECT="$PROJECT_ID"

python -m datagen build --seed 42 --to-firestore
python -m infra.seed_scenarios
