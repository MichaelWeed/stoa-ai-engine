"""SQLite database — token ledger and idempotency cache."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

from sqlalchemy import Column, DateTime, Float, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from stoa.config import get_config


class Base(DeclarativeBase):
    pass


class TaskRecord(Base):
    __tablename__ = "tasks"

    id = Column(String, primary_key=True)
    workflow = Column(String, nullable=False)
    status = Column(String, nullable=False, default="pending")
    steps_executed = Column(Integer, default=0)
    tokens_used = Column(Integer, default=0)
    cost_usd = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    error = Column(Text, nullable=True)
    fsm_trace = Column(Text, nullable=True)  # JSON


class IdempotencyRecord(Base):
    __tablename__ = "idempotency"

    key = Column(String, primary_key=True)
    result = Column(Text, nullable=True)  # JSON
    created_at = Column(DateTime, default=datetime.utcnow)


def _get_engine():
    cfg = get_config()
    # aiosqlite URL → sync URL for simplicity in the ledger layer
    url = cfg.db_url.replace("+aiosqlite", "")
    engine = create_engine(url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    return engine


def get_session() -> Session:
    engine = _get_engine()
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


def idempotency_key(workflow: str, inputs: dict[str, Any]) -> str:
    payload = json.dumps({"workflow": workflow, "inputs": inputs}, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def check_idempotency(key: str) -> Any | None:
    """Return cached result if this exact task was already completed."""
    with get_session() as session:
        rec = session.get(IdempotencyRecord, key)
        if rec and rec.result:
            return json.loads(rec.result)
    return None


def record_idempotency(key: str, result: Any) -> None:
    with get_session() as session:
        rec = IdempotencyRecord(key=key, result=json.dumps(result))
        session.merge(rec)
        session.commit()
