# Use a slim Python base to keep image size down
FROM python:3.11-slim

# Prevent Python buffering
ENV PYTHONUNBUFFERED=1

# Install system dependencies (curl is needed for the Ollama install script)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install Ollama Binary
# We install the binary but DO NOT pull the model here to save 3GB+ of layer size
RUN curl -fsSL https://ollama.com/install.sh | sh

# Install Python dependencies
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy source code
WORKDIR /app
COPY auditor_slm.py /app/auditor_slm.py
COPY entrypoint.sh /app/entrypoint.sh
COPY src/ /app/src/

# Make entrypoint executable
RUN chmod +x /app/entrypoint.sh

# Set the entrypoint to a shell script that handles Ollama startup
ENTRYPOINT ["/app/entrypoint.sh"]
