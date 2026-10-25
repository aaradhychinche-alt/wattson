"""Integration health checks. Never claims a connection that was not probed."""

from __future__ import annotations

from typing import Any

import httpx
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import utcnow
from ..models import IntegrationHealth
from ..providers import get_provider
from ..providers.kepler import KeplerClient


def _ai_status() -> dict[str, Any]:
    settings = get_settings()
    if settings.wattson_ai_provider == "none":
        return {
            "integration": "gemma",
            "status": "disconnected",
            "detail": "Gemma is not configured. Deterministic analysis is active.",
            "provenance": "calculated",
            "meta": {"fallback": "deterministic"},
        }
    if not settings.gemma_model:
        return {
            "integration": "gemma",
            "status": "error",
            "detail": "AI provider selected but GEMMA_MODEL is empty.",
            "provenance": "measured",
            "meta": {"provider": settings.wattson_ai_provider},
        }
    if settings.wattson_ai_provider == "hosted":
        if not settings.hosted_gemma_api_key:
            return {
                "integration": "gemma",
                "status": "disconnected",
                "detail": "Hosted Gemma selected but HOSTED_GEMMA_API_KEY is empty.",
                "provenance": "measured",
                "meta": {"provider": "hosted", "model": settings.gemma_model},
            }
        return {
            "integration": "gemma",
            "status": "disconnected",
            "detail": (
                "Hosted Gemma is configured but not live-probed "
                "(no paid probe on health checks)."
            ),
            "provenance": "measured",
            "meta": {
                "provider": "hosted",
                "model": settings.gemma_model,
                "verification": "configured_unverified",
            },
        }
    try:
        response = httpx.get(f"{settings.ollama_base_url.rstrip('/')}/api/tags", timeout=2.0)
        response.raise_for_status()
        models = [m.get("name", "") for m in response.json().get("models", [])]
    except Exception as exc:
        return {
            "integration": "gemma",
            "status": "error",
            "detail": f"Ollama not reachable: {type(exc).__name__}",
            "provenance": "measured",
            "meta": {"provider": "ollama", "model": settings.gemma_model},
        }
    present = any(
        name == settings.gemma_model or name.startswith(settings.gemma_model + ":")
        for name in models
    )
    if not present:
        return {
            "integration": "gemma",
            "status": "error",
            "detail": f"Ollama is running but model {settings.gemma_model!r} is not pulled.",
            "provenance": "measured",
            "meta": {"provider": "ollama", "model": settings.gemma_model},
        }
    return {
        "integration": "gemma",
        "status": "connected",
        "detail": f"Local open-weight {settings.gemma_model} is available via Ollama.",
        "provenance": "measured",
        "meta": {"provider": "ollama", "model": settings.gemma_model},
    }


def collect_integration_statuses(
    session: Session, *, temporal_ok: bool | None
) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    try:
        session.execute(text("SELECT 1"))
        checks.append(
            {
                "integration": "database",
                "status": "connected",
                "detail": get_settings().wattson_database_url.split("://", 1)[0],
                "provenance": "measured",
                "meta": {},
            }
        )
    except Exception as exc:
        checks.append(
            {
                "integration": "database",
                "status": "error",
                "detail": f"database check failed: {type(exc).__name__}",
                "provenance": "measured",
                "meta": {},
            }
        )
    checks.append(
        {
            "integration": "temporal",
            "status": "connected" if temporal_ok else "disconnected",
            "detail": (
                "Temporal server reachable."
                if temporal_ok
                else "Temporal server not reachable; workflows cannot start."
            ),
            "provenance": "measured",
            "meta": {"host": get_settings().wattson_temporal_host},
        }
    )
    provider = get_provider().status()
    checks.append(
        {
            "integration": "provider",
            "status": provider.get("status", "error"),
            "detail": provider.get("detail", ""),
            "provenance": provider.get("provenance", "measured"),
            "meta": {"provider": provider.get("provider")},
        }
    )
    checks.append(_ai_status())
    kepler = KeplerClient().status()
    checks.append(
        {
            "integration": "kepler",
            "status": kepler.get("status", "error"),
            "detail": kepler.get("detail", ""),
            "provenance": kepler.get("provenance", "measured"),
            "meta": {},
        }
    )

    rows: list[dict[str, Any]] = []
    for check in checks:
        row = session.scalar(
            select(IntegrationHealth).where(
                IntegrationHealth.integration == check["integration"]
            )
        )
        if row is None:
            row = IntegrationHealth(integration=check["integration"])
            session.add(row)
        row.status = check["status"]
        row.detail = check["detail"]
        row.provenance = check["provenance"]
        row.meta = check.get("meta", {})
        row.checked_at = utcnow()
        rows.append(
            {
                "integration": row.integration,
                "status": row.status,
                "detail": row.detail,
                "provenance": row.provenance,
                "meta": row.meta,
                "checked_at": row.checked_at,
            }
        )
    session.commit()
    return rows
