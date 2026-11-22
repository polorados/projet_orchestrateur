# Shared by every role: Python, the dependencies and config.py
FROM python:3.13-slim AS base
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    iproute2 \
    iputils-ping \
    traceroute \
    dnsutils \
    net-tools \
    iputils-tracepath \
    tcpdump \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir fastapi "uvicorn[standard]" httpx python-multipart requests pillow
WORKDIR /app

COPY orchestrateur/measure.py .
COPY orchestrateur/decide.py .
COPY orchestrateur/configure.py .
COPY orchestrateur/main.py .
CMD ["python", "main.py"]
