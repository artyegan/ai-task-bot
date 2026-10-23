# AI Task Bot

Omni-channel task management: create tasks from a Telegram bot by **text or voice**, watch them appear instantly on a **real-time Kanban dashboard**, and move them between *Pending*, *In Progress* and *Completed* from either side.

Everything runs locally with one command and costs nothing: voice notes are transcribed by an open-source Whisper model inside the worker container, so the only credential needed is a free Telegram bot token.

## Quick start

Requirements: Docker with Compose v2 (Docker Desktop, Colima, OrbStack…). About 2 GB of free disk for the images.

```bash
cp .env.example .env              # put your TELEGRAM_BOT_TOKEN in .env (free, from @BotFather)
docker compose up --build         # first build downloads the Whisper model once (~480 MB)
```

When `docker compose ps` shows every service healthy:

| What | Where |
|---|---|
| Dashboard | http://localhost:3000 |
| API docs (OpenAPI) | http://localhost:8000/docs |
| API health | http://localhost:8000/api/health |
| Bot | the username @BotFather gave you |

### Two-minute demo

1. Open the dashboard. The dot next to the title turns green ("Live").
2. Send the bot `/start`, then a text such as *Buy milk*. The task appears on the board instantly, with a toast.
3. Send a voice note. The bot answers **"🎤 Got it, transcribing…"** at once; a few seconds later that message changes to **"✅ Task #2 created from voice: …"** and the task shows up with a 🎤 badge.
4. Drag the card to *In Progress* (or click its button). Telegram receives **"🔄 Task #2 moved to In Progress"**.
5. Send `/list`, then `/done 2`. The card jumps to *Completed* on the board.
6. Resilience: `docker compose stop api` turns the dot red ("Reconnecting"); `docker compose start api` brings it back and the board refetches by itself.

## Architecture

```mermaid
flowchart LR
    TG[Telegram] -->|long polling| BOT[bot<br/>aiogram]
    BOT -->|text → task| PG[(PostgreSQL)]
    BOT -->|voice → job| RQ[(Redis<br/>arq queue + pub/sub)]
    RQ -->|transcribe_voice| WK[worker<br/>arq + faster-whisper]
    WK -->|download audio| TG
    WK -->|task| PG
    WK -->|send_notification| RQ
    RQ -->|notification| WK --> TG
    BOT -. task.created .-> RQ
    WK -. task.created .-> RQ
    API[api<br/>FastAPI] -. subscribe .-> RQ
    API --> PG
    API -->|REST + WebSocket| WEB[web<br/>nginx + React]
    WEB -->|PATCH status| API
    API -->|send_notification| RQ
```

Seven containers, all defined in [`docker-compose.yml`](docker-compose.yml):

| Service | Image | Role |
|---|---|---|
| `postgres` | postgres:16-alpine | users, tasks, voice jobs |
| `redis` | redis:7-alpine | arq job queue **and** pub/sub channel for real-time events |
| `migrate` | backend `app` target | one-shot `alembic upgrade head`; the others wait for it to finish |
| `api` | backend `app` target | REST API + WebSocket fan-out of events |
| `bot` | backend `app` target | Telegram long polling; text → task, voice → queued job |
| `worker` | backend `worker` target | transcription and notification jobs; Whisper model baked in |
| `web` | nginx + built SPA | dashboard; proxies `/api` and `/ws` to `api` (same origin) |

The three backend services are one Python package with three entrypoints sharing `app/core` (models, the task service, events, queue, messages). Task creation has exactly one code path, whether it starts from text, voice, or the dashboard.

### A voice note, end to end

