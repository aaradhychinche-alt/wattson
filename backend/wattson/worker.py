"""Temporal worker entry point."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from temporalio.client import Client
from temporalio.worker import Worker

from .config import get_settings
from .workflow_activities import (
    analyze_plan,
    build_report,
    cleanup,
    collect_results,
    compare_results,
    execute_candidate,
    finalize,
    generate_candidates,
    load_baseline,
    record_stage,
    request_approval,
    revalidate,
    simulate_candidates,
    validate_plan,
    validate_proposal,
)
from .workflows import OptimizationWorkflow

ACTIVITIES: list[Callable[..., Any]] = [
    record_stage,
    validate_plan,
    load_baseline,
    generate_candidates,
    analyze_plan,
    validate_proposal,
    simulate_candidates,
    request_approval,
    revalidate,
    execute_candidate,
    collect_results,
    compare_results,
    build_report,
    cleanup,
    finalize,
]


async def main() -> None:
    settings = get_settings()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    client = await Client.connect(
        settings.wattson_temporal_host, namespace=settings.wattson_temporal_namespace
    )
    worker = Worker(
        client,
        task_queue=settings.wattson_temporal_task_queue,
        workflows=[OptimizationWorkflow],
        activities=ACTIVITIES,
        activity_executor=ThreadPoolExecutor(max_workers=8),
    )
    logging.getLogger("wattson.worker").info(
        "Worker polling task queue %s", settings.wattson_temporal_task_queue
    )
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
