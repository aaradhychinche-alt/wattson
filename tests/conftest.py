"""Shared test configuration. Every test uses a throwaway SQLite database."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

# Configure the application before importing modules that cache settings.
os.environ["WATTSON_API_TOKEN"] = "test-token"
os.environ["WATTSON_AI_PROVIDER"] = "none"
os.environ["WATTSON_PROVIDER"] = "simulator"
os.environ["WATTSON_KILL_SWITCH"] = "false"
os.environ["WATTSON_TEMPORAL_HOST"] = "127.0.0.1:1"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from wattson.config import reset_settings_cache
from wattson.db import configure_database, session_scope
from wattson.models import Base
from wattson.services.demo_seed import seed_demo_workloads


def _sqlite_url(tmp_path: Path) -> str:
    return f"sqlite:///{(tmp_path / 'wattson-test.db').as_posix()}"


@pytest.fixture()
def database(tmp_path: Path) -> Iterator[Engine]:
    reset_settings_cache()
    engine = configure_database(_sqlite_url(tmp_path))
    Base.metadata.create_all(engine)
    with session_scope() as session:
        seed_demo_workloads(session)
    yield engine
    engine.dispose()
    reset_settings_cache()


@pytest.fixture()
def session(database: Engine) -> Iterator[Session]:
    with session_scope() as db_session:
        yield db_session


class FakeTemporal:
    """In-process stand-in for the Temporal gateway used by API tests."""

    def __init__(self) -> None:
        self.client = object()
        self.started: list[tuple[str, int]] = []
        self.approvals: list[tuple[str, str]] = []
        self.rejections: list[tuple[str, str, str]] = []
        self.cancellations: list[tuple[str, str]] = []
        self.status: dict[str, object] | None = {"stage": "awaiting_approval"}

    async def health(self) -> bool:
        return True

    async def start_optimization(self, proposal_id: str, approval_timeout_seconds: int) -> str:
        self.started.append((proposal_id, approval_timeout_seconds))
        return f"optimization-{proposal_id}"

    async def query_status(self, workflow_id: str) -> dict[str, object] | None:
        return self.status

    async def approve(self, workflow_id: str, approval_id: str) -> None:
        self.approvals.append((workflow_id, approval_id))

    async def reject(self, workflow_id: str, approval_id: str, reason: str) -> None:
        self.rejections.append((workflow_id, approval_id, reason))

    async def cancel(self, workflow_id: str, reason: str) -> None:
        self.cancellations.append((workflow_id, reason))


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("WATTSON_DATABASE_URL", _sqlite_url(tmp_path))
    monkeypatch.setenv("WATTSON_API_TOKEN", "test-token")
    monkeypatch.setenv("WATTSON_AI_PROVIDER", "none")
    monkeypatch.setenv("WATTSON_TEMPORAL_HOST", "127.0.0.1:1")
    reset_settings_cache()

    # Avoid a real network attempt during the application lifespan.
    async def _fail_connect(self: object) -> None:
        raise RuntimeError("Temporal disabled in tests")

    monkeypatch.setattr("wattson.api.app.TemporalGateway.connect", _fail_connect)

    from wattson.api.app import app

    with TestClient(app) as test_client:
        with session_scope() as session:
            seed_demo_workloads(session)
        app.state.temporal = FakeTemporal()
        test_client.app_state = app.state  # type: ignore[attr-defined]
        yield test_client

    reset_settings_cache()


@pytest.fixture()
def auth_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-token"}
