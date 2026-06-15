from __future__ import annotations

from app.repositories.profile_session_repository import (
    InMemoryProfileSessionRepository,
    profile_session_repository,
)
from app.schemas.profile_session import ProfileSession
from app.services.errors import JobAgentError


def create_profile_session(
    repository: InMemoryProfileSessionRepository = profile_session_repository,
) -> ProfileSession:
    return repository.create()


def get_profile_session(
    session_id: str,
    repository: InMemoryProfileSessionRepository = profile_session_repository,
) -> ProfileSession:
    session = repository.get(session_id)
    if session is None:
        raise JobAgentError(
            message="Profile session not found.",
            error_code="profile_session_not_found",
            status_code=404,
        )
    return session
