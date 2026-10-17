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
    from packages.operations.service import BusinessError
    from fastapi.responses import JSONResponse
    from sqlalchemy.exc import IntegrityError, DBAPIError

    @app.exception_handler(BusinessError)
    async def business_error(request, exc):
        return JSONResponse(
            status_code=exc.status,
            content={"error": {"code": exc.code, "message": exc.message}},
        )

    @app.exception_handler(IntegrityError)
    async def integrity_error(request, exc):
        return JSONResponse(
            status_code=409,
            content={
                "error": {
                    "code": "write_conflict",
                    "message": "Conflicting record; reload before retrying",
                }
            },
        )

    @app.exception_handler(DBAPIError)
    async def database_error(request, exc):
        return JSONResponse(
            status_code=503,
            content={
                "error": {
                    "code": "storage_unavailable",
                    "message": "Storage busy/unavailable; retry with the same idempotency key",
                }
            },
        )

    app.include_router(api_router)
    return app


app = create_app()
