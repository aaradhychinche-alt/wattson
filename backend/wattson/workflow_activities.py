"""Temporal activities: all DB, provider, and model I/O lives here."""

from __future__ import annotations

import re
from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from temporalio import activity
from temporalio.exceptions import ApplicationError

from .ai import analyze_with_fallback
from .ai.schemas import PolicyError, ProposedTweak, validate_tweak
from .assumptions import load_assumptions
from .db import session_scope, utcnow
from .models import (
    Approval,
    Measurement,
    OptimizationProposal,
    Run,
    WorkflowRef,
    Workload,
)
from .optimizer import ConstraintInput
from .provenance import METRIC_UNITS
from .providers import get_provider
from .providers.base import (
    PermanentProviderError,
    ProvisionedInstance,
    ProvisionRequest,
    TransientProviderError,
)
from .services.audit import record_audit
from .services.kill_switch import effective_kill_switch
from .services.proposals import ensure_candidates, selected_candidate
from .services.reports import persist_report
from .simulator_math import CandidateConfig

SAFETY_ERROR_TYPES = {
    "InvalidConfig",
    "ApprovalRequired",
    "KillSwitchActive",
    "BudgetExceeded",
    "CapabilityMissing",
    "ProviderNotConnected",
    "MissingBaseline",
}


def _attempt() -> int:
    try:
        return activity.info().attempt
    except RuntimeError:
        return 1


def _safe_error(exc: BaseException) -> str:
    text = str(exc)
    text = re.sub(r"(?i)(api[_-]?key|token|authorization)\s*[=:]\s*\S+", r"\1=[redacted]", text)
    return text[:1000]


def _non_retryable(message: str, type_name: str = "PermanentFailure") -> ApplicationError:
    return ApplicationError(message, type=type_name, non_retryable=True)


def _permanent(exc: BaseException) -> ApplicationError:
    if isinstance(exc, TransientProviderError):
        return ApplicationError(_safe_error(exc), type="TransientProviderFailure")
    if isinstance(exc, PermanentProviderError):
        return _non_retryable(_safe_error(exc), type_name="CapabilityMissing")
    return _non_retryable(_safe_error(exc), type_name="ProviderFailure")


def _mark_attempt(
    session: Any, *, workflow_id: str, proposal_id: str, step: str
) -> None:
    attempt = _attempt()
    if attempt <= 1:
        return
    ref = session.scalar(select(WorkflowRef).where(WorkflowRef.workflow_id == workflow_id))
    if ref is not None:
        ref.retries = max(ref.retries, attempt - 1)
    record_audit(
        session,
        event_key=f"activity.retry:{workflow_id}:{step}:{attempt}",
        event_type="activity.retry",
        message=f"Activity {step} retrying (attempt {attempt})",
        proposal_id=proposal_id,
        workflow_id=workflow_id,
        payload={"step": step, "attempt": attempt},
    )
    session.commit()


@activity.defn
def record_stage(payload: dict[str, Any]) -> dict[str, Any]:
    workflow_id = payload["workflow_id"]
    proposal_id = payload["proposal_id"]
    stage = payload["stage"]
    status = payload.get("status", "running")
    note = payload.get("note", "")
    with session_scope() as session:
        ref = session.scalar(select(WorkflowRef).where(WorkflowRef.workflow_id == workflow_id))
        if ref is None:
            ref = WorkflowRef(
                workflow_id=workflow_id,
                proposal_id=proposal_id,
                stage=stage,
                status=status,
                meta={},
            )
            session.add(ref)
        else:
            ref.stage = stage
            # Only finalize() may mark a workflow terminal. A completed *stage*
            # must not make the polling API report the workflow as completed
            # before the report exists.
            if status in {"running", "completed"}:
                ref.status = "running"
        ref.last_error = payload.get("error") or ref.last_error
        ref.meta = {
            **(ref.meta or {}),
            "last_stage_at": utcnow().isoformat(),
            "last_note": note,
        }
        record_audit(
            session,
            event_key=f"workflow.stage:{workflow_id}:{stage}:{status}",
            event_type=f"workflow.stage.{status}",
            message=note or f"Stage {stage} {status}",
            proposal_id=proposal_id,
            workflow_id=workflow_id,
            payload={"stage": stage, "status": status},
        )
        session.commit()
        return {"stage": stage, "status": status}


