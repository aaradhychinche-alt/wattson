"""Shared API dependencies and error shape."""

from __future__ import annotations

import secrets
from typing import Any

from fastapi import Header, Request
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..temporal_client import TemporalGateway


class APIError(Exception):
    def __init__(
        self, status_code: int, code: str, message: str, details: Any | None = None
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details
        super().__init__(message)


def require_token(authorization: str | None = Header(default=None)) -> str:
    settings = get_settings()
    if not settings.wattson_api_token:
        raise APIError(
            503,
            "auth_not_configured",
            "WATTSON_API_TOKEN is not configured on the server.",
        )
    scheme, _, value = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not value:
        raise APIError(401, "unauthorized", "A Bearer token is required.")
    if not secrets.compare_digest(value, settings.wattson_api_token):
        raise APIError(401, "unauthorized", "Invalid API token.")
    return "api-token"


def gateway(request: Request) -> TemporalGateway:
    return request.app.state.temporal


__all__ = ["APIError", "get_db", "require_token", "gateway", "Session"]