1. **bot** receives the voice message and answers *"🎤 Got it, transcribing…"* **before** touching the database, so feedback is immediate. It then stores a `voice_jobs` row and enqueues `transcribe_voice(job_id)`.
2. **worker** picks the job up: marks it `processing`, downloads the audio from Telegram, runs faster-whisper in a thread (one at a time, behind a semaphore, so notifications keep flowing), creates the task through the shared service, marks the job `done` and enqueues `send_notification`.
3. The task service commits, then publishes `task.created` on the Redis `events` channel.
4. **api** holds one Redis subscription per process and pushes the event to every WebSocket client; the dashboard patches its list in place and shows a toast.
5. **worker** runs `send_notification`, which edits the original *"transcribing…"* message into *"✅ Task #N created from voice: …"*.

Failure handling along that path:

| Failure | Behaviour |
|---|---|
| File larger than 20 MB | rejected by the bot before download; user told the limit |
| Telegram download error, network error | retried 3× with 2 s / 8 s / 30 s backoff, then failed with *"could not download the audio"* |
| Model error | same retry policy, then *"transcription failed"* |
| No speech in the audio | failed immediately with *"no speech detected"* (no retries, nothing to gain) |
| Job retried after a crash | idempotent: a job already `done` returns without creating a second task |
| Telegram unreachable when notifying | separate job, 5 retries with backoff; `Retry-After` from Telegram is honoured |
| Message to edit was deleted by the user | falls back to sending a new message |
| Worker restarts | the model loads at startup; the container reports healthy only after that |

Every voice job keeps its state (`queued → processing → done | failed`), attempt count and failure code in `voice_jobs` for inspection.

## Project layout

```
backend/
  app/core/        config, db, models, schemas, services/{tasks,voice}.py, events, queue, messages
  app/api/         FastAPI app, routers (tasks, users, health), WebSocket broadcaster, error envelope
  app/bot/         aiogram entrypoint, middleware (session + user), handlers (commands, text, voice)
  app/worker/      arq entrypoint, jobs (transcribe, notify), transcribers (local_whisper, openai_compatible, fake)
  alembic/         migrations (async env)
  tests/           pytest against real Postgres + Redis (dedicated test database)
  Dockerfile       targets: app, worker (with model), dev
frontend/
  src/lib          API client + types, event reducer (unit-tested)
  src/hooks        useTasks (TanStack Query), useTaskSocket (reconnecting WebSocket)
  src/components   Board, Column, TaskCard, ListView, Toolbar, Toast
  Dockerfile       node build → nginx
docker-compose.yml, Makefile, .env.example
```

## API

| Method | Path | Notes |
|---|---|---|
| GET | `/api/tasks` | `status=` (repeatable), `user_id=`, `limit=`, `offset=`; newest first |
| POST | `/api/tasks` | `{title, user_id, description?}` |
| GET | `/api/tasks/{id}` | |
| PATCH | `/api/tasks/{id}` | `{status?, title?, description?}`; a status change notifies the owner in Telegram |
| DELETE | `/api/tasks/{id}` | |
| GET | `/api/users` | everyone who has messaged the bot |
| GET | `/api/health` | `503` with `db`/`redis` flags when degraded |
| WS | `/ws` | events: `task.created`, `task.updated`, `task.deleted`, `voice.failed` |

Errors are always `{"error": {"code", "message", "details?"}}`. Full schema at `/docs`.

Tasks carry two identifiers: `id` is global (API, dashboard); `number` counts from 1 **per user** and is what the bot shows, so `/done 3` means *your* third task. Numbers are assigned under a row lock on the user, so concurrent messages never collide.

## Bot commands

| Command | Effect |
|---|---|
| `/start` | registers you, shows help |
| any text | creates a task |
| voice note or audio file | creates a task from the transcript |
| `/list` | your open tasks |
| `/done <number>` | marks your task completed |

## Configuration

Everything is read from `.env` (see [`.env.example`](.env.example)). Only the token is required.

