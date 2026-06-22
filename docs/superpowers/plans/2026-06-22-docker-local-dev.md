# Docker Local-Dev Setup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Containerize the `blast-performance-report` batch CLI so it runs identically on any machine, with source mounted live for edit-without-rebuild.

**Architecture:** A `python:3.11-slim` image installs `requirements.txt` at build time. `docker-compose.yml` mounts the project root into `/app` so source, `.env` (writable for token refresh), `data/`, `reports/`, and `./credentials/` are all live on the host. Runs are manual (`docker compose run --rm app python main.py`). One config line is made env-driven so the Google credentials path is portable.

**Tech Stack:** Docker, Docker Compose, Python 3.11, python-dotenv.

> **Note on testing:** This repo has no test framework. Verification is done with real shell commands (build the image, import deps, run the pipeline, inspect outputs). Each task ends with a verification step showing the exact command and expected result.

> **Prerequisite for full run:** The Google service-account JSON currently lives outside the repo. Task 3 moves a copy into `./credentials/service_account.json`. If you don't have that file at execution time, Tasks 1–4 still complete; the full pipeline run in Task 5 only needs Shopify/Attentive secrets in `.env` (current `main.py` does not call Google Sheets).

---

### Task 1: Build-context ignore file

**Files:**
- Create: `.dockerignore`

- [ ] **Step 1: Create `.dockerignore`**

```
# Keep the Docker build context small. Does NOT affect runtime volume mounts.
venv/
.venv/
env/
ENV/
.git/
__pycache__/
*.py[cod]
*$py.class
.DS_Store
Thumbs.db
.idea/
.vscode/
data/
reports/
notebooks/
.ipynb_checkpoints/
.pytest_cache/
.mypy_cache/
.ruff_cache/
docs/
```

- [ ] **Step 2: Verify the file exists and is non-empty**

Run: `test -s .dockerignore && echo OK`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add .dockerignore
git commit -m "Add .dockerignore for Docker build context"
```

---

### Task 2: Dockerfile

**Files:**
- Create: `Dockerfile`

- [ ] **Step 1: Create `Dockerfile`**

```dockerfile
# Python 3.11 to match the local interpreter (3.11.9).
FROM python:3.11-slim

WORKDIR /app

# Install dependencies first so this layer caches across source edits.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Source is bind-mounted at runtime via docker-compose (live edit), so we do
# not COPY it here. Runs are manual; default to a shell.
CMD ["bash"]
```

- [ ] **Step 2: Build the image**

Run: `docker compose build 2>/dev/null || docker build -t blast-report .`

(If `docker-compose.yml` does not exist yet, the fallback `docker build` runs.)
Expected: build completes with a final line like `naming to ... blast-report` or `Successfully built`. No `ERROR`.

- [ ] **Step 3: Verify dependencies import inside the image**

Run: `docker run --rm blast-report python -c "import pandas, gspread, requests, dotenv; print('deps ok')"`
Expected: `deps ok`

- [ ] **Step 4: Commit**

```bash
git add Dockerfile
git commit -m "Add Dockerfile (python:3.11-slim, install requirements)"
```

---

### Task 3: Make CREDS_PATH portable

**Files:**
- Modify: `config/settings.py` (the `CREDS_PATH = "..."` line)
- Modify: `.env` (set `CREDS_PATH`)
- Modify: `.gitignore` (ignore the credentials folder)
- Create: `./credentials/` (place the service-account JSON)

- [ ] **Step 1: Replace the hardcoded `CREDS_PATH` in `config/settings.py`**

Find:
```python
CREDS_PATH = "/Users/webadmin/Documents/Automations/master-file-season/credentials/dialy-report-automation-e20c53e67542.json"
```
Replace with:
```python
# Path to the Google service-account JSON. Override via .env (CREDS_PATH) so the
# location is portable across host and container.
CREDS_PATH = os.getenv("CREDS_PATH", str(BASE_DIR / "credentials" / "service_account.json"))
```

(`os` and `BASE_DIR` are already imported/defined above this line in the file.)

- [ ] **Step 2: Verify the line parses and resolves**

Run: `python -c "from config import settings; print(settings.CREDS_PATH)"`
Expected: prints a path ending in `credentials/service_account.json` (or the `.env` value once Step 4 is done). No traceback.

- [ ] **Step 3: Add the credentials folder to `.gitignore`**

Append to `.gitignore` under the secrets section:
```
credentials/
```

- [ ] **Step 4: Set `CREDS_PATH` in `.env`**

Edit the `CREDS_PATH` entry in `.env` to the container/host path:
```
CREDS_PATH=/app/credentials/service_account.json
```

- [ ] **Step 5: Place the service-account JSON**

```bash
mkdir -p credentials
# Copy your existing service-account JSON into place:
cp "/Users/webadmin/Documents/Automations/master-file-season/credentials/dialy-report-automation-e20c53e67542.json" credentials/service_account.json
```
(If the source file is unavailable now, create the folder and add the JSON later — the current pipeline does not call Google Sheets.)

- [ ] **Step 6: Verify the credentials file is git-ignored**

Run: `git check-ignore credentials/service_account.json && echo IGNORED`
Expected: `credentials/service_account.json` then `IGNORED` (no secret will be committed).

- [ ] **Step 7: Commit (code + gitignore only — never the JSON or .env)**

```bash
git add config/settings.py .gitignore
git commit -m "Make CREDS_PATH env-driven for container portability"
```

---

### Task 4: docker-compose for live-mount runs

**Files:**
- Create: `docker-compose.yml`

- [ ] **Step 1: Create `docker-compose.yml`**

```yaml
services:
  app:
    build: .
    image: blast-report
    working_dir: /app
    # Mount the whole project root: source (live edit), .env (writable for
    # token refresh), data/ and reports/ (outputs on host), credentials/.
    volumes:
      - .:/app
    # Keep STDIN/TTY for interactive `bash` and readable logs.
    stdin_open: true
    tty: true
