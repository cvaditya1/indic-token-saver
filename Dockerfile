FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

WORKDIR /app

RUN useradd --create-home --uid 1000 appuser

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Source only. .env is not copied; pass keys at run time.
COPY src/ src/

RUN mkdir -p /app/logs /app/data && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

CMD ["uvicorn", "indic_token_saver.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]

# Gateway only (no torch). docker build --target slim .
FROM base AS slim

# CPU torch wheels — default full gateway image (no CUDA download).
# docker build --target translate-cpu -t indic-token-saver:translate-cpu .
FROM slim AS translate-cpu
USER root
COPY requirements-translate-cpu.txt requirements-translate-common.txt ./
RUN pip install --no-cache-dir -r requirements-translate-cpu.txt
USER appuser
ENV HF_HOME=/home/appuser/.cache/huggingface

# NVIDIA CUDA torch (opt-in; large layer). Linux + NVIDIA only.
# docker build --target translate-cuda -t indic-token-saver:translate-cuda .
FROM slim AS translate-cuda
USER root
COPY requirements-translate-cuda.txt requirements-translate-common.txt ./
RUN pip install --no-cache-dir -r requirements-translate-cuda.txt
USER appuser
ENV HF_HOME=/home/appuser/.cache/huggingface

# Default `docker build .` is CPU translate (not CUDA).
FROM translate-cpu AS default
