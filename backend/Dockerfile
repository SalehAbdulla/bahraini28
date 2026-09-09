# syntax=docker/dockerfile:1
# Production image for the Bahraini 28 FastAPI backend.
#
# Runs ONE uvicorn worker on purpose: the SSE admin feed uses an in-process
# pub/sub bus. Before scaling to multiple workers, swap that bus for a shared
# one (Redis pub/sub) — same API surface.
FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY scripts ./scripts

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
