# Docker Setup — blast-performance-report (Local Dev)

**Date:** 2026-06-22
**Goal:** Package the runtime + dependencies into Docker so the pipeline runs identically on any machine, invoked manually during development. Source is mounted live so code edits apply without rebuilding.

## Context

`blast-performance-report` is a Python 3.11 **batch CLI** (not a long-running server). `python main.py` fetches Shopify orders (UTM), transforms them, and writes blast-performance report CSVs. Dependencies are in `requirements.txt`. Configuration/secrets load from a project-root `.env` via `python-dotenv`.

Two behaviors of the existing code shape this design:

1. **The app writes back to `.env`.** `auth/token_manager.py` and `config/settings.reload()` call `dotenv.set_key(ENV_PATH, ...)` to persist a refreshed `SHOPIFY_ACCESS_TOKEN`. So `.env` must be a **mounted, writable file**, not just injected environment variables.
2. **`config/settings.py` hardcodes an absolute host path** for the Google service-account JSON (`CREDS_PATH`), pointing outside the project. That path does not exist inside a container. Decision: make it configurable (see below).

## Decisions

- **Purpose:** local-dev consistency (manual runs), not scheduled/cron and not cloud deploy.
- **Code delivery:** mount source as a volume (live edit, no rebuild on code change).
- **Google credentials:** make `CREDS_PATH` env-driven and mount the JSON from a project-local `./credentials/` folder (portable). The `.env` key `CREDS_PATH` already exists; `settings.py` currently ignores it.

## Architecture

Three new files, no change to pipeline logic (one minimal config line changes):

### 1. `Dockerfile`
- Base: `python:3.11-slim`.
- Workdir: `/app`.
- Copy `requirements.txt` first, `pip install --no-cache-dir -r requirements.txt`, **then** rely on the mounted source — so dependency layers cache and rebuilds are fast.
- No `CMD` that auto-runs the pipeline; default to an interactive-friendly command (e.g. `bash`) since runs are manual.

### 2. `docker-compose.yml`
- One service, `app`.
- `build: .`
- `volumes: - .:/app` — mounts the whole project root, which automatically covers:
  - source code (live edit),
  - `.env` (writable, for `set_key`),
  - `data/` and `reports/` (output CSVs appear on the host),
  - `./credentials/` (Google JSON).
- `working_dir: /app`.
- No `env_file:` needed — `python-dotenv`'s `load_dotenv()` reads the mounted `.env` file directly, and the app mutates that same file.

### 3. `.dockerignore`
Exclude from the **build context** (does not affect the runtime volume mount): `venv/`, `.git/`, `__pycache__/`, `*.pyc`, `.DS_Store`, `data/`, `reports/`, `notebooks/`, `.pytest_cache/`. Keeps image builds small and fast.

### 4. Minimal code change — `config/settings.py`
Change the hardcoded line:
```python
CREDS_PATH = "/Users/webadmin/.../dialy-report-automation-...json"
```
to:
```python
CREDS_PATH = os.getenv("CREDS_PATH", str(CONFIG_DIR / "credentials" / "service_account.json"))
```
Then set `CREDS_PATH=/app/credentials/service_account.json` in `.env`, and place the JSON at `./credentials/service_account.json`.

### 5. `.gitignore`
Already ignores `service_account*.json` / `credentials.json`. Add `credentials/` to be safe so no service-account file is ever committed.

## Data Flow

```
host edit (main.py, utils/, etc.)
        │  (live via volume mount)
        ▼
docker compose run --rm app python main.py
        │  reads .env + ./credentials/service_account.json (mounted)
        │  calls Shopify / Attentive APIs
        ▼
writes data/raw, data/processed, reports/*.csv  → visible on host (mounted)
may write refreshed token back to .env           → persisted on host (mounted)
```

## How to Run

- Pipeline: `docker compose run --rm app python main.py`
- Shell: `docker compose run --rm app bash`
- Rebuild after dependency change: `docker compose build`

## Error Handling / Edge Cases

- **Missing `.env`:** container starts but API calls fail with auth errors — same as host today; documented in run steps.
- **Missing credentials JSON:** only affects Google Sheets code paths (not exercised by current `main.py`); pipeline still runs.
- **`venv/` on host:** shadowed harmlessly — the container uses system-installed packages, not the host venv, and `venv/` is excluded from the build context.
- **Line endings / permissions on `.env`:** mounted file retains host ownership; `set_key` writes succeed because the bind mount is read-write by default.

## Testing / Verification

1. `docker compose build` succeeds.
2. `docker compose run --rm app python -c "import pandas, gspread, requests; print('deps ok')"`.
3. `docker compose run --rm app python main.py` produces the same CSVs under `reports/` on the host as a native run.
4. Confirm a refreshed token is written back to host `.env` (token-manager path).

## Out of Scope (YAGNI)

- Cron/scheduling, cloud deploy, multi-stage production image, non-root user hardening, healthchecks. Can be added later if the purpose changes.
