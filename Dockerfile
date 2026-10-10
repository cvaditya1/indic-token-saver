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

# Heavy image with IndicTrans2 dependencies. Not the default target.
# docker build --target translate -t indic-token-saver:translate .
FROM base AS translate
USER root
COPY requirements-translate.txt .
RUN pip install --no-cache-dir -r requirements-translate.txt
USER appuser

# Last stage is the default `docker build .` image: no torch.
FROM base AS slim
