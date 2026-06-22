# Blast Performance Report

Batch pipeline that fetches Shopify orders (with UTM data), transforms them, and
builds per-channel (email + SMS) blast-performance report CSVs. Recipient counts
come from Attentive.

It runs as a one-shot CLI: `python main.py`.

## Run it with Docker (recommended)

Docker bundles Python 3.11 and every dependency, so you don't install anything
locally except Docker itself.

### 1. Install Docker Desktop
Download from <https://www.docker.com/products/docker-desktop/>, open the app
until the daemon is running, then verify:
```bash
docker --version
docker compose version
```

### 2. Get the code
```bash
git clone <repo-url> blast-performance-report
cd blast-performance-report
```

### 3. Configure secrets (`.env`)
`.env` is **git-ignored**, so it is not part of the clone. Create it from the
template and fill in the values (ask the project owner for them, or use your own):
```bash
cp .env.example .env
# then edit .env
```
Minimum required to run `main.py`: `SHOPIFY_STORE`, `SHOPIFY_CLIENT_ID`,
`SHOPIFY_CLIENT_SECRET`, and `ATTENTIVE_API_KEY`. `SHOPIFY_ACCESS_TOKEN` is
fetched automatically on first run and written back to `.env`.

Keep `CREDS_PATH=/app/credentials/service_account.json` as-is for Docker.

### 4. (Optional) Google service-account JSON
Only needed for Google Sheets features (not exercised by the current `main.py`):
```bash
mkdir -p credentials
# place the JSON at: credentials/service_account.json
```
The `credentials/` folder is git-ignored.

### 5. Build and run
```bash
docker compose build
docker compose run --rm app python main.py
```
Outputs land on your machine:
- `data/processed/campaign_data.csv`, `data/processed/all_orders_data.csv`
- `reports/blast_report_email_*.csv`, `reports/blast_report_sms_*.csv`

## Everyday commands
```bash
docker compose run --rm app python main.py   # run the pipeline
docker compose run --rm app bash             # open a shell in the container
docker compose build                         # rebuild after editing requirements.txt
```

## How it works
- **Image:** `python:3.11-slim` with `requirements.txt` installed at build time
  (see [Dockerfile](Dockerfile)).
- **Live edit:** [docker-compose.yml](docker-compose.yml) bind-mounts the project
  root into `/app`, so code edits, `.env`, `data/`, and `reports/` are live on the
  host — no rebuild needed for code changes (only for dependency changes).

## Notes
- Never commit `.env`, `credentials/`, or generated CSVs — all are git-ignored.
- Running natively without Docker also works (Python 3.11 + `pip install -r
  requirements.txt` in a venv), but Docker is the supported, reproducible path.
