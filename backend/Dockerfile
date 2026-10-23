# syntax=docker/dockerfile:1.7
# Multi-stage build. Targets:
#   app    - api and bot (no ML libraries, ~250 MB)
#   worker - app + faster-whisper + baked Whisper model (added in milestone 4)
#   dev    - app + pytest/ruff, used by `make test` and `make lint`

FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /srv
RUN useradd --create-home --uid 1000 app

# Install dependencies first so code changes don't invalidate this layer.
COPY pyproject.toml ./
RUN mkdir -p app && touch app/__init__.py && pip install . && rm -rf app

FROM base AS app
COPY --chown=app:app app ./app
USER app

# Tests + lint (never shipped). `make test` builds and runs this target.
FROM base AS dev
RUN mkdir -p app && touch app/__init__.py && pip install ".[dev]" && rm -rf app
COPY --chown=app:app app ./app
COPY --chown=app:app tests ./tests
USER app
CMD ["pytest", "-q"]
