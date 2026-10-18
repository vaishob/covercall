# CoverCall Operations Runbook (§13.4)

**All data is synthetic.** This one-page runbook covers restarting services, rolling back a Cloud Run revision, rotating secrets in Secret Manager, and reseeding demo data in `asia-southeast1`.

## 1. Restart a Cloud Run Service
```bash
PROJECT_ID=$(gcloud config get-value project)
REGION="asia-southeast1"
for SVC in api solver agent guard persona-sim connectors; do
  gcloud run services update "covercall-${SVC}" \
    --region="${REGION}" \
    --update-env-vars="RESTART_TS=$(date -u +%s)"
done
```

## 2. Roll Back a Cloud Run Revision
```bash
SERVICE="covercall-api"
PREV_REV=$(gcloud run revisions list --service="${SERVICE}" --region="asia-southeast1" \
  --format="value(metadata.name)" --limit=2 | tail -n 1)
gcloud run services update-traffic "${SERVICE}" \
  --region="asia-southeast1" \
  --to-revisions="${PREV_REV}=100"
```

## 3. Rotate Secrets in Secret Manager
Secrets are stored only in Secret Manager: `GEMINI_API_KEY` (read only by `api`, to mint Live API ephemeral tokens), and from Slice 7 `TELEGRAM_BOT_TOKEN`, `TELEGRAM_WEBHOOK_SECRET`, `ROUTES_API_KEY`. After adding a `GEMINI_API_KEY` version, redeploy `covercall-api` so it picks up `:latest`.
```bash
echo -n "${NEW_SECRET_VALUE}" | gcloud secrets versions add TELEGRAM_BOT_TOKEN --data-file=-
gcloud run services update covercall-connectors --region="asia-southeast1" \
  --update-env-vars="SECRET_ROTATED_AT=$(date -u +%s)"
```

## 4. Reseed Synthetic Demo Data
```bash
python3 -m datagen build --seed 42 --to-firestore
```
