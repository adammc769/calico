"""Database utilities for workflow persistence."""
from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Iterator

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from .config import get_settings

Base = declarative_base()


def utcnow() -> datetime:
    """Return the current UTC time as a timezone-aware datetime."""

    return datetime.now(UTC)


class ScrapeRun(Base):
    """Persisted record describing a DOM unit collection run."""

    __tablename__ = "scrape_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    url = Column(String(512), nullable=False)
    status = Column(String(32), nullable=False, default="pending")
    unit_count = Column(Integer, nullable=False, default=0)
    payload = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "url": self.url,
            "status": self.status,
            "unit_count": self.unit_count,
            "payload": json.loads(self.payload) if self.payload else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class AgentRun(Base):
    """Persisted record for an AI agent session."""

    __tablename__ = "agent_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    goal = Column(String(512), nullable=False)
    agent_name = Column(String(128), nullable=False)
    status = Column(String(32), nullable=False, default="pending")
    session_id = Column(String(64), nullable=True)
    parent_run_id = Column(Integer, ForeignKey("scrape_runs.id", ondelete="SET NULL"), nullable=True)
    result_payload = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "goal": self.goal,
            "agent_name": self.agent_name,
            "status": self.status,
            "session_id": self.session_id,
            "parent_run_id": self.parent_run_id,
            "result_payload": json.loads(self.result_payload) if self.result_payload else None,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
        }


class AgentEvent(Base):
    """Detailed event emitted during an agent session."""

    __tablename__ = "agent_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(Integer, ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False)
    step = Column(Integer, nullable=False)
    phase = Column(String(32), nullable=False, default="action")
    success = Column(Boolean, nullable=False, default=False)
    message = Column(Text, nullable=True)
    data = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "run_id": self.run_id,
            "step": self.step,
            "phase": self.phase,
            "success": self.success,
            "message": self.message,
            "data": json.loads(self.data) if self.data else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


_engine: Engine | None = None
_SessionLocal: sessionmaker | None = None


def get_engine() -> Engine:
    """Construct (or return cached) SQLAlchemy engine."""

    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_engine(settings.resolved_database_url(), pool_pre_ping=True)
    return _engine


def get_session_factory() -> sessionmaker:
    """Return a session factory bound to the configured engine."""

    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), expire_on_commit=False)
    return _SessionLocal


@contextmanager
def get_session() -> Iterator[Session]:
    """Provide a transactional scope around a series of operations."""

    session_factory = get_session_factory()
    session: Session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db() -> None:
    """Create database tables if they do not already exist."""

    engine = get_engine()
    Base.metadata.create_all(bind=engine)
