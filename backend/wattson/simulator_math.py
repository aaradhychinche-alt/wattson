"""Deterministic cost / energy / latency math used by planner and simulator."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field

from .assumptions import Assumptions


class CapabilityError(ValueError):
    """Raised when an assumption or configuration cannot be evaluated."""


class CandidateConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    gpu_type: str = Field(min_length=1, max_length=40)
    gpu_count: int = Field(ge=1, le=8)
    batch_size: int = Field(ge=1, le=4096)
    precision: str = Field(pattern="^(fp16|bf16|int8)$")
    checkpointing: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "gpu_type": self.gpu_type,
            "gpu_count": self.gpu_count,
            "batch_size": self.batch_size,
            "precision": self.precision,
            "checkpointing": self.checkpointing,
        }


@dataclass(frozen=True)
class Estimate:
    cost_usd: float
    energy_kwh: float
    latency_ms: float
    throughput_samples_s: float
    runtime_hours: float


def deterministic_unit(*parts: object) -> float:
    digest = hashlib.sha256("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()
    return int(digest[:12], 16) / float(16**12)


def _check(config: CandidateConfig, assumptions: Assumptions) -> None:
    gpu = assumptions.gpus.get(config.gpu_type)
    if gpu is None:
        raise CapabilityError(f"GPU type {config.gpu_type!r} is not in the simulator catalog")
    if config.gpu_count < 1:
        raise CapabilityError("gpu_count must be at least 1")
    if config.precision not in assumptions.precision_speed:
        raise CapabilityError(f"precision {config.precision!r} is not supported")
    if str(config.batch_size) not in assumptions.batch_efficiency:
        raise CapabilityError(f"batch_size {config.batch_size} has no efficiency assumption")
    if gpu.base_samples_per_second <= 0:
        raise CapabilityError("base throughput must be positive")


def estimate(
    config: CandidateConfig,
    dataset_samples: int,
    assumptions: Assumptions,
    *,
    profile: str = "nominal",
    jitter_key: str | None = None,
) -> Estimate:
    """Estimate one candidate.

    Planning uses the nominal profile. Execution can use a labelled profile with
    measured-looking multipliers, plus deterministic jitter. All values remain
    simulated.
    """
    _check(config, assumptions)
    if dataset_samples <= 0:
        raise CapabilityError("dataset_samples must be positive")
    gpu = assumptions.gpus[config.gpu_type]
    speed = (
        gpu.base_samples_per_second
        * config.gpu_count
        * assumptions.precision_speed[config.precision]
        * assumptions.batch_efficiency[str(config.batch_size)]
        * assumptions.checkpoint_throughput_factor[str(config.checkpointing).lower()]
    )
    if speed <= 0:
        raise CapabilityError("derived throughput must be positive")

    prof = assumptions.profiles.get(profile)
    if prof is None:
        raise CapabilityError(f"unknown execution profile {profile!r}")

    jitter = 0.0
    if jitter_key:
        jitter = (deterministic_unit(jitter_key) * 2.0 - 1.0) * assumptions.jitter_fraction

    effective_throughput = speed * prof.throughput_multiplier * (1.0 + jitter)
    processing_seconds = dataset_samples / effective_throughput
    runtime_hours = (processing_seconds + assumptions.cold_start_seconds) / 3600.0
    cost = (
        gpu.hourly_usd * config.gpu_count * runtime_hours
        + assumptions.storage_gb
        * assumptions.storage_usd_per_gb_hour
        * runtime_hours
    ) * prof.cost_multiplier
    energy_kwh = (
        gpu.tdp_watts
        * config.gpu_count
        * runtime_hours
        * assumptions.utilization
        * assumptions.pue
        / 1000.0
    )
    latency_ms = 1000.0 / effective_throughput * prof.latency_multiplier
    return Estimate(
        cost_usd=round(max(cost, 0.0), 6),
        energy_kwh=round(max(energy_kwh, 0.0), 6),
        latency_ms=round(max(latency_ms, 0.0), 6),
        throughput_samples_s=round(max(effective_throughput, 0.0), 6),
        runtime_hours=round(runtime_hours, 6),
    )
