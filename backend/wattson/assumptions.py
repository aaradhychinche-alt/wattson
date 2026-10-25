"""Simulator assumptions loader with mandatory provenance tags."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from .config import get_settings


class AssumptionError(ValueError):
    pass


@dataclass(frozen=True)
class AssumptionValue:
    value: float
    basis: str
    source: str | None = None
    note: str | None = None

    @property
    def provenance(self) -> str:
        return "simulated"


@dataclass(frozen=True)
class GPUAssumption:
    name: str
    hourly_usd: float
    tdp_watts: float
    memory_gb: float
    base_samples_per_second: float


@dataclass(frozen=True)
class Profile:
    name: str
    throughput_multiplier: float
    latency_multiplier: float
    cost_multiplier: float


@dataclass(frozen=True)
class Assumptions:
    version: int
    currency: str
    disclaimer: str
    gpus: dict[str, GPUAssumption]
    utilization: float
    pue: float
    storage_gb: float
    storage_usd_per_gb_hour: float
    cold_start_seconds: float
    max_candidates: int
    max_gpus_per_candidate: int
    jitter_fraction: float
    default_dataset_samples: int
    default_budget_usd: float
    default_max_runtime_hours: float
    default_deadline_hours: float
    precision_speed: dict[str, float]
    checkpoint_throughput_factor: dict[str, float]
    batch_efficiency: dict[str, float]
    profiles: dict[str, Profile]
    transient_launch_probability: float
    transient_collect_probability: float


def _tagged(node: Any, path: str) -> AssumptionValue:
    if not isinstance(node, dict) or "value" not in node or "basis" not in node:
        raise AssumptionError(f"{path}: expected {{value, basis}} tagged value, got {node!r}")
    basis = str(node["basis"])
    if basis not in {"illustrative", "cited"}:
        raise AssumptionError(f"{path}: basis must be illustrative or cited")
    if basis == "cited" and not node.get("source"):
        raise AssumptionError(f"{path}: cited value requires a source")
    if not isinstance(node["value"], (int, float)):
        raise AssumptionError(f"{path}: value must be numeric")
    return AssumptionValue(
        value=float(node["value"]),
        basis=basis,
        source=node.get("source"),
        note=node.get("note"),
    )


def _number(node: Any, path: str) -> float:
    return _tagged(node, path).value


def _mapping(node: Any, path: str) -> dict[str, Any]:
    base = path.rsplit(".", 1)[-1]
    if isinstance(node, dict) and base in node:
        node = node[base]
    if not isinstance(node, dict):
        raise AssumptionError(f"{path}: expected mapping")
    return node


@lru_cache
def load_assumptions(path: str | None = None) -> Assumptions:
    file_path = Path(path or get_settings().wattson_assumptions_path)
    raw = yaml.safe_load(file_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise AssumptionError("assumptions file must be a mapping")

    gpus: dict[str, GPUAssumption] = {}
    for name, node in _mapping(raw, "gpus").items():
        if not isinstance(node, dict):
            raise AssumptionError(f"gpus.{name}: expected mapping")
        gpus[name] = GPUAssumption(
            name=name,
            hourly_usd=_number(node.get("hourly_usd"), f"gpus.{name}.hourly_usd"),
            tdp_watts=_number(node.get("tdp_watts"), f"gpus.{name}.tdp_watts"),
            memory_gb=_number(node.get("memory_gb"), f"gpus.{name}.memory_gb"),
            base_samples_per_second=_number(
                node.get("base_samples_per_second"), f"gpus.{name}.base_samples_per_second"
            ),
        )

    sim = _mapping(raw, "simulation")
    profiles: dict[str, Profile] = {}
    for name, node in _mapping(raw, "profiles").items():
        profiles[name] = Profile(
            name=name,
            throughput_multiplier=_number(
                node.get("throughput_multiplier"), f"profiles.{name}.throughput_multiplier"
            ),
            latency_multiplier=_number(
                node.get("latency_multiplier"), f"profiles.{name}.latency_multiplier"
            ),
            cost_multiplier=_number(
                node.get("cost_multiplier"), f"profiles.{name}.cost_multiplier"
            ),
        )

    def flat(group: str) -> dict[str, float]:
        return {
            str(key): _number(node, f"{group}.{key}")
            for key, node in _mapping(raw, group).items()
        }

    failures = _mapping(raw, "failure_rates")
    return Assumptions(
        version=int(raw.get("version", 0)),
        currency=str(raw.get("currency", "USD")),
        disclaimer=str(raw.get("disclaimer", "")),
        gpus=gpus,
        utilization=_number(sim.get("utilization"), "simulation.utilization"),
        pue=_number(sim.get("pue"), "simulation.pue"),
        storage_gb=_number(sim.get("storage_gb"), "simulation.storage_gb"),
        storage_usd_per_gb_hour=_number(
            sim.get("storage_usd_per_gb_hour"), "simulation.storage_usd_per_gb_hour"
        ),
        cold_start_seconds=_number(
            sim.get("cold_start_seconds"), "simulation.cold_start_seconds"
        ),
        max_candidates=int(_number(sim.get("max_candidates"), "simulation.max_candidates")),
        max_gpus_per_candidate=int(
            _number(sim.get("max_gpus_per_candidate"), "simulation.max_gpus_per_candidate")
        ),
        jitter_fraction=_number(sim.get("jitter_fraction"), "simulation.jitter_fraction"),
        default_dataset_samples=int(
            _number(sim.get("default_dataset_samples"), "simulation.default_dataset_samples")
        ),
        default_budget_usd=_number(
            sim.get("default_budget_usd"), "simulation.default_budget_usd"
        ),
        default_max_runtime_hours=_number(
            sim.get("default_max_runtime_hours"), "simulation.default_max_runtime_hours"
        ),
        default_deadline_hours=_number(
            sim.get("default_deadline_hours"), "simulation.default_deadline_hours"
        ),
        precision_speed=flat("precision_speed"),
        checkpoint_throughput_factor=flat("checkpoint_throughput_factor"),
        batch_efficiency=flat("batch_efficiency"),
        profiles=profiles,
        transient_launch_probability=_number(
            failures.get("transient_launch_probability"),
            "failure_rates.transient_launch_probability",
        ),
        transient_collect_probability=_number(
            failures.get("transient_collect_probability"),
            "failure_rates.transient_collect_probability",
        ),
    )
