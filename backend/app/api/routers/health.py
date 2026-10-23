from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.core.db import check_db
from app.core.redis import check_redis

router = APIRouter(tags=["health"])


@router.get("/api/health")
async def health() -> JSONResponse:
    db_ok, redis_ok = await check_db(), await check_redis()
    ok = db_ok and redis_ok
    return JSONResponse(
        status_code=200 if ok else 503,
        content={"status": "ok" if ok else "degraded", "db": db_ok, "redis": redis_ok},
    )
