"""Deterministic local simulator. It never contacts a cloud or spends money."""

from __future__ import annotations

import threading
from datetime import UTC, datetime
from typing import Any

from ..assumptions import load_assumptions
from ..simulator_math import estimate
from .base import (
    CollectedMetrics,
    ProviderAdapter,
    ProvisionedInstance,
    ProvisionRequest,
    TransientProviderError,
)


class SimulatorProvider(ProviderAdapter):
    name = "simulator"
    provenance = "simulated"

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._instances: dict[str, ProvisionedInstance] = {}
        self._failed_launch_once: set[str] = set()
        self._failed_collect_once: set[str] = set()
        self._assumptions = load_assumptions()

    def status(self) -> dict[str, Any]:
        return {
            "integration": "provider",
            "status": "simulated",
            "detail": "Local deterministic simulator. No cloud credentials, no paid resources.",
            "provenance": "simulated",
            "provider": self.name,
        }

    def supports(self, gpu_type: str) -> bool:
        return gpu_type in self._assumptions.gpus

    def find_by_key(self, idempotency_key: str) -> ProvisionedInstance | None:
        with self._lock:
            return self._instances.get(idempotency_key)

    def provision(self, request: ProvisionRequest) -> ProvisionedInstance:
        with self._lock:
            existing = self._instances.get(request.idempotency_key)
            if existing is not None:
                return existing
            config = request.config
            gpu = self._assumptions.gpus.get(config.gpu_type)
            if gpu is None:
                from .base import ProviderCapabilityError

                raise ProviderCapabilityError(
                    f"simulator does not have assumptions for {config.gpu_type}"
                )
            instance = ProvisionedInstance(
                instance_id="sim-" + request.idempotency_key[-16:],
                provider=self.name,
                status="running",
                idempotency_key=request.idempotency_key,
                hourly_usd=gpu.hourly_usd,
                created_at=datetime.now(UTC),
                detail="Simulated instance (provenance: simulated)",
                meta={
                    "tags": {"wattson:managed": "true", **request.tags},
                    "gpu_type": config.gpu_type,
                    "gpu_count": config.gpu_count,
                },
            )
            self._instances[request.idempotency_key] = instance
            if (
                request.inject_transient_launch
                and request.idempotency_key not in self._failed_launch_once
            ):
                self._failed_launch_once.add(request.idempotency_key)
                # Deliberately fail AFTER recording the instance: the retry must
                # reconcile by key and must not launch a second instance.
                raise TransientProviderError(
                    "simulated transient API timeout after instance creation"
                )
            return instance

    def collect(self, instance: ProvisionedInstance, request: ProvisionRequest) -> CollectedMetrics:
        with self._lock:
            if (
                request.inject_transient_collect
                and request.idempotency_key not in self._failed_collect_once
            ):
                self._failed_collect_once.add(request.idempotency_key)
                raise TransientProviderError("simulated transient metrics endpoint timeout")
        profile = request.execution_profile or "nominal"
        result = estimate(
            request.config,
            request.dataset_samples,
            self._assumptions,
            profile=profile,
            jitter_key=request.workflow_id + ":result",
        )
        return CollectedMetrics(
            cost_usd=result.cost_usd,
            energy_kwh=result.energy_kwh,
            latency_ms=result.latency_ms,
            throughput_samples_s=result.throughput_samples_s,
            runtime_hours=result.runtime_hours,
            source="wattson-simulator/v1 (illustrative assumptions)",
            provenance="simulated",
            sample_count=1,
            energy_source="simulator",
        )

    def cleanup(self, instance: ProvisionedInstance) -> bool:
        with self._lock:
            current = self._instances.get(instance.idempotency_key)
            if current is None:
                return True
            if current.meta.get("tags", {}).get("wattson:managed") != "true":
                raise ValueError("refusing to clean a resource not tagged wattson:managed=true")
            self._instances[instance.idempotency_key] = ProvisionedInstance(
                instance_id=current.instance_id,
                provider=current.provider,
                status="stopped",
                idempotency_key=current.idempotency_key,
                hourly_usd=current.hourly_usd,
                created_at=current.created_at,
                detail="stopped (idempotent cleanup)",
                meta=current.meta,
            )
            return True
