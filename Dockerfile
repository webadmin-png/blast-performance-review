# Python 3.11 to match the local interpreter (3.11.9).
FROM python:3.11-slim

WORKDIR /app

# Install dependencies first so this layer caches across source edits.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Bake the source into the image so it can run anywhere (e.g. Cloud Run), not
# just where docker-compose bind-mounts it. .dockerignore keeps secrets, data,
# and venvs out. Locally, docker-compose bind-mounts over /app for live edits,
# so this COPY does not get in the way of development.
COPY . .

# Cloud Run injects the port to listen on via $PORT (default 8080). Streamlit
# must bind 0.0.0.0:$PORT. CORS/XSRF are disabled because the app sits behind
# IAP and is reached through a proxy. `sh -c … exec` expands ${PORT} and still
# forwards SIGTERM to Streamlit for clean Cloud Run shutdowns.
ENV PORT=8080
CMD ["sh", "-c", "exec streamlit run app.py --server.address=0.0.0.0 --server.port=${PORT} --server.headless=true --server.enableCORS=false --server.enableXsrfProtection=false"]
