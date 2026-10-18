#!/usr/bin/env bash
# Full deploy, in order. Every step is idempotent and can be re-run.
# Prerequisites: gcloud authenticated, PROJECT_ID set, billing enabled, Python 3.12 venv for seeding.
set -euo pipefail
here="$(dirname "$0")"
bash "$here/00_apis.sh"
bash "$here/10_firestore.sh"
bash "$here/20_iam.sh"
bash "$here/25_secrets.sh"
bash "$here/30_images.sh"
bash "$here/40_deploy_services.sh"
bash "$here/50_workflow.sh"
bash "$here/60_seed.sh"
bash "$here/70_hosting.sh"
