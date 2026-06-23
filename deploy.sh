#!/usr/bin/env bash
# ===================================================================
# deploy.sh — Deploy the Streamlit app to Google Cloud Run (private/IAP).
# -------------------------------------------------------------------
# Run from the project root:  ./deploy.sh
# Prereqs: gcloud CLI installed & logged in (`gcloud auth login`).
# See DEPLOY.md for the full walkthrough, including IAP setup.
# ===================================================================
set -euo pipefail

# ── EDIT THESE ──────────────────────────────────────────────────────
PROJECT_ID="your-gcp-project-id"          # gcloud projects list
REGION="asia-southeast2"                   # Jakarta
SERVICE="blast-report"

# Non-secret Shopify config (safe to pass as plain env vars).
SHOPIFY_STORE="wooden-ships.myshopify.com"
SHOPIFY_CLIENT_ID="REPLACE_ME"
SHOPIFY_API_VERSION="2026-01"

# People allowed to open the app (one or more), e.g. "user:you@gmail.com".
ALLOWED_MEMBERS=(
  "user:you@example.com"
  # "user:friend@example.com"
)
# ────────────────────────────────────────────────────────────────────

echo "▶ Using project: $PROJECT_ID  region: $REGION  service: $SERVICE"
gcloud config set project "$PROJECT_ID"

echo "▶ Enabling required APIs…"
gcloud services enable \
  run.googleapis.com \
  secretmanager.googleapis.com \
  iap.googleapis.com \
  cloudbuild.googleapis.com

# ── Secret Manager: store SHOPIFY_CLIENT_SECRET (create once, then add versions)
echo "▶ Ensuring SHOPIFY_CLIENT_SECRET exists in Secret Manager…"
if ! gcloud secrets describe SHOPIFY_CLIENT_SECRET >/dev/null 2>&1; then
  echo "  Creating secret. Paste the Shopify client secret, then press Ctrl-D:"
  gcloud secrets create SHOPIFY_CLIENT_SECRET --replication-policy=automatic --data-file=-
else
  echo "  Secret already exists — skipping (use 'gcloud secrets versions add' to rotate)."
fi

# Let Cloud Run's runtime service account read the secret.
PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"
RUNTIME_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
gcloud secrets add-iam-policy-binding SHOPIFY_CLIENT_SECRET \
  --member="serviceAccount:${RUNTIME_SA}" \
  --role="roles/secretmanager.secretAccessor" >/dev/null

# ── Deploy (Cloud Run builds the image from the Dockerfile) ──────────
echo "▶ Deploying to Cloud Run…"
gcloud run deploy "$SERVICE" \
  --source . \
  --region "$REGION" \
  --no-allow-unauthenticated \
  --execution-environment gen2 \
  --timeout 3600 \
  --cpu 1 --memory 1Gi \
  --min-instances 0 --max-instances 4 \
  --set-env-vars "SHOPIFY_STORE=${SHOPIFY_STORE},SHOPIFY_CLIENT_ID=${SHOPIFY_CLIENT_ID},SHOPIFY_API_VERSION=${SHOPIFY_API_VERSION}" \
  --set-secrets "SHOPIFY_CLIENT_SECRET=SHOPIFY_CLIENT_SECRET:latest"

# ── Enable IAP on the service and grant access to allowed members ───
# Direct IAP for Cloud Run (no load balancer needed). Requires a configured
# OAuth consent screen in the project — see DEPLOY.md if this step errors.
echo "▶ Enabling IAP on the service…"
gcloud beta run services update "$SERVICE" --region "$REGION" --iap

echo "▶ Granting access to allowed members…"
for MEMBER in "${ALLOWED_MEMBERS[@]}"; do
  echo "  - $MEMBER"
  gcloud beta iap web add-iam-policy-binding \
    --resource-type=cloud-run \
    --service="$SERVICE" \
    --region="$REGION" \
    --member="$MEMBER" \
    --role="roles/iap.httpsResourceAccessor"
done

URL="$(gcloud run services describe "$SERVICE" --region "$REGION" --format='value(status.url)')"
echo ""
echo "✅ Deployed. Open (after Google login):  $URL"
