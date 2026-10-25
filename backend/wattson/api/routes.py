"""HTTP API routes."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import __version__
from ..api_schemas import (
    ApprovalOut,
    ApprovalRequest,
    AuditOut,
    CancelRequest,
    ErrorResponse,
    HealthComponent,
    HealthOut,
    IntegrationOut,
    MessageOut,
    Page,
    ProposalCreate,
    ProposalOut,
    RejectRequest,
    ReportOut,
    RunOut,
    SettingsOut,
    SettingsUpdate,
    WorkflowOut,
    WorkflowStart,
    WorkloadCreate,
    WorkloadDetail,
    WorkloadOut,
)
from ..assumptions import load_assumptions
from ..config import get_settings
from ..db import utcnow
from ..models import (
    Approval,
    OptimizationProposal,
    Report,
    Run,
    WorkflowRef,
    Workload,
)
from ..optimizer import ConstraintInput
from ..services.audit import list_audit, record_audit
from ..services.demo_seed import SCENARIOS, seed_demo_workloads
from ..services.integrations import collect_integration_statuses
from ..services.kill_switch import effective_kill_switch, set_kill_switch
from ..services.proposals import DomainError, create_proposal
from ..simulator_math import CandidateConfig, CapabilityError, estimate
from ..temporal_client import TemporalUnavailable
from .deps import APIError, gateway, get_db, require_token
from .routes_helpers import (
    proposal_out,
    run_out,
    workflow_out,
)

router = APIRouter()
auth = Depends(require_token)
db_dep = Depends(get_db)

DbSession = Annotated[Session, db_dep]


def _page(items: list[Any], total: int, limit: int, offset: int) -> dict[str, Any]:
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/api/health", response_model=HealthOut, tags=["health"])
async def health(request: Request, session: DbSession) -> HealthOut:
    temporal_ok = await gateway(request).health()
    checks = collect_integration_statuses(session, temporal_ok=temporal_ok)
    components = [
        HealthComponent(
            name=check["integration"],
            status=check["status"],
            detail=check["detail"],
            provenance=check["provenance"],
        )
        for check in checks
    ]
    db_ok = next((c for c in components if c.name == "database"), None)
    provider = next((c for c in components if c.name == "provider"), None)
    overall: Literal["ok", "degraded"] = (
        "ok"
        if db_ok
        and db_ok.status == "connected"
        and temporal_ok
        and provider
        and provider.status in {"connected", "simulated"}
        else "degraded"
    )
    return HealthOut(
        status=overall,
        version=__version__,
        timestamp=datetime.now(UTC),
        checks=components,
    )


@router.get("/api/integrations", response_model=list[IntegrationOut], tags=["integrations"])
async def integrations(request: Request, session: DbSession, _: str = auth) -> list[IntegrationOut]:
    temporal_ok = await gateway(request).health()
    rows = collect_integration_statuses(session, temporal_ok=temporal_ok)
    return [IntegrationOut(**row) for row in rows]


@router.get("/api/workloads", response_model=Page[WorkloadOut], tags=["workloads"])
def list_workloads(
    session: DbSession,
    _: str = auth,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> Page[WorkloadOut]:
    total = session.scalar(select(func.count(Workload.id))) or 0
    rows = session.scalars(
        select(Workload).order_by(Workload.created_at.desc()).limit(limit).offset(offset)
    )
    return Page[WorkloadOut](
        items=[WorkloadOut.model_validate(row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/api/workloads",
    response_model=WorkloadOut,
    status_code=status.HTTP_201_CREATED,
    tags=["workloads"],
    responses={409: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def create_workload(
    body: WorkloadCreate, session: DbSession, _: str = auth
) -> WorkloadOut:
    assumptions = load_assumptions()
    try:
        candidate = CandidateConfig.model_validate(body.current_config.as_dict())
        estimate(candidate, 1, assumptions)
    except (CapabilityError, ValueError) as exc:
        raise APIError(422, "invalid_config", f"workload config is invalid: {exc}") from exc
    try:
        constraints = ConstraintInput.model_validate(body.constraints or {})
    except Exception as exc:
        raise APIError(422, "invalid_constraints", f"invalid constraints: {exc}") from exc
    if constraints.deadline_at is not None and constraints.deadline_at <= utcnow():
        raise APIError(422, "invalid_constraints", "deadline_at must be in the future")
    meta = body.limited_meta()
    workload = Workload(
        name=body.name.strip(),
        description=body.description,
        workload_type=body.workload_type,
        provider=body.provider,
        current_config=candidate.as_dict(),
        constraints=constraints.model_dump(mode="json"),
        meta=meta,
    )
    session.add(workload)
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise APIError(409, "name_conflict", "A workload with that name already exists.") from exc
    record_audit(
        session,
        event_key=f"workload.created:{workload.id}",
        event_type="workload.created",
        message=f"Workload {workload.name} registered",
        proposal_id=None,
        payload={"workload_id": workload.id, "provider": workload.provider},
    )
    session.commit()
    session.refresh(workload)
    return WorkloadOut.model_validate(workload)


@router.get("/api/workloads/{workload_id}", response_model=WorkloadDetail, tags=["workloads"])
def get_workload(workload_id: str, session: DbSession, _: str = auth) -> WorkloadDetail:
    workload = session.get(Workload, workload_id)
    if workload is None:
        raise APIError(404, "not_found", "Workload not found.")
    runs = session.scalars(
        select(Run).where(Run.workload_id == workload.id).order_by(Run.created_at.desc())
    ).all()
    data = WorkloadOut.model_validate(workload).model_dump()
    return WorkloadDetail(**data, runs=[run_out(run) for run in runs])


@router.get(
    "/api/workloads/{workload_id}/runs", response_model=Page[RunOut], tags=["workloads"]
)
def list_runs(
    workload_id: str,
    session: DbSession,
    _: str = auth,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> Page[RunOut]:
    if session.get(Workload, workload_id) is None:
        raise APIError(404, "not_found", "Workload not found.")
    total = (
        session.scalar(select(func.count(Run.id)).where(Run.workload_id == workload_id)) or 0
    )
    rows = session.scalars(
        select(Run)
        .where(Run.workload_id == workload_id)
        .order_by(Run.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return Page[RunOut](
        items=[run_out(row) for row in rows], total=total, limit=limit, offset=offset
    )


@router.post(
    "/api/optimizations",
    response_model=ProposalOut,
    status_code=status.HTTP_201_CREATED,
    tags=["optimizations"],
    responses={422: {"model": ErrorResponse}},
)
def create_optimization(
    body: ProposalCreate, session: DbSession, _: str = auth
) -> ProposalOut:
    try:
        proposal = create_proposal(session, body.workload_id, body.objective)
    except DomainError as exc:
        raise APIError(422, "cannot_optimize", str(exc)) from exc
    return proposal_out(proposal)


@router.get(
    "/api/optimizations", response_model=Page[ProposalOut], tags=["optimizations"]
)
def list_optimizations(
    session: DbSession,
    _: str = auth,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> Page[ProposalOut]:
    total = session.scalar(select(func.count(OptimizationProposal.id))) or 0
    rows = session.scalars(
        select(OptimizationProposal)
        .order_by(OptimizationProposal.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return Page[ProposalOut](
        items=[proposal_out(row) for row in rows], total=total, limit=limit, offset=offset
    )


@router.get("/api/optimizations/{proposal_id}", response_model=ProposalOut, tags=["optimizations"])
def get_optimization(proposal_id: str, session: DbSession, _: str = auth) -> ProposalOut:
    proposal = session.get(OptimizationProposal, proposal_id)
    if proposal is None:
        raise APIError(404, "not_found", "Optimization proposal not found.")
    return proposal_out(proposal)


async def _signal_decision(
    proposal: OptimizationProposal,
    decision: str,
    reason: str,
    request: Request,
    session: Session,
) -> Approval:
    if not proposal.workflow_id:
        raise APIError(409, "workflow_not_started", "Start the workflow before approving.")
    if proposal.status != "awaiting_approval":
        raise APIError(
            409,
            "not_awaiting_approval",
            f"Proposal is {proposal.status}, not awaiting approval.",
        )
    approval = session.scalar(select(Approval).where(Approval.proposal_id == proposal.id))
    if approval is not None and approval.decision != decision:
        raise APIError(409, "decision_conflict", "A different decision was already recorded.")
    if approval is None:
        approval = Approval(
            proposal_id=proposal.id,
            decision=decision,
            actor="api-token",
            reason=reason,
            workflow_id=proposal.workflow_id,
        )
        session.add(approval)
        try:
            session.flush()
        except IntegrityError as exc:
            session.rollback()
            raise APIError(409, "decision_conflict", "A decision was already recorded.") from exc
        record_audit(
            session,
            event_key=f"approval.{decision}:{approval.id}",
            event_type=f"approval.{decision}",
            message=f"Human decision: {decision}",
            proposal_id=proposal.id,
            workflow_id=proposal.workflow_id,
            payload={"approval_id": approval.id, "reason": reason},
        )
        session.commit()
    try:
        if decision == "approved":
            await gateway(request).approve(proposal.workflow_id, approval.id)
        else:
            await gateway(request).reject(proposal.workflow_id, approval.id, reason)
    except TemporalUnavailable as exc:
        raise APIError(
            503,
            "temporal_unavailable",
            "Approval was recorded but the signal could not be delivered. Retry this request.",
        ) from exc
    return approval


@router.post(
    "/api/optimizations/{proposal_id}/approve",
    response_model=ApprovalOut,
    tags=["optimizations"],
)
async def approve_optimization(
    proposal_id: str,
    body: ApprovalRequest,
    request: Request,
    session: DbSession,
    _: str = auth,
) -> ApprovalOut:
    proposal = session.get(OptimizationProposal, proposal_id)
    if proposal is None:
        raise APIError(404, "not_found", "Optimization proposal not found.")
    approval = await _signal_decision(proposal, "approved", body.reason, request, session)
    return ApprovalOut.model_validate(approval)


@router.post(
    "/api/optimizations/{proposal_id}/reject",
    response_model=ApprovalOut,
    tags=["optimizations"],
)
async def reject_optimization(
    proposal_id: str,
    body: RejectRequest,
    request: Request,
    session: DbSession,
    _: str = auth,
) -> ApprovalOut:
    proposal = session.get(OptimizationProposal, proposal_id)
    if proposal is None:
        raise APIError(404, "not_found", "Optimization proposal not found.")
    approval = await _signal_decision(proposal, "rejected", body.reason, request, session)
    return ApprovalOut.model_validate(approval)


@router.post(
    "/api/workflows",
    response_model=WorkflowOut,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["workflows"],
)
async def start_workflow(
    body: WorkflowStart, request: Request, session: DbSession, _: str = auth
) -> WorkflowOut:
    proposal = session.get(OptimizationProposal, body.proposal_id)
    if proposal is None:
        raise APIError(404, "not_found", "Optimization proposal not found.")
    existing = session.scalar(
        select(WorkflowRef).where(WorkflowRef.proposal_id == proposal.id)
    )
    if existing is not None:
        finished = {"completed", "failed", "cancelled", "rejected", "needs_intervention"}
        if existing.status in finished:
            raise APIError(409, "workflow_finished", f"Workflow already {existing.status}.")
        return workflow_out(existing, await gateway(request).query_status(existing.workflow_id))
    if not proposal.selected_candidate_id:
        raise APIError(422, "no_candidate", "Proposal has no eligible selected candidate.")
    workflow_id = f"optimization-{proposal.id}"
    ref = WorkflowRef(
        workflow_id=workflow_id,
        proposal_id=proposal.id,
        stage="created",
        status="running",
        meta={},
    )
    proposal.workflow_id = workflow_id
    proposal.status = "proposed"
    session.add(ref)
    record_audit(
        session,
        event_key=f"workflow.started:{workflow_id}",
        event_type="workflow.started",
        message="Optimization workflow started",
        proposal_id=proposal.id,
        workflow_id=workflow_id,
        payload={"approval_timeout_seconds": get_settings().wattson_approval_timeout_seconds},
    )
    session.commit()
    try:
        await gateway(request).start_optimization(
            proposal.id, get_settings().wattson_approval_timeout_seconds
        )
    except TemporalUnavailable as exc:
        ref.status = "failed"
        ref.last_error = "Temporal unavailable at start"
        proposal.error = ref.last_error
        session.commit()
        raise APIError(
            503,
            "temporal_unavailable",
            "Could not start the workflow. Is the Temporal server and worker running?",
        ) from exc
    session.refresh(ref)
    return workflow_out(ref, None)


@router.get("/api/workflows", response_model=Page[WorkflowOut], tags=["workflows"])
def list_workflows(
    session: DbSession,
    _: str = auth,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> Page[WorkflowOut]:
    total = session.scalar(select(func.count(WorkflowRef.id))) or 0
    rows = session.scalars(
        select(WorkflowRef)
        .order_by(WorkflowRef.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    items = []
    for row in rows:
        proposal = session.get(OptimizationProposal, row.proposal_id)
        report = proposal.report if proposal else None
        items.append(workflow_out(row, None, report=report))
    return Page[WorkflowOut](items=items, total=total, limit=limit, offset=offset)


@router.get("/api/workflows/{workflow_id}", response_model=WorkflowOut, tags=["workflows"])
async def get_workflow(
    workflow_id: str, request: Request, session: DbSession, _: str = auth
) -> WorkflowOut:
    ref = session.scalar(select(WorkflowRef).where(WorkflowRef.workflow_id == workflow_id))
    if ref is None:
        raise APIError(404, "not_found", "Workflow not found.")
    proposal = session.get(OptimizationProposal, ref.proposal_id)
    report = proposal.report if proposal else None
    live = await gateway(request).query_status(workflow_id)
    return workflow_out(ref, live, report=report)


@router.post(
    "/api/workflows/{workflow_id}/cancel",
    response_model=MessageOut,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["workflows"],
)
async def cancel_workflow(
    workflow_id: str,
    body: CancelRequest,
    request: Request,
    session: DbSession,
    _: str = auth,
) -> MessageOut:
    ref = session.scalar(select(WorkflowRef).where(WorkflowRef.workflow_id == workflow_id))
    if ref is None:
        raise APIError(404, "not_found", "Workflow not found.")
    if ref.status in {"completed", "failed", "cancelled", "rejected", "needs_intervention"}:
        raise APIError(409, "workflow_finished", f"Workflow already {ref.status}.")
    try:
        await gateway(request).cancel(workflow_id, body.reason)
    except TemporalUnavailable as exc:
        raise APIError(
            503, "temporal_unavailable", "Could not deliver cancellation signal."
        ) from exc
    ref.meta = {**(ref.meta or {}), "cancel_requested": True, "cancel_reason": body.reason}
    record_audit(
        session,
        event_key=f"workflow.cancel_requested:{workflow_id}",
        event_type="workflow.cancel_requested",
        message="Cancellation requested",
        proposal_id=ref.proposal_id,
        workflow_id=workflow_id,
        payload={"reason": body.reason},
    )
    session.commit()
    return MessageOut(ok=True, message="Cancellation signal sent.")


@router.get("/api/reports", response_model=Page[ReportOut], tags=["reports"])
def list_reports(
    session: DbSession,
    _: str = auth,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> Page[ReportOut]:
    total = session.scalar(select(func.count(Report.id))) or 0
    rows = session.scalars(
        select(Report).order_by(Report.created_at.desc()).limit(limit).offset(offset)
    ).all()
    return Page[ReportOut](
        items=[ReportOut.model_validate(row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/api/reports/{report_id}", response_model=ReportOut, tags=["reports"])
def get_report(report_id: str, session: DbSession, _: str = auth) -> ReportOut:
    report = session.get(Report, report_id)
    if report is None:
        raise APIError(404, "not_found", "Report not found.")
    return ReportOut.model_validate(report)


@router.get("/api/audit", response_model=Page[AuditOut], tags=["audit"])
def audit_log(
    session: DbSession,
    _: str = auth,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    event_type: str | None = Query(default=None, max_length=80),
    proposal_id: str | None = Query(default=None, max_length=32),
) -> Page[AuditOut]:
    rows, total = list_audit(
        session, limit=limit, offset=offset, event_type=event_type, proposal_id=proposal_id
    )
    return Page[AuditOut](
        items=[AuditOut.model_validate(row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


def _settings_out(session: Session) -> SettingsOut:
    settings = get_settings()
    active, source = effective_kill_switch(session)
    return SettingsOut(
        kill_switch_active=active,
        kill_switch_source=source,
        kill_switch_env=settings.wattson_kill_switch,
        provider=settings.wattson_provider,
        ai_provider=settings.wattson_ai_provider,
        gemma_model=settings.gemma_model,
        ai_configured=settings.ai_configured,
        temporal_host=settings.wattson_temporal_host,
        temporal_namespace=settings.wattson_temporal_namespace,
        task_queue=settings.wattson_temporal_task_queue,
        database_driver=settings.wattson_database_url.split("://", 1)[0],
        api_token_configured=bool(settings.wattson_api_token),
    )


@router.get("/api/settings", response_model=SettingsOut, tags=["settings"])
def get_app_settings(session: DbSession, _: str = auth) -> SettingsOut:
    return _settings_out(session)


@router.patch("/api/settings", response_model=SettingsOut, tags=["settings"])
def update_app_settings(
    body: SettingsUpdate, session: DbSession, _: str = auth
) -> SettingsOut:
    set_kill_switch(session, body.kill_switch, actor="api-token")
    return _settings_out(session)


# Demo-only seeding is intentionally a CLI concern (python -m wattson.demo). No
# unauthenticated seed endpoint exists. This route is not exposed; the import
# keeps the seed contract close to the API surface during development.
__all__ = ["router", "SCENARIOS", "seed_demo_workloads"]