@activity.defn
def validate_plan(proposal_id: str) -> dict[str, Any]:
    with session_scope() as session:
        proposal = session.get(OptimizationProposal, proposal_id)
        if proposal is None:
            raise _non_retryable("proposal not found", "InvalidConfig")
        workload = session.get(Workload, proposal.workload_id)
        if workload is None:
            raise _non_retryable("workload not found", "InvalidConfig")
        if proposal.baseline_run_id is None:
            raise _non_retryable("proposal has no baseline", "MissingBaseline")
        baseline = session.get(Run, proposal.baseline_run_id)
        if baseline is None or baseline.status != "completed":
            raise _non_retryable("baseline run is missing or incomplete", "MissingBaseline")
        try:
            CandidateConfig.model_validate(workload.current_config)
        except Exception as exc:
            raise _non_retryable(f"invalid workload config: {exc}", "InvalidConfig") from exc
        try:
            constraints = ConstraintInput.model_validate(workload.constraints or {})
        except Exception as exc:
            raise _non_retryable(f"invalid constraints: {exc}", "InvalidConfig") from exc
        dataset_samples = int(
            workload.meta.get("dataset_samples") or load_assumptions().default_dataset_samples
        )
        if dataset_samples <= 0:
            raise _non_retryable("dataset_samples must be positive", "InvalidConfig")
        return {
            "proposal_id": proposal.id,
            "workload_id": workload.id,
            "baseline_run_id": baseline.id,
            "provider": workload.provider,
            "dataset_samples": dataset_samples,
            "budget_usd": constraints.budget_usd,
            "max_runtime_hours": constraints.max_runtime_hours,
            "deadline_at": constraints.deadline_at.isoformat() if constraints.deadline_at else None,
            "workflow_id": proposal.workflow_id,
        }


@activity.defn
def load_baseline(proposal_id: str) -> dict[str, Any]:
    with session_scope() as session:
        proposal = session.get(OptimizationProposal, proposal_id)
        if proposal is None or proposal.baseline_run_id is None:
            raise _non_retryable("baseline unavailable", "MissingBaseline")
        baseline = session.get(Run, proposal.baseline_run_id)
        if baseline is None:
            raise _non_retryable("baseline unavailable", "MissingBaseline")
        metrics = {
            m.metric: {
                "value": m.value,
                "unit": m.unit,
                "provenance": m.provenance,
                "measured_at": m.measured_at.isoformat(),
                "source": m.source,
                "available": m.value is not None,
            }
            for m in baseline.measurements
        }
        return {
            "run_id": baseline.id,
            "started_at": baseline.started_at.isoformat() if baseline.started_at else None,
            "completed_at": baseline.completed_at.isoformat() if baseline.completed_at else None,
            "metrics": metrics,
        }


@activity.defn
def generate_candidates(proposal_id: str) -> dict[str, Any]:
    with session_scope() as session:
        proposal = session.get(OptimizationProposal, proposal_id)
        if proposal is None:
            raise _non_retryable("proposal not found", "InvalidConfig")
        try:
            result = ensure_candidates(session, proposal)
        except Exception as exc:
            raise _non_retryable(f"candidate generation failed: {exc}", "InvalidConfig") from exc
        return result


