# AI Task Bot

Omni-channel task management: create tasks from a Telegram bot by text or voice, see them appear instantly on a web Kanban dashboard, and move them between Pending, In Progress and Completed.

> Status: milestone 3 (text bot). Voice worker and dashboard are coming in the next milestones.

## Stack

- **Backend**: Python 3.12, FastAPI, SQLAlchemy 2 (async) + Alembic, aiogram 3, arq
- **Transcription**: faster-whisper running locally on CPU (free, offline; no API key)
- **Storage**: PostgreSQL 16, Redis 7 (job queue + pub/sub for real-time events)
- **Frontend**: React + Vite + TypeScript
- **Deployment**: Docker Compose, one command

## Quick start

Requirements: Docker with Compose v2. The only credential is a free Telegram bot token from [@BotFather](https://t.me/BotFather).

```bash
cp .env.example .env        # put your TELEGRAM_BOT_TOKEN in .env
docker compose up --build
```

Then:

- API health: http://localhost:8000/api/health
- API docs: http://localhost:8000/docs

## Architecture

_(diagram and walkthrough added in milestone 6)_

## Development

```bash
make up       # build + start in the background
make logs     # follow logs
make test     # backend tests
make lint
make down
```

## Design decisions

_(filled in as milestones land)_
