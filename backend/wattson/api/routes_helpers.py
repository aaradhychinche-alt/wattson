"""ORM -> API schema converters."""

from __future__ import annotations

from typing import Any

from ..api_schemas import (
    ApprovalOut,
    MeasurementOut,
    ProposalOut,
    RunOut,
    WorkflowOut,
)
from ..models import Measurement, OptimizationProposal, Report, Run, WorkflowRef


def measurement_out(row: Measurement) -> MeasurementOut:
    return MeasurementOut.from_row(row)


def run_out(run: Run) -> RunOut:
    data = RunOut.model_validate(run)
    data.measurements = [measurement_out(m) for m in run.measurements]
    return data


def proposal_out(proposal: OptimizationProposal) -> ProposalOut:
    approval = proposal.approval
    report = proposal.report
    return ProposalOut(
        id=proposal.id,
        workload_id=proposal.workload_id,
        baseline_run_id=proposal.baseline_run_id,
        status=proposal.status,
        objective=proposal.objective,
        weights=proposal.weights,
        config_snapshot=proposal.config_snapshot,
        constraints_snapshot=proposal.constraints_snapshot,
        candidates=proposal.candidates,
        selected_candidate_id=proposal.selected_candidate_id,
        analysis=proposal.analysis,
        normalization=proposal.normalization,
        workflow_id=proposal.workflow_id,
        error=proposal.error,
        created_at=proposal.created_at,
        updated_at=proposal.updated_at,
        approval=ApprovalOut.model_validate(approval) if approval else None,
        report_id=report.id if report else None,
        verdict=report.verdict if report else None,
    )


def workflow_out(
    ref: WorkflowRef, live: dict[str, Any] | None = None, report: Report | None = None
) -> WorkflowOut:
    stage = ref.stage
    last_error = ref.last_error
    if live:
        stage = str(live.get("stage") or stage)
        last_error = live.get("last_error") or last_error
    return WorkflowOut(
        workflow_id=ref.workflow_id,
        proposal_id=ref.proposal_id,
        run_id=ref.run_id,
        stage=stage,
        status=ref.status,
        retries=ref.retries,
        last_error=last_error,
        meta=ref.meta or {},
        created_at=ref.created_at,
        updated_at=ref.updated_at,
        live_stage=stage if live else None,
        verdict=report.verdict if report else None,
        report_id=report.id if report else None,
    )