```

- [ ] **Step 2: Validate the compose file**

Run: `docker compose config >/dev/null && echo OK`
Expected: `OK` (no YAML/schema errors).

- [ ] **Step 3: Verify the mount works (host edit visible in container)**

Run: `docker compose run --rm app python -c "import pathlib; print(pathlib.Path('main.py').exists())"`
Expected: `True`

- [ ] **Step 4: Verify `.env` is readable through the mount**

Run: `docker compose run --rm app python -c "from config import settings; print('env loaded:', bool(settings.SHOPIFY_STORE))"`
Expected: `env loaded: True`

- [ ] **Step 5: Commit**

```bash
git add docker-compose.yml
git commit -m "Add docker-compose for live-mount local dev runs"
```

---

### Task 5: End-to-end pipeline run

**Files:** none (verification only)

- [ ] **Step 1: Record current report outputs (baseline)**

Run: `ls reports/ 2>/dev/null || echo "no reports yet"`
Expected: a listing or `no reports yet`. Note it for comparison.

- [ ] **Step 2: Run the pipeline in the container**

Run: `docker compose run --rm app python main.py`
Expected: console shows "Fetching orders with UTM data from Shopify...", "Saved campaign_data.csv ...", and "EMAIL blast report (...)" / "SMS blast report (...)" lines. No traceback.

(Requires valid Shopify/Attentive secrets in `.env`. If APIs are unreachable, the failure will be an auth/network error from the API call — same as a native run — not a Docker problem.)

- [ ] **Step 3: Verify outputs landed on the host**

Run: `ls -la reports/ data/processed/`
Expected: fresh `blast_report_email_*.csv`, `blast_report_sms_*.csv` in `reports/`, and `campaign_data.csv` / `all_orders_data.csv` in `data/processed/` — written by the container, visible on the host.

- [ ] **Step 4: Verify token write-back path is intact**

Run: `docker compose run --rm app python -c "from auth.token_manager import get_token; print('token len:', len(get_token()))"`
Expected: `token len: <n>` with n > 0, and `.env` on the host has an updated `SHOPIFY_ACCESS_TOKEN` (proves the writable `.env` mount works).

- [ ] **Step 5: Final commit (docs only — outputs and secrets stay ignored)**

```bash
git add docs/superpowers/plans/2026-06-22-docker-local-dev.md
git commit -m "Add Docker local-dev implementation plan"
```

---

## Usage (after implementation)

- Run pipeline: `docker compose run --rm app python main.py`
- Open a shell: `docker compose run --rm app bash`
- Rebuild after changing `requirements.txt`: `docker compose build`