@activity.defn
def analyze_plan(proposal_id: str) -> dict[str, Any]:
    with session_scope() as session:
        proposal = session.get(OptimizationProposal, proposal_id)
        if proposal is None:
            raise _non_retryable("proposal not found", "InvalidConfig")
        workload = session.get(Workload, proposal.workload_id)
        if workload is None:
            raise _non_retryable("workload not found", "InvalidConfig")
        stored = proposal.analysis or {}
        if not stored.get("payload"):
            analysis = analyze_with_fallback(
                {
                    "id": workload.id,
                    "name": workload.name,
                    "description": workload.description,
                    "workload_type": workload.workload_type,
                    "provider": workload.provider,
                    "current_config": workload.current_config,
                    "constraints": workload.constraints,
                    "meta": workload.meta,
                },
                str(workload.meta.get("logs") or ""),
            )
            stored = analysis.model_dump(mode="json")
            proposal.analysis = stored
            session.commit()
        try:
            tweak = stored["payload"].get("proposed_tweak")
            if tweak:
                validate_tweak(ProposedTweak(**tweak))
        except PolicyError as exc:
            raise _non_retryable(f"AI tweak rejected by policy: {exc}", "InvalidConfig") from exc
        return {
            "source": stored.get("source", "deterministic_fallback"),
            "provider": stored.get("provider", "deterministic"),
            "model": stored.get("model", ""),
            "fallback_reason": stored.get("fallback_reason"),
            "proposed_tweak": stored.get("payload", {}).get("proposed_tweak"),
        }


@activity.defn
def validate_proposal(proposal_id: str) -> dict[str, Any]:
    with session_scope() as session:
        proposal = session.get(OptimizationProposal, proposal_id)
        if proposal is None:
            raise _non_retryable("proposal not found", "InvalidConfig")
        if not proposal.candidates:
            raise _non_retryable("no candidates to validate", "InvalidConfig")
        try:
            candidate = selected_candidate(proposal)
            config = CandidateConfig.model_validate(candidate["config"])
        except Exception as exc:
            raise _non_retryable(f"selected candidate invalid: {exc}", "InvalidConfig") from exc
        if not candidate.get("eligible"):
            raise _non_retryable("selected candidate violates constraints", "InvalidConfig")
        return {
            "selected_candidate_id": candidate["id"],
            "config": config.as_dict(),
            "score": candidate.get("score"),
            "normalization": proposal.normalization,
        }


@activity.defn
def simulate_candidates(proposal_id: str) -> dict[str, Any]:
    with session_scope() as session:
        proposal = session.get(OptimizationProposal, proposal_id)
        if proposal is None:
            raise _non_retryable("proposal not found", "InvalidConfig")
        eligible = [c for c in proposal.candidates if c.get("eligible")]
        for candidate in eligible:
            candidate["provenance"] = "simulated"
        proposal.candidates = list(proposal.candidates)
        session.commit()
        return {
            "simulated": len(eligible),
            "rejected": len(proposal.candidates) - len(eligible),
            "provenance": "simulated",
        }


@activity.defn
def request_approval(payload: dict[str, Any]) -> dict[str, Any]:
    proposal_id = payload["proposal_id"]
    workflow_id = payload["workflow_id"]
    timeout_seconds = int(payload["approval_timeout_seconds"])
    with session_scope() as session:
        proposal = session.get(OptimizationProposal, proposal_id)
        if proposal is None:
            raise _non_retryable("proposal not found", "InvalidConfig")
        if proposal.status in {"cancelled", "rejected", "completed"}:
            return {"already_final": True, "status": proposal.status}
        proposal.status = "awaiting_approval"
        ref = session.scalar(select(WorkflowRef).where(WorkflowRef.workflow_id == workflow_id))
        if ref is not None:
            ref.stage = "awaiting_approval"
            ref.status = "running"
        record_audit(
            session,
            event_key=f"approval.requested:{proposal_id}",
            event_type="approval.requested",
            message="Workflow is blocked awaiting explicit approval",
            proposal_id=proposal_id,
            workflow_id=workflow_id,
            payload={
                "selected_candidate_id": proposal.selected_candidate_id,
                "timeout_seconds": timeout_seconds,
            },
        )
        session.commit()
        return {"awaiting": True, "timeout_seconds": timeout_seconds}


def _approval_state(
    session: Any, proposal_id: str, approval_id: str | None
) -> tuple[bool, str]:
    if not approval_id:
        return False, "approval_missing"
    approval = session.get(Approval, approval_id)
    if approval is None or approval.proposal_id != proposal_id:
        return False, "approval_not_found"
    if approval.decision != "approved":
        return False, "approval_not_approved"
    return True, "ok"


