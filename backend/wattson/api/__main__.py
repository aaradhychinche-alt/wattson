"""ASGI entrypoint: uvicorn wattson.api.app:app."""

from .app import app

__all__ = ["app"]
