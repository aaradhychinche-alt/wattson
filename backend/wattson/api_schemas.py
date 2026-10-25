"""Pydantic v2 API schemas (request/response contracts)."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    PlainSerializer,
)

from .db import as_utc
from .provenance import Provenance
from .simulator_math import CandidateConfig


def _utc(value: datetime | None) -> datetime | None:
    return as_utc(value)


UTCDateTime = Annotated[
    datetime,
    AfterValidator(_utc),
    PlainSerializer(lambda value: value.isoformat() if value else None, return_type=str),
]

ObjectiveName = Literal[
    "balanced", "lowest_cost", "lowest_energy", "lowest_latency", "highest_throughput"
]


class APIModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Page[T](BaseModel):
    items: list[T]
    total: int
    limit: int
    offset: int


class WorkloadCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    description: str = Field(default="", max_length=4000)
    workload_type: Literal["fine_tune", "inference_batch"] = "fine_tune"
    provider: Literal["simulator", "jarvislabs"] = "simulator"
    current_config: CandidateConfig
    constraints: dict[str, Any] = Field(default_factory=dict)
    meta: dict[str, Any] = Field(default_factory=dict)

    def limited_meta(self) -> dict[str, Any]:
        import json

        encoded = json.dumps(self.meta, default=str)
        if len(encoded) > 200_000:
            raise ValueError("meta exceeds 200 KB limit")
        return self.meta


class WorkloadOut(APIModel):
    id: str
    name: str
    description: str
    workload_type: str
    provider: str
    current_config: dict[str, Any]
    constraints: dict[str, Any]
    meta: dict[str, Any]
    created_at: UTCDateTime
    updated_at: UTCDateTime


class MeasurementOut(APIModel):
    metric: str
    value: float | None
    unit: str
    measured_at: UTCDateTime
    source: str
    provenance: Provenance
    sample_count: int
    notes: str
    label: str = ""

    @classmethod
    def from_row(cls, row: Any) -> MeasurementOut:
        from .provenance import metric_label

        return cls(
            metric=row.metric,
            value=row.value,
            unit=row.unit,
            measured_at=row.measured_at,
            source=row.source,
            provenance=row.provenance,
            sample_count=row.sample_count,
            notes=row.notes,
            label=metric_label(row.value, row.provenance),
        )


class RunOut(APIModel):
    id: str
    workload_id: str
    kind: str
    status: str
    config: dict[str, Any]
    provider: str
    provider_instance_id: str | None = None
    started_at: UTCDateTime
    completed_at: UTCDateTime | None = None
    notes: str
    measurements: list[MeasurementOut] = Field(default_factory=list)


class WorkloadDetail(WorkloadOut):
    runs: list[RunOut] = Field(default_factory=list)


class ProposalCreate(BaseModel):
    workload_id: str = Field(min_length=1, max_length=32)
    objective: ObjectiveName = "balanced"


class ApprovalRequest(BaseModel):
    reason: str = Field(default="", max_length=1000)


class RejectRequest(BaseModel):
    reason: str = Field(default="", max_length=1000)


class ApprovalOut(APIModel):
    id: str
    proposal_id: str
    decision: str
    actor: str
    reason: str
    workflow_id: str | None = None
    created_at: UTCDateTime


class ProposalOut(APIModel):
    id: str
    workload_id: str
    baseline_run_id: str | None
    status: str
    objective: str
    weights: dict[str, Any]
    config_snapshot: dict[str, Any]
    constraints_snapshot: dict[str, Any]
    candidates: list[dict[str, Any]]
    selected_candidate_id: str | None
    analysis: dict[str, Any]
    normalization: str
    workflow_id: str | None
    error: str | None
    created_at: UTCDateTime
    updated_at: UTCDateTime
    approval: ApprovalOut | None = None
    report_id: str | None = None
    verdict: str | None = None


class WorkflowStart(BaseModel):
    proposal_id: str = Field(min_length=1, max_length=32)


class WorkflowOut(APIModel):
    workflow_id: str
    proposal_id: str
    run_id: str | None = None
    stage: str
    status: str
    retries: int
    last_error: str | None = None
    meta: dict[str, Any] = Field(default_factory=dict)
    created_at: UTCDateTime
    updated_at: UTCDateTime
    live_stage: str | None = None
    verdict: str | None = None
    report_id: str | None = None


class CancelRequest(BaseModel):
    reason: str = Field(default="cancelled via API", max_length=500)


class ReportOut(APIModel):
    id: str
    proposal_id: str
    baseline_run_id: str
    result_run_id: str
    verdict: str
    overall_change_pct: float | None
    summary: dict[str, Any]
    narrative: str
    narrative_source: str
    uncertainty: str
    completeness: dict[str, Any]
    measurement_window: dict[str, Any]
    created_at: UTCDateTime


class AuditOut(APIModel):
    id: int
    event_key: str
    event_type: str
    actor: str
    proposal_id: str | None
    workflow_id: str | None
    message: str
    payload: dict[str, Any]
    created_at: UTCDateTime


class IntegrationOut(APIModel):
    integration: str
    status: str
    detail: str
    provenance: str
    meta: dict[str, Any] = Field(default_factory=dict)
    checked_at: UTCDateTime


class HealthComponent(BaseModel):
    name: str
    status: Literal["connected", "disconnected", "simulated", "error"]
    detail: str
    provenance: str = "measured"


class HealthOut(BaseModel):
    status: Literal["ok", "degraded"]
    version: str
    timestamp: datetime
    checks: list[HealthComponent]


class SettingsOut(BaseModel):
    kill_switch_active: bool
    kill_switch_source: str
    kill_switch_env: bool
    provider: str
    ai_provider: str
    gemma_model: str
    ai_configured: bool
    temporal_host: str
    temporal_namespace: str
    task_queue: str
    database_driver: str
    api_token_configured: bool


class SettingsUpdate(BaseModel):
    kill_switch: bool


class ErrorBody(BaseModel):
    code: str
    message: str
    details: Any | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody


class MessageOut(BaseModel):
    ok: bool = True
    message: str = ""