| Variable | Default | Purpose |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | — | from @BotFather |
| `TRANSCRIBER` | `local` | `local` (faster-whisper, offline), `openai_compatible` (e.g. Groq's free tier), `fake` (tests) |
| `WHISPER_MODEL` | `small` | also a build arg: `tiny`/`base`/`small`/`medium` |
| `WHISPER_COMPUTE_TYPE` | `int8` | CPU-friendly quantisation |
| `WHISPER_LANGUAGE` | auto | force a language code, e.g. `en` |
| `WHISPER_INITIAL_PROMPT` | a to-do sentence | primes the model so *buy* beats *bye* on short clips |
| `OPENAI_COMPAT_*` | — | base URL, key, model for the OpenAI-compatible adapter |
| `MAX_VOICE_BYTES` | 20 MB | Telegram's bot download limit |
| `LOG_LEVEL` | `INFO` | |

To use a smaller model: `WHISPER_MODEL=base docker compose up --build`.

## Development

```bash
make up        # docker compose up --build -d
make logs
make test      # backend tests against real Postgres + Redis (separate test database)
make lint      # ruff
make web-test  # frontend unit tests + typecheck (needs node)
make reset     # stop and delete the database volume
```

Frontend with hot reload against the API in Docker: `cd frontend && npm install && npm run dev` → http://localhost:5173.

Tests: 42 backend tests (service layer, API, WebSocket events, bot handlers with a stubbed Telegram message, worker jobs with a stubbed Telegram client and the fake transcriber) and 4 frontend unit tests.

## Design decisions and trade-offs

- **Everything free, nothing external.** Transcription runs locally with [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (CTranslate2, int8 on CPU). A 3-second voice note takes about 4 seconds end to end on a laptop. The OpenAI-compatible adapter exists for anyone with a Groq or OpenAI key, but nothing depends on it.
- **The model is baked into the worker image**, in its own build stage, so code or dependency changes never trigger a re-download, and the first voice note is as fast as the tenth. Price: the worker image is ~1.1 GB (api and bot are ~360 MB each, web 76 MB). A volume-cached model would make the image small but the first `up` slow and the demo offline-fragile.
- **Blocking inference never blocks the event loop.** arq runs jobs as coroutines; inference runs in a thread behind a semaphore of 1. Notification jobs keep flowing while a transcription runs. CTranslate2 releases the GIL, so a thread is enough; no process pool.
- **One Redis, two roles.** arq's queue for work that must happen (durable, retried) and a pub/sub channel for events that are nice to have (a missed event is recovered by the dashboard's refetch on reconnect). Events are published only after the commit, by the service, so every writer behaves the same.
- **Two separate jobs** (`transcribe_voice`, `send_notification`) so a Telegram outage never blocks the model and vice versa, and each gets its own timeout and retry policy.
- **Per-user task numbers** on top of the global id: a user's first task is #1 in their chat regardless of how many other users exist.
- **Idempotency over exactly-once.** A retried job checks the voice job's state before creating anything.
- **Compose ordering is explicit.** `migrate` is a one-shot container; the others use `service_completed_successfully` on it and `service_healthy` on Postgres and Redis. The worker's healthcheck passes only after the model is loaded.
- **Dependencies are bounded.** Every runtime dependency has an upper bound; a floating major (PyAV 19) broke decoding once during development. The frontend has a lockfile.
- **No authentication.** The brief describes a single shared board, so the dashboard is a trusted internal view. Adding auth would be the first step towards multi-tenancy, which is out of scope.
- **No platform pin.** CTranslate2 and PyAV ship native arm64 and x86-64 wheels; the image builds natively on Apple Silicon and on Intel.

### Known limitations

- Whisper `small` mishears very short clips occasionally (*"bye butter"*). The initial prompt fixes most of these; `WHISPER_MODEL=medium` fixes more at ~3× the size and CPU time.
- Telegram limits bot downloads to 20 MB (roughly 20 minutes of voice).
- Voice notes are processed one at a time per worker. Scale by running more worker containers (`docker compose up --scale worker=2`); arq handles the distribution.
- The dashboard loads up to 500 tasks; there is no pagination in the UI.
