import asyncio
import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.database import init_db
from app.logging_config import configure_logging, request_id_ctx
from app.redis_client import close_redis
from app.routers import health, items

settings = get_settings()
configure_logging(settings.log_level)
logger = logging.getLogger(__name__)


async def _init_db_with_retry(attempts: int = 5, delay: float = 2.0) -> None:
    """Best-effort schema bootstrap.

    On a fresh deploy the database may not be reachable the instant the app
    boots. Retry a few times, but never let a DB hiccup crash startup — the
    app must still bind to $PORT so the platform healthcheck can succeed.
    /ready reports the real dependency status.
    """
    for attempt in range(1, attempts + 1):
        try:
            await init_db()
            logger.info("database initialized")
            return
        except Exception:
            logger.warning(
                "database init failed; will retry",
                extra={"attempt": attempt, "max_attempts": attempts},
                exc_info=True,
            )
            if attempt < attempts:
                await asyncio.sleep(delay)
    logger.error("database init gave up; starting anyway (see /ready)")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("starting up", extra={"environment": settings.environment})
    await _init_db_with_retry()
    yield
    await close_redis()
    logger.info("shutdown complete")


app = FastAPI(title=settings.app_name, lifespan=lifespan)


@app.middleware("http")
async def request_context(request: Request, call_next):
    """Attach a request id, time the request, and log the outcome."""
    request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
    token = request_id_ctx.set(request_id)
    start = time.perf_counter()

    try:
        response = await call_next(request)
    except Exception:
        elapsed = (time.perf_counter() - start) * 1000
        logger.exception(
            "unhandled error",
            extra={
                "method": request.method,
                "path": request.url.path,
                "duration_ms": round(elapsed, 2),
            },
        )
        # Log while request_id is still set in context, then reset.
        request_id_ctx.reset(token)
        return JSONResponse(
            status_code=500, content={"detail": "internal server error"}
        )

    elapsed = (time.perf_counter() - start) * 1000
    response.headers["x-request-id"] = request_id
    logger.info(
        "request completed",
        extra={
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": round(elapsed, 2),
        },
    )
    request_id_ctx.reset(token)
    return response


app.include_router(health.router)
app.include_router(items.router)
