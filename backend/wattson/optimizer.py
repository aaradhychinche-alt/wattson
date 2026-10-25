"""Deterministic candidate generation, hard constraints, and weighted scoring."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from .assumptions import Assumptions, load_assumptions
from .db import utcnow
from .simulator_math import CandidateConfig, CapabilityError, estimate

Objective = Literal[
    "balanced", "lowest_cost", "lowest_energy", "lowest_latency", "highest_throughput"
]

OBJECTIVE_WEIGHTS: dict[str, dict[str, float]] = {
    "balanced": {
        "cost_usd": 0.35,
        "energy_kwh": 0.25,
        "latency_ms": 0.25,
        "throughput_samples_s": 0.15,
    },
    "lowest_cost": {
        "cost_usd": 1.0,
        "energy_kwh": 0.0,
        "latency_ms": 0.0,
        "throughput_samples_s": 0.0,
    },
    "lowest_energy": {
        "cost_usd": 0.0,
        "energy_kwh": 1.0,
        "latency_ms": 0.0,
        "throughput_samples_s": 0.0,
    },
    "lowest_latency": {
        "cost_usd": 0.0,
        "energy_kwh": 0.0,
        "latency_ms": 1.0,
        "throughput_samples_s": 0.0,
    },
    "highest_throughput": {
        "cost_usd": 0.0,
        "energy_kwh": 0.0,
        "latency_ms": 0.0,
        "throughput_samples_s": 1.0,
    },
}


class Weights(BaseModel):
    cost_usd: float = Field(ge=0)
    energy_kwh: float = Field(ge=0)
    latency_ms: float = Field(ge=0)
    throughput_samples_s: float = Field(ge=0)

    @model_validator(mode="after")
    def _sum(self) -> Weights:
        if abs(sum(self.model_dump().values()) - 1.0) > 1e-6:
            raise ValueError("weights must sum to 1.0")
        return self


class CandidateOut(BaseModel):
    id: str
    config: CandidateConfig
    estimates: dict[str, float] | None = None
    runtime_hours: float | None = None
    eligible: bool = True
    constraint_failures: list[dict[str, str]] = Field(default_factory=list)
    normalized: dict[str, float] | None = None
    score: float | None = None
    rank: int | None = None
    provenance: Literal["predicted", "simulated"] = "predicted"


class ConstraintInput(BaseModel):
    budget_usd: float | None = Field(default=None, gt=0)
    max_runtime_hours: float | None = Field(default=None, gt=0)
    deadline_at: datetime | None = None
    allowed_gpu_types: list[str] | None = None


class PlanContext(BaseModel):
    provider: Literal["simulator", "jarvislabs"] = "simulator"
    provider_gpu_types: list[str] | None = None
    now: datetime = Field(default_factory=utcnow)


class OptimizationPlan(BaseModel):
    objective: Objective = "balanced"
    weights: Weights
    candidates: list[CandidateOut]
    selected_candidate_id: str | None
    normalization: str
    generated_at: datetime
    provider: str
    dataset_samples: int
    assumptions_version: int
    disclaimer: str


def weights_for(objective: str) -> Weights:
    if objective not in OBJECTIVE_WEIGHTS:
        raise ValueError(f"unknown objective {objective!r}")
    return Weights(**OBJECTIVE_WEIGHTS[objective])


def _candidate_id(config: CandidateConfig) -> str:
    payload = json.dumps(config.as_dict(), sort_keys=True, separators=(",", ":"))
    return "cand-" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:10]


def generate_configs(
    assumptions: Assumptions, provider_gpu_types: list[str] | None = None
) -> list[CandidateConfig]:
    allowed = set(provider_gpu_types) if provider_gpu_types else set(assumptions.gpus)
    gpu_names = sorted(name for name in assumptions.gpus if name in allowed)
    configs: list[CandidateConfig] = []
    for gpu in gpu_names:
        for count in range(1, assumptions.max_gpus_per_candidate + 1):
            for batch in (32, 64):
                for precision in ("fp16", "int8"):
                    configs.append(
                        CandidateConfig(
                            gpu_type=gpu,
                            gpu_count=count,
                            batch_size=batch,
                            precision=precision,
                            checkpointing=True,
                        )
                    )
    return configs[: assumptions.max_candidates]


def _normalize(candidates: list[CandidateOut], weights: Weights) -> None:
    eligible = [c for c in candidates if c.eligible and c.estimates]
    if len(eligible) <= 1:
        for candidate in eligible:
            candidate.normalized = {key: 0.0 for key in weights.model_dump()}
            candidate.score = 0.0
        return
    mins: dict[str, float] = {}
    maxs: dict[str, float] = {}
    for metric in weights.model_dump():
        values = [float(c.estimates[metric]) for c in eligible if c.estimates]
        mins[metric] = min(values)
        maxs[metric] = max(values)

    for candidate in eligible:
        assert candidate.estimates is not None
        norm: dict[str, float] = {}
        for metric in weights.model_dump():
            span = maxs[metric] - mins[metric]
            if span == 0:
                norm[metric] = 0.0
            elif metric == "throughput_samples_s":
                norm[metric] = (maxs[metric] - candidate.estimates[metric]) / span
            else:
                norm[metric] = (candidate.estimates[metric] - mins[metric]) / span
            norm[metric] = round(norm[metric], 8)
        candidate.normalized = norm
        score = sum(getattr(weights, metric) * norm[metric] for metric in norm)
        candidate.score = round(score, 8)

    ranked = sorted(
        eligible,
        key=lambda c: (
            c.score if c.score is not None else float("inf"),
            c.estimates["cost_usd"] if c.estimates else float("inf"),
            c.id,
        ),
    )
    for rank, candidate in enumerate(ranked, start=1):
        candidate.rank = rank


def plan_optimization(
    *,
    dataset_samples: int,
    constraints: ConstraintInput,
    context: PlanContext | None = None,
    objective: str = "balanced",
    assumptions: Assumptions | None = None,
    weights: Weights | None = None,
) -> OptimizationPlan:
    ctx = context or PlanContext()
    assumptions = assumptions or load_assumptions()
    weights = weights or weights_for(objective)
    if constraints.deadline_at is not None and constraints.deadline_at.tzinfo is None:
        constraints = constraints.model_copy(
            update={"deadline_at": constraints.deadline_at.replace(tzinfo=ctx.now.tzinfo)}
        )
    candidates: list[CandidateOut] = []
    for config in generate_configs(assumptions, ctx.provider_gpu_types):
        cid = _candidate_id(config)
        failures: list[dict[str, str]] = []
        if (
            constraints.allowed_gpu_types
            and config.gpu_type not in constraints.allowed_gpu_types
        ):
            failures.append(
                {
                    "code": "gpu_not_allowed",
                    "message": f"{config.gpu_type} is not in allowed_gpu_types",
                }
            )
        if (
            ctx.provider == "jarvislabs"
            and ctx.provider_gpu_types
            and config.gpu_type not in ctx.provider_gpu_types
        ):
            failures.append(
                {
                    "code": "provider_capability_missing",
                    "message": f"provider does not document {config.gpu_type}",
                }
            )
        try:
            est = estimate(config, dataset_samples, assumptions)
        except CapabilityError as exc:
            candidates.append(
                CandidateOut(
                    id=cid,
                    config=config,
                    eligible=False,
                    constraint_failures=failures
                    + [{"code": "estimate_unavailable", "message": str(exc)}],
                )
            )
            continue

        if constraints.budget_usd is not None and est.cost_usd > constraints.budget_usd:
            failures.append(
                {
                    "code": "budget_exceeded",
                    "message": (
                        f"estimated ${est.cost_usd:.2f} exceeds ${constraints.budget_usd:.2f}"
                    ),
                }
            )
        if (
            constraints.max_runtime_hours is not None
            and est.runtime_hours > constraints.max_runtime_hours
        ):
            failures.append(
                {
                    "code": "runtime_exceeded",
                    "message": (
                        f"estimated {est.runtime_hours:.2f}h exceeds "
                        f"{constraints.max_runtime_hours:.2f}h"
                    ),
                }
            )
        if constraints.deadline_at is not None:
            finish = ctx.now + timedelta(hours=est.runtime_hours)
            if finish > constraints.deadline_at:
                failures.append(
                    {
                        "code": "deadline_exceeded",
                        "message": (
                            f"estimated finish {finish.isoformat()} is after "
                            f"{constraints.deadline_at.isoformat()}"
                        ),
                    }
                )
        candidates.append(
            CandidateOut(
                id=cid,
                config=config,
                estimates={
                    "cost_usd": est.cost_usd,
                    "energy_kwh": est.energy_kwh,
                    "latency_ms": est.latency_ms,
                    "throughput_samples_s": est.throughput_samples_s,
                },
                runtime_hours=est.runtime_hours,
                eligible=not failures,
                constraint_failures=failures,
            )
        )

    _normalize(candidates, weights)
    selected = next((c for c in candidates if c.rank == 1), None)
    eligible_count = sum(1 for c in candidates if c.eligible)
    normalization = (
        "skipped_single_candidate"
        if eligible_count <= 1
        else "min_max_across_eligible_candidates"
    )
    return OptimizationPlan(
        objective=objective,  # type: ignore[arg-type]
        weights=weights,
        candidates=candidates,
        selected_candidate_id=selected.id if selected else None,
        normalization=normalization,
        generated_at=ctx.now,
        provider=ctx.provider,
        dataset_samples=dataset_samples,
        assumptions_version=assumptions.version,
        disclaimer=assumptions.disclaimer,
    )
