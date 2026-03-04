# ───────────────────────────────────────────────────────────
# DockDesk - Semantic Documentation Auditor
# ───────────────────────────────────────────────────────────
# Build:  docker build -t dockdesk .
# Run:    docker run -v /path/to/repo:/workspace dockdesk audit .
#
# Ollama must be running on the host (or a linked container).
# The container connects to host Ollama by default.
# ───────────────────────────────────────────────────────────

FROM python:3.11-slim

LABEL maintainer="DockDesk" \
      description="Local-first semantic documentation auditor" \
      version="2.1.0"

# Install git (needed for git-diff based scoping)
RUN apt-get update && \
    apt-get install -y --no-install-recommends git && \
    rm -rf /var/lib/apt/lists/*

# Set default Ollama host to reach the Docker host
ENV OLLAMA_HOST=http://host.docker.internal:11434

WORKDIR /app

# Install Python dependencies first (cache layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy package source
COPY pyproject.toml .
COPY dockdesk/ dockdesk/
COPY auditor_slm.py .

# Install dockdesk as a package
RUN pip install --no-cache-dir .

# The target repo gets mounted here
WORKDIR /workspace

ENTRYPOINT ["dockdesk"]
CMD ["audit", "--workspace", ".", "--skip-rag"]
