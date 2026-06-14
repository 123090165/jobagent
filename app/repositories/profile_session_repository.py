from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from app.schemas.profile_session import (
    ProfileSession,
    ProfileSessionStatus,
    ProfileSessionStep,
)


class InMemoryProfileSessionRepository:
    """Temporary repository for the v4 API contract skeleton."""

    def __init__(self) -> None:
        self._sessions: dict[str, ProfileSession] = {}

    def create(self) -> ProfileSession:
        now = datetime.now(timezone.utc)
        session = ProfileSession(
            session_id=str(uuid4()),
            status=ProfileSessionStatus.active,
            created_at=now,
            updated_at=now,
            current_step=ProfileSessionStep.resume_intake,
        )
        self._sessions[session.session_id] = session
        return session

    def get(self, session_id: str) -> ProfileSession | None:
        return self._sessions.get(session_id)


profile_session_repository = InMemoryProfileSessionRepository()