def _revalidate(
    session: Any, proposal: OptimizationProposal, approval_id: str | None
) -> dict[str, Any]:
    workload = session.get(Workload, proposal.workload_id)
    if workload is None:
        return {"ok": False, "code": "missing_workload", "message": "workload missing"}
    approved, code = _approval_state(session, proposal.id, approval_id)
    if not approved:
        return {"ok": False, "code": code, "message": "recorded approval is required"}
    kill_active, source = effective_kill_switch(session)
    if kill_active:
        return {
            "ok": False,
            "code": "kill_switch",
            "message": f"kill switch active ({source})",
        }
    candidate = selected_candidate(proposal)
    config = CandidateConfig.model_validate(candidate["config"])
    constraints = ConstraintInput.model_validate(workload.constraints or {})
    estimates = candidate.get("estimates") or {}
    cost = estimates.get("cost_usd")
    runtime = candidate.get("runtime_hours")
    if constraints.budget_usd is not None and cost is not None and cost > constraints.budget_usd:
        return {
            "ok": False,
            "code": "budget_exceeded",
            "message": f"estimated ${cost:.2f} exceeds ${constraints.budget_usd:.2f}",
        }
    if (
        constraints.max_runtime_hours is not None
        and runtime is not None
        and runtime > constraints.max_runtime_hours
    ):
        return {
            "ok": False,
            "code": "runtime_exceeded",
            "message": f"estimated {runtime:.2f}h exceeds {constraints.max_runtime_hours:.2f}h",
        }
    if constraints.deadline_at is not None and runtime is not None:
        deadline = constraints.deadline_at
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=utcnow().tzinfo)
        if utcnow() + timedelta(hours=runtime) > deadline:
            return {"ok": False, "code": "deadline_exceeded", "message": "deadline would be missed"}
    provider = get_provider()
    if provider.name != workload.provider:
        return {
            "ok": False,
            "code": "provider_mismatch",
            "message": (
                f"workload requests {workload.provider} but WATTSON_PROVIDER is {provider.name}"
            ),
        }
    if not provider.supports(config.gpu_type):
        return {
            "ok": False,
            "code": "provider_capability_missing",
            "message": f"provider does not support {config.gpu_type}",
        }
    provider_status = provider.status()
    if workload.provider != "simulator" and provider_status.get("status") != "connected":
        return {
            "ok": False,
            "code": "provider_not_connected",
            "message": str(provider_status.get("detail", "provider is not connected")),
        }
    return {"ok": True, "code": "ok", "message": "revalidated", "provider": provider.name}


@activity.defn
def revalidate(payload: dict[str, Any]) -> dict[str, Any]:
    with session_scope() as session:
        proposal = session.get(OptimizationProposal, payload["proposal_id"])
        if proposal is None:
            return {"ok": False, "code": "missing_proposal", "message": "proposal missing"}
        return _revalidate(session, proposal, payload.get("approval_id"))


