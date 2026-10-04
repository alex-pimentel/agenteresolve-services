"""Ephemeral in-memory sessions for RAG/DataChat/VoiceChat.

Sessions live only in worker memory with a TTL and are never written to Postgres. A worker
restart drops them, which the specs explicitly accept.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any

DEFAULT_TTL_SECONDS = 24 * 60 * 60


@dataclass
class Session:
    session_id: str
    kind: str
    created_at: float
    data: dict[str, Any] = field(default_factory=dict)


class SessionStore:
    def __init__(self, ttl: int = DEFAULT_TTL_SECONDS) -> None:
        self.ttl = ttl
        self._sessions: dict[str, Session] = {}
        self._lock = threading.Lock()

    def create(self, session_id: str, kind: str, **data: Any) -> Session:
        with self._lock:
            session = Session(
                session_id=session_id, kind=kind, created_at=time.time(), data=dict(data)
            )
            self._sessions[session_id] = session
            return session

    def get(self, session_id: str) -> Session | None:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return None
            if time.time() - session.created_at > self.ttl:
                del self._sessions[session_id]
                return None
            return session

    def delete(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)

    def clear(self) -> None:
        with self._lock:
            self._sessions.clear()


_store = SessionStore()


def get_session_store() -> SessionStore:
    return _store


def set_session_store(store: SessionStore) -> None:
    global _store
    _store = store
