# Factory Knowledge Assistant — container image
#
# Build:  docker build -t factory-knowledge .
# Run:    docker run -p 8501:8501 --env-file .env factory-knowledge
#
# To reach an Ollama/LM Studio server running on the HOST machine, use
# host.docker.internal instead of localhost:
#   docker run -p 8501:8501 \
#     -e OLLAMA_HOST=http://host.docker.internal:11434 \
#     factory-knowledge

FROM python:3.11-slim

# Keep Python lean and unbuffered so container logs stream in real time.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install dependencies first so this layer caches across code changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code and the knowledge base.
COPY factory_knowledge/ ./factory_knowledge/
COPY dba/ ./dba/
COPY eval/ ./eval/
COPY data/ ./data/
COPY tests/ ./tests/
COPY .streamlit/ ./.streamlit/
COPY app.py cli.py ui_helpers.py roles.yaml ./
# Branding: logo_sidebar.png is the downscaled sidebar wordmark the app loads,
# logo.png the full-res source, icon.png the square favicon.
COPY logo.png logo_sidebar.png icon.png ./

# Streamlit needs a writable home for its config/state.
ENV HOME=/app \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

# Default to the pure-stdlib retriever so the container starts fast and works
# with no external services. Override with -e RETRIEVER=vector when an
# embedding backend is reachable.
ENV RETRIEVER=keyword \
    CHUNK_STRATEGY=metadata_aware

EXPOSE 8501

# Fail the health check if the app stops serving, so orchestrators restart it.
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request;urllib.request.urlopen('http://localhost:8501/_stcore/health')" || exit 1

CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