@activity.defn
def execute_candidate(payload: dict[str, Any]) -> dict[str, Any]:
    proposal_id = payload["proposal_id"]
    workflow_id = payload["workflow_id"]
    idempotency_key = payload["idempotency_key"]
    approval_id = payload.get("approval_id")
    with session_scope() as session:
        _mark_attempt(session, workflow_id=workflow_id, proposal_id=proposal_id, step="execute")
        proposal = session.get(OptimizationProposal, proposal_id)
        if proposal is None:
            raise _non_retryable("proposal not found", "InvalidConfig")
        existing = session.scalar(select(Run).where(Run.idempotency_key == idempotency_key))
        if existing is not None:
            return {
                "run_id": existing.id,
                "instance_id": existing.provider_instance_id,
                "provider": existing.provider,
                "deduplicated": True,
            }
        revalidation = _revalidate(session, proposal, approval_id)
        if not revalidation["ok"]:
            code = revalidation["code"]
            type_name = {
                "approval_missing": "ApprovalRequired",
                "approval_not_found": "ApprovalRequired",
                "approval_not_approved": "ApprovalRequired",
                "kill_switch": "KillSwitchActive",
                "budget_exceeded": "BudgetExceeded",
                "runtime_exceeded": "BudgetExceeded",
                "deadline_exceeded": "BudgetExceeded",
                "provider_capability_missing": "CapabilityMissing",
                "provider_not_connected": "ProviderNotConnected",
            }.get(code, "PermanentFailure")
            raise _non_retryable(revalidation["message"], type_name)
        workload = session.get(Workload, proposal.workload_id)
        if workload is None:
            raise _non_retryable("workload not found", "InvalidConfig")
        candidate = selected_candidate(proposal)
        config = CandidateConfig.model_validate(candidate["config"])
        dataset_samples = int(
            workload.meta.get("dataset_samples") or load_assumptions().default_dataset_samples
        )
        request = ProvisionRequest(
            proposal_id=proposal.id,
            workflow_id=workflow_id,
            idempotency_key=idempotency_key,
            config=config,
            dataset_samples=dataset_samples,
            runtime_hours=float(candidate.get("runtime_hours") or 0.0),
            execution_profile=str(workload.meta.get("execution_profile") or "nominal"),
            inject_transient_launch=bool(workload.meta.get("inject_transient_launch")),
            inject_transient_collect=bool(workload.meta.get("inject_transient_collect")),
            tags={"wattson:proposal": proposal.id, "wattson:workflow": workflow_id},
        )
        provider = get_provider()
        try:
            instance = provider.provision(request)
        except Exception as exc:
            session.rollback()
            raise _permanent(exc) from exc

        run = Run(
            workload_id=workload.id,
            kind="optimization",
            status="running",
            config=config.as_dict(),
            provider=provider.name,
            provider_instance_id=instance.instance_id,
            idempotency_key=idempotency_key,
            started_at=instance.created_at,
            notes=f"WATTSON-managed instance {instance.instance_id}",
        )
        session.add(run)
        try:
            session.flush()
        except IntegrityError:
            session.rollback()
            existing = session.scalar(
                select(Run).where(Run.idempotency_key == idempotency_key)
            )
            if existing is not None:
                return {
                    "run_id": existing.id,
                    "instance_id": existing.provider_instance_id,
                    "provider": existing.provider,
                    "deduplicated": True,
                }
            raise
        proposal.status = "executing"
        ref = session.scalar(select(WorkflowRef).where(WorkflowRef.workflow_id == workflow_id))
        if ref is not None:
            ref.run_id = run.id
            ref.stage = "execute"
        record_audit(
            session,
            event_key=f"provider.launch:{idempotency_key}",
            event_type="provider.launched",
            message=f"Provider instance launched ({provider.provenance})",
            proposal_id=proposal.id,
            workflow_id=workflow_id,
            payload={
                "instance_id": instance.instance_id,
                "provider": provider.name,
                "provenance": provider.provenance,
                "idempotency_key": idempotency_key,
            },
        )
        record_audit(
            session,
            event_key=f"execution.approved:{proposal.id}",
            event_type="execution.approved",
            message="Execution authorized by recorded approval",
            proposal_id=proposal.id,
            workflow_id=workflow_id,
            payload={"approval_id": approval_id},
        )
        session.commit()
        return {
            "run_id": run.id,
            "instance_id": instance.instance_id,
            "provider": provider.name,
            "deduplicated": False,
            "provenance": provider.provenance,
        }


