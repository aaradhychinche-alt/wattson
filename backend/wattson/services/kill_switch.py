"""Global kill switch shared by API and workers through the audit ledger."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import AuditEvent
from .audit import record_audit


def effective_kill_switch(session: Session) -> tuple[bool, str]:
    """Environment wins; otherwise the latest API toggle in the shared DB wins."""
    if get_settings().wattson_kill_switch:
        return True, "environment"
    latest = session.scalar(
        select(AuditEvent)
        .where(AuditEvent.event_type == "kill_switch.changed")
        .order_by(AuditEvent.id.desc())
        .limit(1)
    )
    if latest and bool(latest.payload.get("enabled")):
        return True, "api"
    return False, "off"


def require_kill_switch_off(session: Session) -> None:
    from ..providers.base import KillSwitchActive

    active, source = effective_kill_switch(session)
    if active:
        raise KillSwitchActive(f"kill switch is active ({source}); new infrastructure blocked")


def set_kill_switch(session: Session, enabled: bool, actor: str = "api-token") -> tuple[bool, str]:
    record_audit(
        session,
        event_key="kill_switch.changed",
        event_type="kill_switch.changed",
        message=f"kill switch {'enabled' if enabled else 'disabled'} via API",
        actor=actor,
        payload={"enabled": enabled},
        dedupe=False,
    )
    session.commit()
    return effective_kill_switch(session)
