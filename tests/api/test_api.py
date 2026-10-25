"""HTTP contract, auth, approval-recording, and kill-switch tests."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select

from wattson.db import session_scope
from wattson.models import Approval, OptimizationProposal, WorkflowRef


def _workloads(client: TestClient, headers: dict[str, str]) -> list[dict[str, object]]:
    response = client.get("/api/workloads", headers=headers)
    assert response.status_code == 200
    return response.json()["items"]


def test_health_is_public_and_reports_provenance(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    names = {check["name"] for check in body["checks"]}
    assert {"database", "temporal", "provider", "gemma", "kepler"} <= names
    assert all(check["provenance"] for check in body["checks"])


def test_protected_routes_require_bearer_token(client: TestClient) -> None:
    response = client.get("/api/workloads")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"

    bad = client.get("/api/workloads", headers={"Authorization": "Bearer wrong"})
    assert bad.status_code == 401

    malformed = client.get("/api/workloads", headers={"Authorization": "Basic abc"})
    assert malformed.status_code == 401


def test_error_envelope_and_unknown_ids(client: TestClient, auth_headers: dict[str, str]) -> None:
    missing = client.get("/api/workloads/does-not-exist", headers=auth_headers)
    assert missing.status_code == 404
    assert missing.json() == {
        "error": {
            "code": "not_found",
            "message": "Workload not found.",
            "details": None,
        }
    }
    invalid = client.get("/api/workloads?limit=0", headers=auth_headers)
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "validation_error"


def test_list_and_create_workload(client: TestClient, auth_headers: dict[str, str]) -> None:
    assert len(_workloads(client, auth_headers)) == 2
    payload = {
        "name": "Test - new workload",
        "description": "A tiny test workload",
        "workload_type": "fine_tune",
        "provider": "simulator",
        "current_config": {
            "gpu_type": "L4",
            "gpu_count": 1,
            "batch_size": 32,
            "precision": "fp16",
            "checkpointing": True,
        },
        "constraints": {"budget_usd": 2.0, "max_runtime_hours": 4.0},
    }
    created = client.post("/api/workloads", headers=auth_headers, json=payload)
    assert created.status_code == 201
    assert created.json()["name"] == payload["name"]
    duplicate = client.post("/api/workloads", headers=auth_headers, json=payload)
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "name_conflict"


def test_invalid_workload_is_rejected(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.post(
        "/api/workloads",
        headers=auth_headers,
        json={
            "name": "Bad workload",
            "description": "",
            "workload_type": "fine_tune",
            "provider": "simulator",
            "current_config": {
                "gpu_type": "V100",
                "gpu_count": 1,
                "batch_size": 32,
                "precision": "fp16",
                "checkpointing": True,
            },
            "constraints": {},
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_config"


def test_create_and_read_optimization(client: TestClient, auth_headers: dict[str, str]) -> None:
    workload = _workloads(client, auth_headers)[0]
    created = client.post(
        "/api/optimizations",
        headers=auth_headers,
        json={"workload_id": workload["id"], "objective": "balanced"},
    )
    assert created.status_code == 201
    proposal = created.json()
    assert proposal["status"] == "proposed"
    assert len(proposal["candidates"]) == 24
    assert proposal["selected_candidate_id"]
    assert proposal["analysis"]["source"] == "deterministic_fallback"
    assert proposal["normalization"] == "min_max_across_eligible_candidates"

    read = client.get(f"/api/optimizations/{proposal['id']}", headers=auth_headers)
    assert read.status_code == 200
    assert read.json()["id"] == proposal["id"]
    listing = client.get("/api/optimizations", headers=auth_headers)
    assert listing.status_code == 200
    assert listing.json()["total"] == 1


def test_workflow_start_records_approval_then_signals(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    workload = _workloads(client, auth_headers)[0]
    proposal = client.post(
        "/api/optimizations",
        headers=auth_headers,
        json={"workload_id": workload["id"]},
    ).json()

    start = client.post(
        "/api/workflows",
        headers=auth_headers,
        json={"proposal_id": proposal["id"]},
    )
    assert start.status_code == 202
    workflow_id = start.json()["workflow_id"]
    assert workflow_id == f"optimization-{proposal['id']}"
    assert start.json()["stage"] == "created"

    gateway = client.app.state.temporal
    assert gateway.started == [(proposal["id"], 900)]

    duplicate = client.post(
        "/api/workflows",
        headers=auth_headers,
        json={"proposal_id": proposal["id"]},
    )
    assert duplicate.status_code == 202
    assert len(gateway.started) == 1

    with session_scope() as session:
        row = session.get(OptimizationProposal, proposal["id"])
        assert row is not None
        row.status = "awaiting_approval"
        session.commit()

    approved = client.post(
        f"/api/optimizations/{proposal['id']}/approve",
        headers=auth_headers,
        json={"reason": "Approved in test"},
    )
    assert approved.status_code == 200
    approval = approved.json()
    assert approval["decision"] == "approved"
    assert gateway.approvals == [(workflow_id, approval["id"])]

    with session_scope() as session:
        stored = session.scalar(select(Approval).where(Approval.proposal_id == proposal["id"]))
        assert stored is not None and stored.reason == "Approved in test"
        ref = session.scalar(select(WorkflowRef).where(WorkflowRef.workflow_id == workflow_id))
        assert ref is not None

    conflict = client.post(
        f"/api/optimizations/{proposal['id']}/reject",
        headers=auth_headers,
        json={"reason": "changed my mind"},
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "decision_conflict"


def test_rejection_requires_started_workflow(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    workload = _workloads(client, auth_headers)[0]
    proposal = client.post(
        "/api/optimizations",
        headers=auth_headers,
        json={"workload_id": workload["id"]},
    ).json()
    response = client.post(
        f"/api/optimizations/{proposal['id']}/reject",
        headers=auth_headers,
        json={"reason": "too risky"},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "workflow_not_started"


def test_kill_switch_round_trip_is_audited(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    enabled = client.patch(
        "/api/settings", headers=auth_headers, json={"kill_switch": True}
    )
    assert enabled.status_code == 200
    assert enabled.json()["kill_switch_active"] is True
    assert enabled.json()["kill_switch_source"] == "api"

    disabled = client.patch(
        "/api/settings", headers=auth_headers, json={"kill_switch": False}
    )
    assert disabled.status_code == 200
    assert disabled.json()["kill_switch_active"] is False
    assert disabled.json()["kill_switch_source"] == "off"

    audit = client.get(
        "/api/audit", headers=auth_headers, params={"event_type": "kill_switch.changed"}
    )
    assert audit.status_code == 200
    assert audit.json()["total"] == 2


def test_pagination_metadata(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/api/workloads?limit=1&offset=1", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 1
    assert body["total"] == 2
    assert body["limit"] == 1
    assert body["offset"] == 1
