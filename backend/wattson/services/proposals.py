"""Proposal orchestration shared by API and workflow activities."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..ai import analyze_with_fallback
from ..ai.schemas import PolicyError, validate_tweak
from ..assumptions import load_assumptions
from ..config import get_settings
from ..db import utcnow
from ..models import OptimizationProposal, Run, Workload
from ..optimizer import ConstraintInput, PlanContext, plan_optimization
from ..providers.jarvislabs import JARVISLABS_GPUS
from .audit import record_audit


class DomainError(ValueError):
    pass


def latest_baseline(session: Session, workload_id: str) -> Run | None:
    return session.scalar(
        select(Run)
        .where(Run.workload_id == workload_id, Run.kind == "baseline", Run.status == "completed")
        .order_by(Run.completed_at.desc(), Run.created_at.desc())
    )


def _workload_dict(workload: Workload) -> dict[str, Any]:
    return {
        "id": workload.id,
        "name": workload.name,
        "description": workload.description,
        "workload_type": workload.workload_type,
        "provider": workload.provider,
        "current_config": workload.current_config,
        "constraints": workload.constraints,
        "meta": workload.meta,
    }


def create_proposal(
    session: Session, workload_id: str, objective: str = "balanced"
) -> OptimizationProposal:
    workload = session.get(Workload, workload_id)
    if workload is None:
        raise DomainError("workload not found")
    baseline = latest_baseline(session, workload.id)
    if baseline is None:
        raise DomainError("workload has no completed baseline run")
    assumptions = load_assumptions()
    dataset_samples = int(
        workload.meta.get("dataset_samples") or assumptions.default_dataset_samples
    )
    constraints = ConstraintInput.model_validate(workload.constraints or {})
    provider = workload.provider
    context = PlanContext(
        provider=provider,  # type: ignore[arg-type]
        provider_gpu_types=list(JARVISLABS_GPUS) if provider == "jarvislabs" else None,
        now=utcnow(),
    )
    plan = plan_optimization(
        dataset_samples=dataset_samples,
        constraints=constraints,
        context=context,
        objective=objective,
        assumptions=assumptions,
    )
    logs = str(workload.meta.get("logs") or "")
    analysis = analyze_with_fallback(_workload_dict(workload), logs, settings=get_settings())
    if analysis.payload.proposed_tweak is not None:
        try:
            validate_tweak(analysis.payload.proposed_tweak)
        except PolicyError as exc:
            analysis = analyze_with_fallback(
                _workload_dict(workload), logs, settings=get_settings()
            )
            analysis.fallback_reason = f"model tweak rejected by policy: {exc}"

    proposal = OptimizationProposal(
        workload_id=workload.id,
        baseline_run_id=baseline.id,
        status="proposed",
        objective=objective,
        weights=plan.weights.model_dump(),
        config_snapshot=workload.current_config,
        constraints_snapshot=workload.constraints,
        candidates=[candidate.model_dump(mode="json") for candidate in plan.candidates],
        selected_candidate_id=plan.selected_candidate_id,
        analysis=analysis.model_dump(mode="json"),
        normalization=plan.normalization,
    )
    session.add(proposal)
    session.flush()
    record_audit(
        session,
        event_key=f"proposal.created:{proposal.id}",
        event_type="proposal.created",
        message="Optimization proposal created",
        proposal_id=proposal.id,
        payload={
            "objective": objective,
            "candidates": len(plan.candidates),
            "eligible": sum(1 for c in plan.candidates if c.eligible),
            "selected_candidate_id": plan.selected_candidate_id,
            "analysis_source": analysis.source,
        },
    )
    session.commit()
    session.refresh(proposal)
    return proposal


def ensure_candidates(session: Session, proposal: OptimizationProposal) -> dict[str, Any]:
    """Workflow step: validate stored candidates or regenerate deterministically."""
    if proposal.candidates:
        eligible = [c for c in proposal.candidates if c.get("eligible")]
        if not eligible:
            raise DomainError("no candidate survives the hard constraints")
        selected = next(
            (c for c in eligible if c["id"] == proposal.selected_candidate_id), None
        )
        if selected is None:
            selected = sorted(eligible, key=lambda c: (c.get("score", 1e9), c["id"]))[0]
            proposal.selected_candidate_id = selected["id"]
            session.commit()
        return {
            "candidates": len(proposal.candidates),
            "eligible": len(eligible),
            "selected_candidate_id": selected["id"],
            "regenerated": False,
        }
    workload = session.get(Workload, proposal.workload_id)
    if workload is None:
        raise DomainError("workload not found")
    assumptions = load_assumptions()
    dataset_samples = int(
        workload.meta.get("dataset_samples") or assumptions.default_dataset_samples
    )
    context = PlanContext(
        provider=workload.provider,  # type: ignore[arg-type]
        provider_gpu_types=(
            list(JARVISLABS_GPUS) if workload.provider == "jarvislabs" else None
        ),
    )
    baseline = latest_baseline(session, workload.id)
    if baseline is None:
        raise DomainError("workload has no completed baseline run")
    plan = plan_optimization(
        dataset_samples=dataset_samples,
        constraints=ConstraintInput.model_validate(workload.constraints or {}),
        context=context,
        objective=proposal.objective,
    )
    proposal.baseline_run_id = baseline.id
    proposal.weights = plan.weights.model_dump()
    proposal.candidates = [c.model_dump(mode="json") for c in plan.candidates]
    proposal.selected_candidate_id = plan.selected_candidate_id
    proposal.normalization = plan.normalization
    session.commit()
    eligible_count = sum(1 for c in plan.candidates if c.eligible)
    if eligible_count == 0:
        raise DomainError("no candidate survives the hard constraints")
    return {
        "candidates": len(plan.candidates),
        "eligible": eligible_count,
        "selected_candidate_id": plan.selected_candidate_id,
        "regenerated": True,
    }


def selected_candidate(proposal: OptimizationProposal) -> dict[str, Any]:
    for candidate in proposal.candidates:
        if candidate.get("id") == proposal.selected_candidate_id:
            return candidate
    raise DomainError("proposal has no selected candidate")
