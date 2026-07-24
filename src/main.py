from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

import src.models
from src.api.routes import (
    allocations,
    experiments,
    observations,
)
from src.config import settings
from src.core.database import engine
from src.core.exceptions import AppException
from src.core.logging import configure_logging, get_logger
from src.models import Base


configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(
    app: FastAPI,
) -> AsyncIterator[None]:
    logger.info("Starting application")

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    yield

    logger.info("Shutting down application")
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.api.title,
        version=settings.api.version,
        debug=settings.api.debug,
        docs_url=settings.api.docs_url,
        redoc_url=settings.api.redoc_url,
        lifespan=lifespan,
    )

    app.include_router(
        experiments.router,
        prefix="/experiments",
        tags=["Experiments"],
    )

    app.include_router(
        observations.router,
        prefix="/experiments",
        tags=["Observations"],
    )

    app.include_router(
        allocations.router,
        prefix="/experiments",
        tags=["Allocations"],
    )

    register_exception_handlers(app)

    return app


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppException)
    async def handle_app_exception(
        request: Request,
        exception: AppException,
    ) -> JSONResponse:
        logger.warning(
            "Application error on %s: %s",
            request.url.path,
            exception.message,
        )

        content: dict[str, object] = {
            "detail": exception.message,
        }

        if exception.details is not None:
            content["details"] = exception.details

        return JSONResponse(
            status_code=exception.status_code,
            content=content,
        )


app = create_app()


@app.get(
    "/health",
    tags=["System"],
)
async def health_check() -> dict[str, str]:
    return {
        "status": "healthy",
        "environment": settings.environment,
        "version": settings.api.version,
    }