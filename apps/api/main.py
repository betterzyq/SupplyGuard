"""SupplyGuard FastAPI application."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.api.middleware.logging import LoggingContextMiddleware
from apps.api.middleware.request_id import RequestIdMiddleware
from apps.api.middleware.trace_finalize import TraceFinalizeMiddleware
from apps.api.routers.v1.router import api_router
from packages.common.cache.redis_client import close_redis
from packages.common.config import get_settings
from packages.common.db.session import close_postgres
from packages.common.graph.neo4j_client import close_neo4j
from packages.common.logging import get_logger, setup_logging
from packages.common.vector.qdrant_client import close_qdrant
from packages.observability.callbacks import setup_langsmith_tracing

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    setup_langsmith_tracing()
    logger.info(
        "application_startup app_name={} env={}",
        settings.APP_NAME,
        settings.APP_ENV,
    )
    yield
    await close_postgres()
    await close_redis()
    await close_qdrant()
    await close_neo4j()
    logger.info("application_shutdown")


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging(debug=settings.DEBUG)

    app = FastAPI(
        title=settings.APP_NAME,
        version="0.1.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:3001",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(TraceFinalizeMiddleware)
    app.add_middleware(LoggingContextMiddleware)
    app.add_middleware(RequestIdMiddleware)
    app.include_router(api_router)
    return app


app = create_app()
