"""SQLAlchemy 2 models. Every measurement carries provenance."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from .db import utcnow

PROVENANCE_VALUES = ("measured", "calculated", "estimated", "predicted", "simulated")
RUN_KINDS = ("baseline", "optimization")
INTEGRATION_STATUSES = ("connected", "disconnected", "simulated", "error")
VERDICTS = ("improved", "regressed", "mixed", "inconclusive")


def new_id() -> str:
    return uuid.uuid4().hex


class Base(DeclarativeBase):
    type_annotation_map = {dict[str, Any]: JSON, list[Any]: JSON}


class Workload(Base):
    __tablename__ = "workloads"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    workload_type: Mapped[str] = mapped_column(String(40), nullable=False, default="fine_tune")
    provider: Mapped[str] = mapped_column(String(40), nullable=False, default="simulator")
    current_config: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    constraints: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    meta: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    runs: Mapped[list[Run]] = relationship(
        back_populates="workload", cascade="all, delete-orphan", passive_deletes=True
    )
    proposals: Mapped[list[OptimizationProposal]] = relationship(
        back_populates="workload", cascade="all, delete-orphan", passive_deletes=True
    )

    __table_args__ = (
        CheckConstraint(
            "provider in ('simulator','jarvislabs')", name="ck_workload_provider"
        ),
        Index("ix_workloads_created_at", "created_at"),
    )


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    workload_id: Mapped[str] = mapped_column(
        ForeignKey("workloads.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(20), nullable=False, default="optimization")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="running")
    config: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    provider: Mapped[str] = mapped_column(String(40), nullable=False, default="simulator")
    provider_instance_id: Mapped[str | None] = mapped_column(String(200))
    idempotency_key: Mapped[str | None] = mapped_column(String(200), unique=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    workload: Mapped[Workload] = relationship(back_populates="runs")
    measurements: Mapped[list[Measurement]] = relationship(
        back_populates="run", cascade="all, delete-orphan", passive_deletes=True
    )

    __table_args__ = (
        CheckConstraint("kind in ('baseline','optimization')", name="ck_run_kind"),
        Index("ix_runs_workload_started", "workload_id", "started_at"),
    )


class Measurement(Base):
    __tablename__ = "measurements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("runs.id", ondelete="CASCADE"), nullable=False
    )
    metric: Mapped[str] = mapped_column(String(60), nullable=False)
    value: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit: Mapped[str] = mapped_column(String(30), nullable=False)
    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    source: Mapped[str] = mapped_column(String(200), nullable=False)
    provenance: Mapped[str] = mapped_column(String(20), nullable=False)
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")

    run: Mapped[Run] = relationship(back_populates="measurements")

    __table_args__ = (
        UniqueConstraint("run_id", "metric", name="uq_measurement_run_metric"),
        CheckConstraint(
            "provenance in ('measured','calculated','estimated','predicted','simulated')",
            name="ck_measurement_provenance",
        ),
        CheckConstraint("value is null or value >= 0", name="ck_measurement_non_negative"),
        Index("ix_measurements_metric", "metric"),
    )

    @property
    def available(self) -> bool:
        return self.value is not None


class OptimizationProposal(Base):
    __tablename__ = "optimization_proposals"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    workload_id: Mapped[str] = mapped_column(
        ForeignKey("workloads.id", ondelete="CASCADE"), nullable=False
    )
    baseline_run_id: Mapped[str | None] = mapped_column(
        ForeignKey("runs.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="proposed")
    objective: Mapped[str] = mapped_column(String(40), nullable=False, default="balanced")
    weights: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    config_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    constraints_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    candidates: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    selected_candidate_id: Mapped[str | None] = mapped_column(String(80))
    analysis: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    normalization: Mapped[str] = mapped_column(String(60), nullable=False, default="")
    workflow_id: Mapped[str | None] = mapped_column(String(200), unique=True)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    workload: Mapped[Workload] = relationship(back_populates="proposals")
    approval: Mapped[Approval | None] = relationship(
        back_populates="proposal", uselist=False, cascade="all, delete-orphan"
    )
    report: Mapped[Report | None] = relationship(
        back_populates="proposal", uselist=False, cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint(
            "status in ('proposed','awaiting_approval','approved','rejected','executing',"
            "'completed','failed','cancelled','needs_intervention')",
            name="ck_proposal_status",
        ),
        Index("ix_proposals_workload_created", "workload_id", "created_at"),
    )


class Approval(Base):
    __tablename__ = "approvals"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    proposal_id: Mapped[str] = mapped_column(
        ForeignKey("optimization_proposals.id", ondelete="CASCADE"), nullable=False
    )
    decision: Mapped[str] = mapped_column(String(20), nullable=False)
    actor: Mapped[str] = mapped_column(String(120), nullable=False, default="api-token")
    reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    workflow_id: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    proposal: Mapped[OptimizationProposal] = relationship(back_populates="approval")

    __table_args__ = (
        UniqueConstraint("proposal_id", name="uq_approval_proposal"),
        CheckConstraint("decision in ('approved','rejected')", name="ck_approval_decision"),
    )


class WorkflowRef(Base):
    __tablename__ = "workflow_refs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workflow_id: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    proposal_id: Mapped[str] = mapped_column(
        ForeignKey("optimization_proposals.id", ondelete="CASCADE"), nullable=False
    )
    run_id: Mapped[str | None] = mapped_column(ForeignKey("runs.id", ondelete="SET NULL"))
    stage: Mapped[str] = mapped_column(String(60), nullable=False, default="created")
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="running")
    retries: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text)
    meta: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    __table_args__ = (Index("ix_workflow_refs_proposal", "proposal_id"),)


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    proposal_id: Mapped[str] = mapped_column(
        ForeignKey("optimization_proposals.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    baseline_run_id: Mapped[str] = mapped_column(
        ForeignKey("runs.id", ondelete="CASCADE"), nullable=False
    )
    result_run_id: Mapped[str] = mapped_column(
        ForeignKey("runs.id", ondelete="CASCADE"), nullable=False
    )
    verdict: Mapped[str] = mapped_column(String(20), nullable=False)
    overall_change_pct: Mapped[float | None] = mapped_column(Float)
    summary: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    narrative: Mapped[str] = mapped_column(Text, nullable=False, default="")
    narrative_source: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    uncertainty: Mapped[str] = mapped_column(Text, nullable=False, default="")
    completeness: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    measurement_window: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    proposal: Mapped[OptimizationProposal] = relationship(back_populates="report")

    __table_args__ = (
        CheckConstraint(
            "verdict in ('improved','regressed','mixed','inconclusive')", name="ck_report_verdict"
        ),
        Index("ix_reports_created_at", "created_at"),
    )


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_key: Mapped[str] = mapped_column(String(250), nullable=False, unique=True)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    actor: Mapped[str] = mapped_column(String(120), nullable=False, default="system")
    proposal_id: Mapped[str | None] = mapped_column(String(32))
    workflow_id: Mapped[str | None] = mapped_column(String(200))
    message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        Index("ix_audit_created_at", "created_at"),
        Index("ix_audit_proposal", "proposal_id"),
        Index("ix_audit_type", "event_type"),
    )


class IntegrationHealth(Base):
    __tablename__ = "integration_health"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    integration: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="disconnected")
    detail: Mapped[str] = mapped_column(Text, nullable=False, default="")
    provenance: Mapped[str] = mapped_column(String(20), nullable=False, default="measured")
    meta: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, nullable=False, default=dict)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        CheckConstraint(
            "status in ('connected','disconnected','simulated','error')",
            name="ck_integration_status",
        ),
        CheckConstraint(
            "provenance in ('measured','calculated','estimated','predicted','simulated')",
            name="ck_integration_provenance",
        ),
    )
