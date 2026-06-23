# Deploy to Google Cloud Run (private, IAP-protected)

The Streamlit app runs on **Cloud Run** behind **IAP** (Identity-Aware Proxy), so
only Google accounts you allow can open it. Region: **Jakarta (`asia-southeast2`)**.

## 0. One-time prerequisites

1. **Install the gcloud CLI**: https://cloud.google.com/sdk/docs/install
2. **Log in and pick/create a project:**
   ```bash
   gcloud auth login
   gcloud projects list                       # find your PROJECT_ID
   gcloud config set project YOUR_PROJECT_ID
   ```
3. **Billing** must be enabled on the project (Cloud Run has a free tier; idle ≈ $0).
4. **OAuth consent screen** (needed for IAP), one-time:
   Console → *APIs & Services → OAuth consent screen* → User type **External** →
   fill app name + your email → add yourself and your friend under **Test users**.

## 1. Configure the deploy script

Open [deploy.sh](deploy.sh) and edit the block at the top:
- `PROJECT_ID` — your GCP project id
- `SHOPIFY_CLIENT_ID` — your Shopify custom-app client id
- `ALLOWED_MEMBERS` — Google accounts allowed to open the app, e.g.
  `"user:you@gmail.com"` and `"user:friend@gmail.com"`

The **Shopify client secret is NOT put in the script** — it goes to Secret Manager
(the script prompts you to paste it on first run).

## 2. Deploy

```bash
chmod +x deploy.sh
./deploy.sh
```

The script will:
1. Enable the required APIs (Run, Secret Manager, IAP, Cloud Build).
2. Store `SHOPIFY_CLIENT_SECRET` in Secret Manager (prompts for the value once).
3. Build the image from the `Dockerfile` and deploy to Cloud Run
   (`--no-allow-unauthenticated`, gen2 filesystem, 60-min timeout for long fetches).
4. Turn on IAP and grant access to everyone in `ALLOWED_MEMBERS`.
5. Print the service URL.

Open the URL → sign in with an allowed Google account → the app loads.

## 3. Updating after code changes

After you `git pull` (or edit locally), just redeploy:
```bash
./deploy.sh
```
Cloud Run rebuilds the image (picking up `requirements.txt` and source changes)
and rolls out a new revision with zero downtime.

## How secrets work here
- `config/settings.py` reads config via `os.getenv()`, so Cloud Run env vars and
  mounted secrets are picked up automatically — **no `.env` file is needed** in the
  cloud.
- `auth/token_manager.get_token()` writes the refreshed Shopify token to `.env` at
  runtime; on Cloud Run this happens on the in-memory filesystem (gen2) and is
  re-minted on each cold start. Nothing persists to disk or to the image.
- Only **Shopify** credentials are required for the UI. Google `service_account.json`
  is **not** needed (the app does not touch Google Sheets).

## Giving a teammate access later
```bash
gcloud beta iap web add-iam-policy-binding \
  --resource-type=cloud-run --service=blast-report --region=asia-southeast2 \
  --member="user:teammate@gmail.com" \
  --role="roles/iap.httpsResourceAccessor"
```
They also need to be added as a **Test user** on the OAuth consent screen (step 0.4).

## Troubleshooting
| Symptom | Fix |
|---|---|
| `--iap` flag not recognized | `gcloud components update`, or enable IAP for the service in the Console (Cloud Run → service → *Security → IAP*). |
| 403 after login | The account isn't in `ALLOWED_MEMBERS` **and** the OAuth test users list. Add it to both. |
| Credential error on **Generate** | `SHOPIFY_CLIENT_ID` / secret wrong — recheck env var and Secret Manager value. |
| Fetch times out | Raise `--timeout` (max 3600s) and/or narrow the date range. |

## Cost
Cloud Run bills per request/CPU-second with a generous free tier. With
`--min-instances 0`, it scales to zero when idle, so an internal tool used a few
times a day typically costs near nothing.
