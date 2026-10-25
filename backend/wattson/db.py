"""Database engine, session factory, and UTC helpers."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from .config import get_settings

_engine: Engine | None = None
_SessionFactory: sessionmaker[Session] | None = None


def utcnow() -> datetime:
    return datetime.now(UTC)


def as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _prepare_sqlite(url: str) -> None:
    if url.startswith("sqlite:///") and ":memory:" not in url:
        raw = url.removeprefix("sqlite:///")
        path = Path(raw)
        if not path.is_absolute():
            path = Path.cwd() / path
        path.parent.mkdir(parents=True, exist_ok=True)


def make_engine(url: str) -> Engine:
    _prepare_sqlite(url)
    kwargs: dict[str, Any] = {"pool_pre_ping": True, "future": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False, "timeout": 30}
    eng = create_engine(url, **kwargs)
    if url.startswith("sqlite"):

        @event.listens_for(eng, "connect")
        def _sqlite_pragmas(dbapi_connection: Any, _record: Any) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=30000")
            cursor.close()

    return eng


def configure_database(url: str | None = None) -> Engine:
    global _engine, _SessionFactory
    if _engine is not None:
        _engine.dispose()
    _engine = make_engine(url or get_settings().wattson_database_url)
    _SessionFactory = sessionmaker(bind=_engine, expire_on_commit=False, autoflush=False)
    return _engine


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        configure_database()
    assert _engine is not None
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    global _SessionFactory
    if _SessionFactory is None:
        configure_database()
    assert _SessionFactory is not None
    return _SessionFactory


def session_scope() -> Session:
    """Return a new Session. Caller owns commit/rollback/close."""
    return get_session_factory()()


def get_db() -> Iterator[Session]:
    session = session_scope()
    try:
        yield session
    finally:
        session.close()
