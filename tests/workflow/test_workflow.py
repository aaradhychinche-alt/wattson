"""Temporal workflow tests on a time-skipping test server.

These tests use the real workflow and real activities against a temporary
SQLite database. They never contact a cloud provider or spend money.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest
from sqlalchemy import select
from temporalio.client import WorkflowHandle
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from wattson.db import session_scope
from wattson.models import (
    Approval,
    AuditEvent,
    OptimizationProposal,
    Report,
    Run,
    Workload,
)
from wattson.services.proposals import create_proposal
from wattson.workflow_activities import (
    analyze_plan,
    build_report,
    cleanup,
    collect_results,
    compare_results,
    execute_candidate,
    finalize,
    generate_candidates,
    load_baseline,
    record_stage,
    request_approval,
    revalidate,
    simulate_candidates,
    validate_plan,
    validate_proposal,
)
from wattson.workflows import OptimizationWorkflow

TASK_QUEUE = "wattson-test"

ACTIVITIES = [
    record_stage,
    validate_plan,
    load_baseline,
    generate_candidates,
    analyze_plan,
    validate_proposal,
    simulate_candidates,
    request_approval,
    revalidate,
    execute_candidate,
    collect_results,
    compare_results,
    build_report,
    cleanup,
    finalize,
]


@pytest.fixture()
async def environment() -> AsyncIterator[WorkflowEnvironment]:
    env = await WorkflowEnvironment.start_time_skipping()
    yield env
    await env.shutdown()


@pytest.fixture()
async def worker(environment: WorkflowEnvironment) -> AsyncIterator[None]:
    with ThreadPoolExecutor(max_workers=8) as executor:
        worker = Worker(
            environment.client,
            task_queue=TASK_QUEUE,
            workflows=[OptimizationWorkflow],
            activities=ACTIVITIES,
            activity_executor=executor,
        )
        async with worker:
            yield


def make_proposal(scenario_index: int = 0) -> tuple[str, str, str]:
    marker = "Vision" if scenario_index == 0 else "Speech"
    with session_scope() as session:
        workload = session.scalar(select(Workload).where(Workload.name.like(f"%{marker}%")))
        assert workload is not None
        proposal = create_proposal(session, workload.id, "balanced")
        workflow_id = f"test-{uuid.uuid4().hex[:12]}"
        proposal.workflow_id = workflow_id
        session.commit()
        return proposal.id, workflow_id, proposal.selected_candidate_id or ""


async def start(
    environment: WorkflowEnvironment, proposal_id: str, workflow_id: str, timeout: int = 3600
) -> WorkflowHandle[Any, Any]:
    return await environment.client.start_workflow(
        "OptimizationWorkflow",
        {"proposal_id": proposal_id, "approval_timeout_seconds": timeout},
        id=workflow_id,
        task_queue=TASK_QUEUE,
    )


def add_approval(proposal_id: str, decision: str = "approved") -> str:
    with session_scope() as session:
        approval = Approval(
            proposal_id=proposal_id,
            decision=decision,
            actor="test",
            reason="test decision",
        )
        session.add(approval)
        session.commit()
        return approval.id


async def test_approved_run_completes_with_a_single_idempotent_launch(
    database: Any, environment: WorkflowEnvironment, worker: None
) -> None:
    proposal_id, workflow_id, candidate_id = make_proposal(0)
    assert candidate_id
    approval_id = add_approval(proposal_id)

    handle = await start(environment, proposal_id, workflow_id)
    await handle.signal("approve", approval_id)
    result = await handle.result()
    assert result["status"] == "completed"
    assert result["verdict"] == "improved"

    with session_scope() as session:
        proposal = session.get(OptimizationProposal, proposal_id)
        assert proposal is not None
        assert proposal.status == "completed"
        report = session.scalar(select(Report).where(Report.proposal_id == proposal_id))
        assert report is not None
        assert report.verdict == "improved"
        assert report.summary["metrics"]["cost_usd"]["result_provenance"] == "simulated"
        assert report.completeness["ratio"] == 1.0

        runs = session.scalars(
            select(Run).where(Run.workload_id == proposal.workload_id, Run.kind == "optimization")
        ).all()
        assert len(runs) == 1
        assert runs[0].provider_instance_id
        assert runs[0].status == "completed"

        launches = session.scalars(
            select(AuditEvent).where(
                AuditEvent.event_type == "provider.launched",
                AuditEvent.workflow_id == workflow_id,
            )
        ).all()
        assert len(launches) == 1
        retries = session.scalars(
            select(AuditEvent).where(
                AuditEvent.event_type == "activity.retry",
                AuditEvent.workflow_id == workflow_id,
            )
        ).all()
        assert len(retries) == 1
        finished = session.scalars(
            select(AuditEvent).where(
                AuditEvent.event_type == "workflow.finished",
                AuditEvent.workflow_id == workflow_id,
            )
        ).all()
        assert len(finished) == 1


async def test_throttled_execution_is_reported_as_regressed(
    database: Any, environment: WorkflowEnvironment, worker: None
) -> None:
    proposal_id, workflow_id, _ = make_proposal(1)
    approval_id = add_approval(proposal_id)
    handle = await start(environment, proposal_id, workflow_id)
    await handle.signal("approve", approval_id)
    result = await handle.result()

    assert result["status"] == "completed"
    assert result["verdict"] == "regressed"
    with session_scope() as session:
        report = session.scalar(select(Report).where(Report.proposal_id == proposal_id))
        assert report is not None
        assert report.verdict == "regressed"
        assert report.overall_change_pct is not None and report.overall_change_pct < 0
        assert "regress" in report.narrative.lower()


async def test_missing_recorded_approval_blocks_execution(
    database: Any, environment: WorkflowEnvironment, worker: None
) -> None:
    proposal_id, workflow_id, _ = make_proposal(0)
    handle = await start(environment, proposal_id, workflow_id)
    await handle.signal("approve", "approval-does-not-exist")
    result = await handle.result()

    assert result["status"] == "needs_intervention"
    with session_scope() as session:
        assert session.scalar(
            select(Run).where(Run.idempotency_key.like(f"{workflow_id}%"))
        ) is None
        launches = session.scalars(
            select(AuditEvent).where(
                AuditEvent.event_type == "provider.launched",
                AuditEvent.workflow_id == workflow_id,
            )
        ).all()
        assert launches == []
        proposal = session.get(OptimizationProposal, proposal_id)
        assert proposal is not None
        assert proposal.status == "needs_intervention"


async def test_rejection_ends_workflow_without_execution(
    database: Any, environment: WorkflowEnvironment, worker: None
) -> None:
    proposal_id, workflow_id, _ = make_proposal(0)
    approval_id = add_approval(proposal_id, decision="rejected")
    handle = await start(environment, proposal_id, workflow_id)
    await handle.signal(
        "reject", {"approval_id": approval_id, "reason": "too risky for production"}
    )
    result = await handle.result()

    assert result["status"] == "rejected"
    with session_scope() as session:
        runs = session.scalars(
            select(Run).where(Run.idempotency_key.like(f"{workflow_id}%"))
        ).all()
        assert runs == []
        proposal = session.get(OptimizationProposal, proposal_id)
        assert proposal is not None and proposal.status == "rejected"


async def test_cancellation_before_approval_ends_without_execution(
    database: Any, environment: WorkflowEnvironment, worker: None
) -> None:
    proposal_id, workflow_id, _ = make_proposal(0)
    handle = await start(environment, proposal_id, workflow_id)
    await handle.signal("cancel", "operator cancelled")
    result = await handle.result()

    assert result["status"] == "cancelled"
    with session_scope() as session:
        runs = session.scalars(
            select(Run).where(Run.idempotency_key.like(f"{workflow_id}%"))
        ).all()
        assert runs == []
        proposal = session.get(OptimizationProposal, proposal_id)
        assert proposal is not None and proposal.status == "cancelled"


async def test_approval_timeout_requires_human_intervention(
    database: Any, environment: WorkflowEnvironment, worker: None
) -> None:
    proposal_id, workflow_id, _ = make_proposal(0)
    handle = await start(environment, proposal_id, workflow_id, timeout=30)
    result = await handle.result()

    assert result["status"] == "needs_intervention"
    assert "timed out" in result["error"]
    with session_scope() as session:
        proposal = session.get(OptimizationProposal, proposal_id)
        assert proposal is not None
        assert proposal.status == "needs_intervention"
        assert proposal.error and "timed out" in proposal.error
