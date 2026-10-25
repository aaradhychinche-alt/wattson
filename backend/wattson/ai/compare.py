"""Optional side-by-side analysis comparison: deterministic baseline vs Gemma.

This command never presents model output as measured data and never lets model
output change a plan. It is a diagnostic for operators who have configured
Gemma and want to inspect the two analyses next to each other.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from sqlalchemy import select

from ..config import Settings, get_settings
from ..db import session_scope
from ..models import Workload
from .provider import fallback_analysis, get_model_provider


def compare_analysis(
    workload: dict[str, Any],
    logs: str,
    settings: Settings | None = None,
) -> dict[str, Any]:
    deterministic = fallback_analysis(workload, logs, "Deterministic comparison baseline")
    result: dict[str, Any] = {
        "workload": {
            "id": workload.get("id", ""),
            "name": workload.get("name", ""),
            "provider": workload.get("provider", ""),
        },
        "deterministic": {
            "source": deterministic.source,
            "provider": deterministic.provider,
            "model": deterministic.model,
            "input_flags": deterministic.input_flags,
            "payload": deterministic.payload.model_dump(mode="json"),
        },
        "gemma": {
            "status": "unavailable",
            "reason": "Gemma is not configured. Set WATTSON_AI_PROVIDER and GEMMA_MODEL.",
            "provider": None,
            "model": None,
            "payload": None,
        },
        "comparison_note": (
            "Side-by-side inspection only. The deterministic optimizer, policy validation, "
            "and persisted approval remain authoritative. Model output cannot change constraints."
        ),
    }

    provider = get_model_provider(settings)
    if provider is None:
        return result

    try:
        payload = provider.analyze(workload, logs)
        result["gemma"] = {
            "status": "available",
            "reason": None,
            "provider": provider.name,
            "model": provider.model,
            "payload": payload.model_dump(mode="json"),
        }
    except Exception as exc:
        # The error type/message is useful for diagnosis; the raw response is
        # never echoed because it may contain untrusted content.
        result["gemma"] = {
            "status": "error",
            "reason": f"{type(exc).__name__}: {exc}"[:500],
            "provider": provider.name,
            "model": provider.model,
            "payload": None,
        }
    return result


def _load_workload(workload_id: str | None) -> tuple[dict[str, Any], str]:
    session = session_scope()
    try:
        query = select(Workload).order_by(Workload.created_at.desc())
        if workload_id:
            query = query.where(Workload.id == workload_id)
        workload = session.scalar(query.limit(1))
        if workload is None:
            raise LookupError(
                "No workload found. Seed the demo first (uv run wattson-demo) or pass a valid "
                "--workload-id."
            )
        data = {
            "id": workload.id,
            "name": workload.name,
            "description": workload.description,
            "workload_type": workload.workload_type,
            "provider": workload.provider,
            "current_config": workload.current_config,
            "constraints": workload.constraints,
            "meta": workload.meta,
        }
        return data, str((workload.meta or {}).get("logs") or "")
    finally:
        session.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compare deterministic analysis with optional Gemma output for one workload."
    )
    parser.add_argument("--workload-id", default=None, help="Workload id (defaults to newest).")
    args = parser.parse_args(argv)

    try:
        workload, logs = _load_workload(args.workload_id)
    except Exception as exc:
        print(f"WATTSON gemma comparison unavailable: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    result = compare_analysis(workload, logs, get_settings())
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
