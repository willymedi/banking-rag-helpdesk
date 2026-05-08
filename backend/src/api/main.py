from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from src.api.container import get_container, get_settings
from src.api.middleware.rate_limit import build_limiter
from src.api.middleware.request_id import RequestIdMiddleware
from src.api.routes import feedback, health, ingest, query
from src.infrastructure.observability.structlog_config import configure_logging

log = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging(get_settings().log_level)
    container = get_container()
    try:
        await container.warm_bm25()
    except Exception as exc:
        log.warning("startup.bm25_warm_failed", err=str(exc))
    log.info("startup.complete", agents=container.orchestrator.agent_names)
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Mesa de Ayuda IA — Banco", version="0.1.0", lifespan=lifespan)

    limiter = build_limiter()
    app.state.limiter = limiter

    @app.exception_handler(RateLimitExceeded)
    async def _rate_limit_handler(request: Request, exc: RateLimitExceeded):
        return JSONResponse(status_code=429, content={"detail": "rate limit exceeded"})

    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(query.router)
    app.include_router(feedback.router)
    app.include_router(ingest.router)
    return app


app = create_app()
