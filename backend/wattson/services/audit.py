"""Audit log with idempotent event keys."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models import AuditEvent


def record_audit(
    session: Session,
    *,
    event_key: str,
    event_type: str,
    message: str = "",
    actor: str = "system",
    proposal_id: str | None = None,
    workflow_id: str | None = None,
    payload: dict[str, Any] | None = None,
    dedupe: bool = True,
) -> bool:
    """Insert an audit event. Returns True if inserted, False if already present.

    Uses a SAVEPOINT so a duplicate key never poisons the caller's transaction.
    """
    key = event_key if dedupe else f"{event_key}:{uuid.uuid4().hex[:12]}"
    event = AuditEvent(
        event_key=key,
        event_type=event_type,
        actor=actor,
        proposal_id=proposal_id,
        workflow_id=workflow_id,
        message=message,
        payload=payload or {},
    )
    try:
        with session.begin_nested():
            session.add(event)
            session.flush()
        return True
    except IntegrityError:
        return False


def list_audit(
    session: Session,
    *,
    limit: int = 50,
    offset: int = 0,
    event_type: str | None = None,
    proposal_id: str | None = None,
) -> tuple[list[AuditEvent], int]:
    from sqlalchemy import func

    stmt = select(AuditEvent)
    count_stmt = select(func.count(AuditEvent.id))
    if event_type:
        stmt = stmt.where(AuditEvent.event_type == event_type)
        count_stmt = count_stmt.where(AuditEvent.event_type == event_type)
    if proposal_id:
        stmt = stmt.where(AuditEvent.proposal_id == proposal_id)
        count_stmt = count_stmt.where(AuditEvent.proposal_id == proposal_id)
    stmt = stmt.order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
    total = session.scalar(count_stmt) or 0
    return list(session.scalars(stmt.limit(limit).offset(offset))), total
