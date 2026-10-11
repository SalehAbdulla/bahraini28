# syntax=docker/dockerfile:1
# Production image for the Bahraini 28 FastAPI backend.
#
# Runs ONE uvicorn worker on purpose: the SSE admin feed uses an in-process
# pub/sub bus. Before scaling to multiple workers, swap that bus for a shared
# one (Redis pub/sub) - same API surface.
FROM python:3.14-slim

# PYTHONPATH=/srv so `python scripts/<name>.py` can `import app`: uvicorn inserts
# "." on sys.path itself, but a plain `python path/to/script.py` puts the
# *script's* directory there instead of the working directory - without this the
# seed/migration scripts fail with ModuleNotFoundError: No module named 'app'.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/srv

WORKDIR /srv

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY scripts ./scripts
# `scripts/seed_areas.py` reads data/bahrain_areas.csv (tracked in git), so the
# data dir has to be in the image for the documented seed command to work.
COPY data ./data

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
