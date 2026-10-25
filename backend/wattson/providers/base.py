"""Provider abstraction. Adapters perform I/O; workflows never do."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from ..simulator_math import CandidateConfig


class ProviderError(RuntimeError):
    """Base error for provider operations."""


class TransientProviderError(ProviderError):
    """Retryable provider failure (timeout, 429, temporary API error)."""


class PermanentProviderError(ProviderError):
    """Non-retryable provider failure (bad config, capability missing)."""


class ProviderCapabilityError(PermanentProviderError):
    pass


class ApprovalRequired(PermanentProviderError):
    pass


class KillSwitchActive(PermanentProviderError):
    pass


@dataclass(frozen=True)
class ProvisionRequest:
    proposal_id: str
    workflow_id: str
    idempotency_key: str
    config: CandidateConfig
    dataset_samples: int
    runtime_hours: float
    execution_profile: str = "nominal"
    inject_transient_launch: bool = False
    inject_transient_collect: bool = False
    tags: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ProvisionedInstance:
    instance_id: str
    provider: str
    status: str
    idempotency_key: str
    hourly_usd: float | None
    created_at: datetime
    detail: str = ""
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CollectedMetrics:
    cost_usd: float
    energy_kwh: float
    latency_ms: float
    throughput_samples_s: float
    runtime_hours: float
    source: str
    provenance: str
    sample_count: int = 1
    energy_source: str = "simulator"


class ProviderAdapter(ABC):
    name: str
    provenance: str

    @abstractmethod
    def status(self) -> dict[str, Any]:
        """Return integration status without making a paid launch."""

    @abstractmethod
    def supports(self, gpu_type: str) -> bool: ...

    @abstractmethod
    def provision(self, request: ProvisionRequest) -> ProvisionedInstance:
        """Launch or reconcile an instance. Must be idempotent by idempotency_key."""

    @abstractmethod
    def collect(self, instance: ProvisionedInstance, request: ProvisionRequest) -> CollectedMetrics:
        """Collect run results. Must not fabricate real-provider measurements."""

    @abstractmethod
    def cleanup(self, instance: ProvisionedInstance) -> bool:
        """Idempotently stop only WATTSON-owned resources."""
