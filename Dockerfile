# Use a slim Python base to keep image size down
FROM python:3.11-slim

# Prevent Python buffering
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Install system dependencies
# - curl: for API calls to external Ollama service
# - ca-certificates: for HTTPS
# - git: for repo operations
# - build-essential: for compiling Python packages with C extensions
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install Python dependencies first (better layer caching)
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /app/requirements.txt

# Copy source code
COPY auditor_slm.py /app/auditor_slm.py
COPY entrypoint.sh /app/entrypoint.sh
COPY src/ /app/src/

# Ensure entrypoint is executable
RUN chmod +x /app/entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]
