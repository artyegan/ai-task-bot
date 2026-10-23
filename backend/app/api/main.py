"""FastAPI application: REST API + WebSocket event stream."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.db import check_db, engine
from app.core.logging import configure_logging, get_logger
from app.core.redis import check_redis, redis

settings = get_settings()
configure_logging(settings.log_level)
log = get_logger("api")


@asynccontextmanager
async def lifespan(_: FastAPI):
    log.info("api.start")
    yield
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


@app.get("/api/health")
async def health() -> JSONResponse:
    db_ok, redis_ok = await check_db(), await check_redis()
    ok = db_ok and redis_ok
    return JSONResponse(
        status_code=200 if ok else 503,
        content={"status": "ok" if ok else "degraded", "db": db_ok, "redis": redis_ok},
    )
