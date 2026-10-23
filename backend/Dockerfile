# syntax=docker/dockerfile:1.7
# Multi-stage build. Targets:
#   app    - api, bot and migrate (no ML libraries, ~360 MB)
#   worker - app deps + faster-whisper + baked Whisper model (~1.1 GB)
#   dev    - app + pytest/ruff, used by `make test` and `make lint`
#
# Dependencies are installed from pyproject.toml via a stub package that is uninstalled
# again, so site-packages holds only third-party code and /srv/app is the one `app`.

FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/srv \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /srv
RUN useradd --create-home --uid 1000 app
COPY pyproject.toml ./
RUN mkdir -p app && touch app/__init__.py \
    && pip install . && pip uninstall -y ai-task-bot && rm -rf app

FROM base AS app
COPY --chown=app:app alembic.ini ./
COPY --chown=app:app alembic ./alembic
COPY --chown=app:app app ./app
USER app

# Tests + lint (never shipped).
FROM base AS dev
RUN mkdir -p app && touch app/__init__.py \
    && pip install ".[dev]" && pip uninstall -y ai-task-bot && rm -rf app
COPY --chown=app:app app ./app
COPY --chown=app:app tests ./tests
USER app
CMD ["pytest", "-q"]

# The Whisper model, downloaded in a stage of its own so that dependency or code changes
# never invalidate it. WHISPER_MODEL: tiny|base|small|medium (CTranslate2 builds by Systran).
FROM python:3.12-slim AS model
ARG WHISPER_MODEL=small
ENV HF_HUB_DISABLE_TELEMETRY=1
RUN pip install --no-cache-dir "huggingface_hub>=0.25" \
    && python -c "from huggingface_hub import snapshot_download; \
snapshot_download('Systran/faster-whisper-${WHISPER_MODEL}', local_dir='/models/${WHISPER_MODEL}', \
allow_patterns=['config.json', 'preprocessor_config.json', 'model.bin', 'tokenizer.json', 'vocabulary.*'])" \
    && du -sh /models/${WHISPER_MODEL}

# Worker: transcription + notification jobs.
FROM base AS worker
ARG WHISPER_MODEL=small
ENV WHISPER_MODEL=${WHISPER_MODEL} \
    WHISPER_MODEL_DIR=/models
RUN mkdir -p app && touch app/__init__.py \
    && pip install ".[worker]" && pip uninstall -y ai-task-bot && rm -rf app
COPY --from=model /models /models
COPY --chown=app:app app ./app
USER app
CMD ["arq", "app.worker.main.WorkerSettings"]