@activity.defn
def collect_results(payload: dict[str, Any]) -> dict[str, Any]:
    proposal_id = payload["proposal_id"]
    run_id = payload["run_id"]
    workflow_id = payload["workflow_id"]
    idempotency_key = payload["idempotency_key"]
    with session_scope() as session:
        _mark_attempt(session, workflow_id=workflow_id, proposal_id=proposal_id, step="collect")
        run = session.get(Run, run_id)
        if run is None:
            raise _non_retryable("run not found", "InvalidConfig")
        if run.status == "completed" and run.measurements:
            return {
                "run_id": run.id,
                "metrics": {m.metric: m.value for m in run.measurements},
                "completed": True,
            }
        proposal = session.get(OptimizationProposal, proposal_id)
        if proposal is None:
            raise _non_retryable("proposal not found", "InvalidConfig")
        workload = session.get(Workload, proposal.workload_id)
        if workload is None:
            raise _non_retryable("workload not found", "InvalidConfig")
        candidate = selected_candidate(proposal)
        config = CandidateConfig.model_validate(candidate["config"])
        dataset_samples = int(
            workload.meta.get("dataset_samples") or load_assumptions().default_dataset_samples
        )
        request = ProvisionRequest(
            proposal_id=proposal.id,
            workflow_id=workflow_id,
            idempotency_key=idempotency_key,
            config=config,
            dataset_samples=dataset_samples,
            runtime_hours=float(candidate.get("runtime_hours") or 0.0),
            execution_profile=str(workload.meta.get("execution_profile") or "nominal"),
            inject_transient_launch=bool(workload.meta.get("inject_transient_launch")),
            inject_transient_collect=bool(workload.meta.get("inject_transient_collect")),
        )
        instance = ProvisionedInstance(
            instance_id=run.provider_instance_id or "",
            provider=run.provider,
            status="running",
            idempotency_key=idempotency_key,
            hourly_usd=None,
            created_at=run.started_at,
            meta={"tags": {"wattson:managed": "true"}},
        )
        provider = get_provider()
        try:
            metrics = provider.collect(instance, request)
        except Exception as exc:
            session.rollback()
            raise _permanent(exc) from exc
        values = {
            "cost_usd": metrics.cost_usd,
            "energy_kwh": metrics.energy_kwh,
            "latency_ms": metrics.latency_ms,
            "throughput_samples_s": metrics.throughput_samples_s,
            "runtime_hours": metrics.runtime_hours,
        }
        now = utcnow()
        for metric, value in values.items():
            existing = session.scalar(
                select(Measurement).where(
                    Measurement.run_id == run.id, Measurement.metric == metric
                )
            )
            if existing is None:
                session.add(
                    Measurement(
                        run_id=run.id,
                        metric=metric,
                        value=value,
                        unit=METRIC_UNITS[metric],
                        measured_at=now,
                        source=metrics.source,
                        provenance=metrics.provenance,
                        sample_count=metrics.sample_count,
                        notes=f"energy_source={metrics.energy_source}",
                    )
                )
            else:
                existing.value = value
                existing.measured_at = now
        run.status = "completed"
        run.completed_at = now
        proposal.status = "executing"
        record_audit(
            session,
            event_key=f"run.completed:{run.id}",
            event_type="run.completed",
            message="Result metrics collected",
            proposal_id=proposal.id,
            workflow_id=workflow_id,
            payload={"run_id": run.id, "provenance": metrics.provenance},
        )
        session.commit()
        return {
            "run_id": run.id,
            "metrics": values,
            "provenance": metrics.provenance,
            "source": metrics.source,
            "completed": True,
            "measurement_window": {
                "started_at": run.started_at.isoformat() if run.started_at else None,
                "completed_at": now.isoformat(),
            },
        }


@activity.defn
def compare_results(payload: dict[str, Any]) -> dict[str, Any]:
    from .services.reports import build_report_payload

    with session_scope() as session:
        proposal = session.get(OptimizationProposal, payload["proposal_id"])
        if proposal is None or proposal.baseline_run_id is None:
            raise _non_retryable("proposal/baseline missing", "MissingBaseline")
        baseline = session.get(Run, proposal.baseline_run_id)
        result = session.get(Run, payload["run_id"])
        if baseline is None or result is None:
            raise _non_retryable("baseline or result run missing", "MissingBaseline")
        comparison = build_report_payload(proposal, baseline, result)
        record_audit(
            session,
            event_key=f"comparison.completed:{proposal.id}",
            event_type="comparison.completed",
            message=f"Deterministic comparison verdict: {comparison['verdict']}",
            proposal_id=proposal.id,
            workflow_id=payload.get("workflow_id"),
            payload={
                "verdict": comparison["verdict"],
                "overall_change_pct": comparison["overall_change_pct"],
                "completeness": comparison["completeness"],
            },
        )
        session.commit()
        return {
            "verdict": comparison["verdict"],
            "overall_change_pct": comparison["overall_change_pct"],
            "completeness": comparison["completeness"],
        }


