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
    openssh-client \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir fastapi "uvicorn[standard]" httpx python-multipart requests pillow
WORKDIR /app

# Clé SSH du controller (copiée sur les edges par sdwlab/lab_test.py)
RUN mkdir -p /root/.ssh && ssh-keygen -q -t ed25519 -N "" -f /root/.ssh/id_ed25519

COPY orchestrateur/measure.py .
COPY orchestrateur/decide.py .
COPY orchestrateur/configure.py .
COPY orchestrateur/main.py .
COPY orchestrateur/intent.json .
COPY orchestrateur/constants.py .
CMD ["python", "main.py"]
