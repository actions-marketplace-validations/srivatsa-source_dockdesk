# Use a slim Python base to keep image size down
FROM python:3.11-slim

# Prevent Python buffering
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Install system dependencies
# - curl: for Ollama install and API calls
# - ca-certificates: for HTTPS
# - git: for repo operations
# - build-essential: for compiling Python packages with C extensions
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Ollama Binary
# Note: The install script works in Docker but requires the container to run as root
# We install the binary but DO NOT pull the model here to save 3GB+ of layer size
RUN curl -fsSL https://ollama.com/install.sh | sh || \
    (echo "Ollama install script failed, trying direct download..." && \
     curl -L https://ollama.com/download/ollama-linux-amd64 -o /usr/local/bin/ollama && \
     chmod +x /usr/local/bin/ollama)

# Set working directory early
WORKDIR /app

# Install Python dependencies first (better caching)
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /app/requirements.txt

# Copy source code
COPY auditor_slm.py /app/auditor_slm.py
COPY entrypoint.sh /app/entrypoint.sh
COPY src/ /app/src/

# Ensure all files have correct permissions
RUN chmod +x /app/entrypoint.sh && \
    chmod -R 755 /app/src/

# Set the entrypoint to a shell script that handles Ollama startup
ENTRYPOINT ["/app/entrypoint.sh"]