@activity.defn
def build_report(payload: dict[str, Any]) -> dict[str, Any]:
    proposal_id = payload["proposal_id"]
    workflow_id = payload["workflow_id"]
    run_id = payload["run_id"]
    with session_scope() as session:
        proposal = session.get(OptimizationProposal, proposal_id)
        if proposal is None or proposal.baseline_run_id is None:
            raise _non_retryable("proposal/baseline missing", "MissingBaseline")
        baseline = session.get(Run, proposal.baseline_run_id)
        result = session.get(Run, run_id)
        if baseline is None or result is None:
            raise _non_retryable("baseline or result run missing", "MissingBaseline")
        report = persist_report(session, proposal, baseline, result)
        proposal.status = "completed"
        record_audit(
            session,
            event_key=f"report.created:{report.id}",
            event_type="report.created",
            message=f"Report verdict: {report.verdict}",
            proposal_id=proposal.id,
            workflow_id=workflow_id,
            payload={
                "report_id": report.id,
                "verdict": report.verdict,
                "overall_change_pct": report.overall_change_pct,
                "narrative_source": report.narrative_source,
            },
        )
        session.commit()
        return {
            "report_id": report.id,
            "verdict": report.verdict,
            "overall_change_pct": report.overall_change_pct,
            "narrative_source": report.narrative_source,
        }


@activity.defn
def cleanup(payload: dict[str, Any]) -> dict[str, Any]:
    proposal_id = payload["proposal_id"]
    workflow_id = payload["workflow_id"]
    run_id = payload.get("run_id")
    if not run_id:
        return {"cleaned": False, "reason": "no instance launched"}
    with session_scope() as session:
        run = session.get(Run, run_id)
        if run is None or run.provider_instance_id is None:
            return {"cleaned": False, "reason": "no instance"}
        provider = get_provider()
        instance = ProvisionedInstance(
            instance_id=run.provider_instance_id,
            provider=run.provider,
            status="running",
            idempotency_key=run.idempotency_key or "",
            hourly_usd=None,
            created_at=run.started_at,
            meta={
                "tags": {"wattson:managed": "true"},
                "name": "wattson-" + (run.idempotency_key or "")[-12:],
            },
        )
        try:
            cleaned = provider.cleanup(instance)
        except Exception as exc:
            raise _permanent(exc) from exc
        record_audit(
            session,
            event_key=f"cleanup:{run.id}",
            event_type="cleanup.completed",
            message="Idempotent cleanup completed for WATTSON-owned resource",
            proposal_id=proposal_id,
            workflow_id=workflow_id,
            payload={"run_id": run.id, "instance_id": run.provider_instance_id, "cleaned": cleaned},
        )
        session.commit()
        return {"cleaned": cleaned, "run_id": run.id}


@activity.defn
def finalize(payload: dict[str, Any]) -> dict[str, Any]:
    proposal_id = payload["proposal_id"]
    workflow_id = payload["workflow_id"]
    status = payload["status"]
    error = (payload.get("error") or "")[:1000]
    verdict = payload.get("verdict")
    with session_scope() as session:
        proposal = session.get(OptimizationProposal, proposal_id)
        if proposal is not None:
            proposal.status = status
            proposal.error = error or None
        ref = session.scalar(select(WorkflowRef).where(WorkflowRef.workflow_id == workflow_id))
        if ref is not None:
            ref.status = status
            ref.stage = "finished"
            ref.last_error = error or ref.last_error
        record_audit(
            session,
            event_key=f"workflow.finished:{workflow_id}",
            event_type="workflow.finished",
            message=f"Workflow finished: {status}" + (f" ({error})" if error else ""),
            proposal_id=proposal_id,
            workflow_id=workflow_id,
            payload={"status": status, "verdict": verdict, "error": error},
        )
        session.commit()
        return {"proposal_id": proposal_id, "status": status, "verdict": verdict, "error": error}
