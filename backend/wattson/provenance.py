"""Metric/provenance primitives shared by API, simulator, and reports."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from .db import utcnow


class Provenance(StrEnum):
    MEASURED = "measured"
    CALCULATED = "calculated"
    ESTIMATED = "estimated"
    PREDICTED = "predicted"
    SIMULATED = "simulated"


PROVENANCE_LABELS: dict[str, str] = {
    "measured": "Measured",
    "calculated": "Calculated",
    "estimated": "Estimated",
    "predicted": "Predicted",
    "simulated": "Simulated",
}

METRIC_UNITS: dict[str, str] = {
    "cost_usd": "USD",
    "energy_kwh": "kWh",
    "latency_ms": "ms",
    "throughput_samples_s": "samples/s",
    "runtime_hours": "h",
}

LOWER_IS_BETTER = {"cost_usd", "energy_kwh", "latency_ms", "runtime_hours"}


class MetricOut(BaseModel):
    metric: str
    value: float | None
    unit: str
    measured_at: datetime
    source: str
    provenance: Provenance
    sample_count: int = 1
    notes: str = ""
    label: str = "Unavailable"

    @classmethod
    def unavailable(
        cls, metric: str, unit: str, source: str, provenance: Provenance
    ) -> MetricOut:
        return cls(
            metric=metric,
            value=None,
            unit=unit,
            measured_at=utcnow(),
            source=source,
            provenance=provenance,
            label="Unavailable",
        )


def metric_label(value: float | None, provenance: str | Provenance) -> str:
    if value is None:
        return "Unavailable"
    label = PROVENANCE_LABELS[Provenance(provenance).value]
    return label


def safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def pct_change(baseline: float | None, result: float | None, lower_is_better: bool) -> float | None:
    """Positive means improvement, negative means regression. None if unavailable."""
    if baseline is None or result is None or baseline == 0:
        return None
    raw = (result - baseline) / abs(baseline) * 100.0
    return round(-raw if lower_is_better else raw, 3)


class MeasurementIn(BaseModel):
    metric: str = Field(min_length=1, max_length=60)
    value: float | None = Field(default=None, ge=0)
    unit: str = Field(min_length=1, max_length=30)
    measured_at: datetime = Field(default_factory=utcnow)
    source: str = Field(min_length=1, max_length=200)
    provenance: Provenance
    sample_count: int = Field(default=1, ge=1)
    notes: str = ""
