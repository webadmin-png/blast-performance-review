# Python 3.11 to match the local interpreter (3.11.9).
FROM python:3.11-slim

WORKDIR /app

# Install dependencies first so this layer caches across source edits.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Source is bind-mounted at runtime via docker-compose (live edit), so we do
# not COPY it here. Runs are manual; default to a shell.
CMD ["bash"]
