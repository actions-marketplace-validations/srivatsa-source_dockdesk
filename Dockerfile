# 🚀 UPGRADE: Use Python 3.11 (Fixes importlib crash)
FROM python:3.11-slim

# Prevent Python from buffering stdout/stderr
ENV PYTHONUNBUFFERED=1

# Install dependencies (Force latest versions)
RUN pip install --upgrade pip
COPY requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt

# Copy your script
COPY integrity_agent.py /app/integrity_agent.py

# Run it
ENTRYPOINT ["python", "/app/integrity_agent.py"]