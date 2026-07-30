"""编排 可复用简历画像 的所有权检查、状态转换、领域服务和持久化操作。"""

from __future__ import annotations

from app.repositories.resume_profile_repository import (
    ResumeProfileRepository,
    resume_profile_repository,
)
from app.schemas.resume_profile import ResumeProfile, ResumeProfileUpdateRequest
from app.services.errors import JobAgentError


def list_resume_profiles(
    *,
    user_id: str,
    include_archived: bool = False,
    repository: ResumeProfileRepository = resume_profile_repository,
) -> list[ResumeProfile]:
    return repository.list_by_user(user_id, include_archived=include_archived)


def get_resume_profile(
    resume_profile_id: str,
    *,
    user_id: str,
    repository: ResumeProfileRepository = resume_profile_repository,
) -> ResumeProfile:
    profile = repository.get(user_id=user_id, resume_profile_id=resume_profile_id)
    if profile is None:
        raise _not_found()
    return profile


def update_resume_profile(
    resume_profile_id: str,
    payload: ResumeProfileUpdateRequest,
    *,
    user_id: str,
    repository: ResumeProfileRepository = resume_profile_repository,
) -> ResumeProfile:
    profile = repository.update(
        user_id=user_id,
        resume_profile_id=resume_profile_id,
        payload=payload,
    )
    if profile is None:
        raise _not_found()
    return profile


def set_default_resume_profile(
    resume_profile_id: str,
    *,
    user_id: str,
    repository: ResumeProfileRepository = resume_profile_repository,
) -> ResumeProfile:
    profile = repository.set_default(user_id=user_id, resume_profile_id=resume_profile_id)
    if profile is None:
        raise _not_found()
    return profile


def archive_resume_profile(
    resume_profile_id: str,
    *,
    user_id: str,
    repository: ResumeProfileRepository = resume_profile_repository,
) -> ResumeProfile:
    profile = repository.archive(user_id=user_id, resume_profile_id=resume_profile_id)
    if profile is None:
        raise _not_found()
    return profile


def restore_resume_profile(
    resume_profile_id: str,
    *,
    user_id: str,
    repository: ResumeProfileRepository = resume_profile_repository,
) -> ResumeProfile:
    profile = repository.restore(user_id=user_id, resume_profile_id=resume_profile_id)
    if profile is None:
        raise _not_found()
    return profile


def delete_resume_profile(
    resume_profile_id: str,
    *,
    user_id: str,
    repository: ResumeProfileRepository = resume_profile_repository,
) -> None:
    if not repository.delete(user_id=user_id, resume_profile_id=resume_profile_id):
        raise _not_found()


def _not_found() -> JobAgentError:
    return JobAgentError(
        message="Resume profile not found.",
        error_code="resume_profile_not_found",
        status_code=404,
    )
