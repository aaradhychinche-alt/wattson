"""A completed stage must not make the workflow look finished."""

from __future__ import annotations

from sqlalchemy import select

from wattson.db import session_scope
from wattson.models import OptimizationProposal, WorkflowRef, Workload
from wattson.services.proposals import create_proposal
from wattson.workflow_activities import finalize, record_stage


def test_stage_updates_keep_workflow_running_until_finalize(database: object) -> None:
    with session_scope() as session:
        workload = session.scalar(select(Workload).limit(1))
        assert workload is not None
        proposal = create_proposal(session, workload.id)
        proposal.workflow_id = "test-stage-workflow"
        session.add(
            WorkflowRef(
                workflow_id=proposal.workflow_id,
                proposal_id=proposal.id,
                stage="created",
                status="running",
                meta={},
            )
        )
        session.commit()
        proposal_id = proposal.id

    record_stage(
        {
            "workflow_id": "test-stage-workflow",
            "proposal_id": proposal_id,
            "stage": "compare",
            "status": "completed",
            "note": "compare done",
        }
    )
    with session_scope() as session:
        ref = session.scalar(
            select(WorkflowRef).where(WorkflowRef.workflow_id == "test-stage-workflow")
        )
        assert ref is not None
        assert ref.stage == "compare"
        assert ref.status == "running"

    finalize(
        {
            "proposal_id": proposal_id,
            "workflow_id": "test-stage-workflow",
            "status": "completed",
            "verdict": "improved",
        }
    )
    with session_scope() as session:
        ref = session.scalar(
            select(WorkflowRef).where(WorkflowRef.workflow_id == "test-stage-workflow")
        )
        assert ref is not None
        assert ref.status == "completed"
        proposal = session.get(OptimizationProposal, proposal_id)
        assert proposal is not None
        assert proposal.status == "completed"
