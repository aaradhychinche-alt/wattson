"""Temporal client gateway for API and demo orchestration."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Any

from temporalio.client import Client
from temporalio.common import WorkflowIDConflictPolicy

from .config import get_settings


class TemporalUnavailable(RuntimeError):
    pass


class TemporalGateway:
    def __init__(self) -> None:
        self.client: Client | None = None

    async def connect(self) -> None:
        settings = get_settings()
        try:
            self.client = await asyncio.wait_for(
                Client.connect(
                    settings.wattson_temporal_host,
                    namespace=settings.wattson_temporal_namespace,
                ),
                timeout=5.0,
            )
        except Exception as exc:
            self.client = None
            raise TemporalUnavailable(f"Temporal unavailable: {type(exc).__name__}") from exc

    async def health(self) -> bool:
        if self.client is None:
            return False
        try:
            await asyncio.wait_for(self.client.service_client.check_health(), timeout=2.0)
            return True
        except Exception:
            return False

    def _require(self) -> Client:
        if self.client is None:
            raise TemporalUnavailable("Temporal client is not connected")
        return self.client

    async def start_optimization(
        self, proposal_id: str, approval_timeout_seconds: int
    ) -> str:
        settings = get_settings()
        client = self._require()
        workflow_id = f"optimization-{proposal_id}"
        await client.start_workflow(
            "OptimizationWorkflow",
            {
                "proposal_id": proposal_id,
                "approval_timeout_seconds": approval_timeout_seconds,
            },
            id=workflow_id,
            task_queue=settings.wattson_temporal_task_queue,
            id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
            rpc_timeout=timedelta(seconds=5),
        )
        return workflow_id

    async def query_status(self, workflow_id: str) -> dict[str, Any] | None:
        if self.client is None:
            return None
        try:
            handle = self.client.get_workflow_handle(workflow_id)
            return await asyncio.wait_for(
                handle.query("status", result_type=dict), timeout=2.0
            )
        except Exception:
            return None

    async def approve(self, workflow_id: str, approval_id: str) -> None:
        client = self._require()
        handle = client.get_workflow_handle(workflow_id)
        try:
            await asyncio.wait_for(handle.signal("approve", approval_id), timeout=5.0)
        except Exception as exc:
            raise TemporalUnavailable(f"approval signal failed: {type(exc).__name__}") from exc

    async def reject(self, workflow_id: str, approval_id: str, reason: str) -> None:
        client = self._require()
        handle = client.get_workflow_handle(workflow_id)
        try:
            await asyncio.wait_for(
                handle.signal("reject", {"approval_id": approval_id, "reason": reason}),
                timeout=5.0,
            )
        except Exception as exc:
            raise TemporalUnavailable(f"reject signal failed: {type(exc).__name__}") from exc

    async def cancel(self, workflow_id: str, reason: str) -> None:
        client = self._require()
        handle = client.get_workflow_handle(workflow_id)
        try:
            await asyncio.wait_for(handle.signal("cancel", reason), timeout=5.0)
        except Exception as exc:
            raise TemporalUnavailable(f"cancel signal failed: {type(exc).__name__}") from exc
