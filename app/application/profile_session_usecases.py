"""编排 简历到搜索的流程会话 的所有权检查、状态转换、领域服务和持久化操作。"""

from __future__ import annotations

from app.repositories.profile_session_repository import (
    ProfileSessionRepository,
    profile_session_repository,
)
from app.schemas.profile_session import ProfileSession
from app.services.errors import JobAgentError


def create_profile_session(
    repository: ProfileSessionRepository = profile_session_repository,
    *,
    user_id: str | None = None,
) -> ProfileSession:
    return repository.create(user_id=user_id) if user_id is not None else repository.create()


def get_profile_session(
    session_id: str,
    repository: ProfileSessionRepository = profile_session_repository,
    *,
    user_id: str | None = None,
) -> ProfileSession:
    session = repository.get(session_id, user_id=user_id)
    if session is None:
        raise JobAgentError(
            message="Profile session not found.",
            error_code="profile_session_not_found",
            status_code=404,
        )
    return session
