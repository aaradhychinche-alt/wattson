"""FastAPI application factory with a consistent error envelope."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .. import __version__
from ..config import get_settings
from ..db import configure_database, get_engine
from ..models import Base
from ..temporal_client import TemporalGateway
from .deps import APIError
from .routes import router

logger = logging.getLogger("wattson.api")


def _error(status: int, code: str, message: str, details: Any | None = None) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"error": {"code": code, "message": message, "details": jsonable_encoder(details)}},
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_database(settings.wattson_database_url)
    # Alembic remains the migration source of truth; create_all only makes a
    # clean local database usable before the first migration command.
    Base.metadata.create_all(get_engine())
    gateway = TemporalGateway()
    try:
        await gateway.connect()
    except Exception:
        gateway.client = None
    app.state.temporal = gateway
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="WATTSON API",
        version=__version__,
        description=(
            "Evidence-based closed loop for AI workload optimization. "
            "All simulator metrics are labelled simulated."
        ),
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @app.exception_handler(APIError)
    async def _api_error(_request: Request, exc: APIError) -> JSONResponse:
        return _error(exc.status_code, exc.code, exc.message, exc.details)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
        return _error(
            422,
            "validation_error",
            "Request validation failed.",
            [
                {
                    "loc": list(err.get("loc", [])),
                    "msg": err.get("msg", ""),
                    "type": err.get("type", ""),
                }
                for err in exc.errors()
            ],
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return _error(exc.status_code, "http_error", str(exc.detail))

    @app.exception_handler(Exception)
    async def _unhandled(_request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled API error")
        return _error(500, "internal_error", "An internal error occurred.")

    app.include_router(router)
    return app


app = create_app()
