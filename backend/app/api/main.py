"""FastAPI application: REST API + WebSocket event stream."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import ws
from app.api.errors import install_error_handlers
from app.api.routers import health, tasks, users
from app.core import queue
from app.core.config import get_settings
from app.core.db import engine
from app.core.logging import configure_logging, get_logger
from app.core.redis import redis

settings = get_settings()
configure_logging(settings.log_level)
log = get_logger("api")


@asynccontextmanager
async def lifespan(_: FastAPI):
    await ws.broadcaster.start()
    log.info("api.start")
    yield
    await ws.broadcaster.stop()
    await queue.close_pool()
    await engine.dispose()
    await redis.aclose()
    log.info("api.stop")


app = FastAPI(title="AI Task Bot API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_methods=["*"],
    allow_headers=["*"],
)
install_error_handlers(app)
app.include_router(health.router)
app.include_router(tasks.router)
app.include_router(users.router)
app.include_router(ws.router)
