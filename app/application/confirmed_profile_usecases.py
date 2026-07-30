"""编排 确认画像 的所有权检查、状态转换、领域服务和持久化操作。"""

from __future__ import annotations

from app.application.profile_session_usecases import get_profile_session
from app.repositories.confirmed_profile_repository import (
    ConfirmedProfileRepository,
    confirmed_profile_repository,
)
from app.repositories.profile_draft_repository import (
    ProfileDraftRepository,
    profile_draft_repository,
)
from app.repositories.resume_document_repository import (
    ResumeDocumentRepository,
    resume_document_repository,
)
from app.repositories.resume_profile_repository import (
    ResumeProfileRepository,
    resume_profile_repository,
)
from app.repositories.profile_session_repository import (
    ProfileSessionRepository,
    profile_session_repository,
)
from app.schemas.confirmed_profile import ConfirmedProfile
from app.schemas.confirmed_profile import ConfirmedProfileResponse
from app.services.errors import JobAgentError
from app.storage.database import LOCAL_USER_ID


def confirm_profile_draft(
    draft_id: str,
    *,
    user_id: str | None = None,
    session_repository: ProfileSessionRepository = profile_session_repository,
    draft_repository: ProfileDraftRepository = profile_draft_repository,
    confirmed_repository: ConfirmedProfileRepository = confirmed_profile_repository,
    resume_repository: ResumeDocumentRepository = resume_document_repository,
    resume_profile_repository: ResumeProfileRepository = resume_profile_repository,
) -> ConfirmedProfileResponse:
    """确认草稿、推进 session，并同步一份可脱离页面会话复用的 ResumeProfile。"""
    profile_draft = draft_repository.get(draft_id, user_id=user_id)
    if profile_draft is None:
        raise JobAgentError(
            message="Profile draft not found.",
            error_code="profile_draft_not_found",
            status_code=404,
        )

    session = get_profile_session(
        profile_draft.session_id,
        repository=session_repository,
        user_id=user_id,
    )
    if session.profile_draft_id != profile_draft.profile_draft_id:
        raise JobAgentError(
            message="Profile draft is not current for this session.",
            error_code="invalid_profile_session_state",
            status_code=409,
        )
    if session.resume_document_id is None or session.parsed_review_id is None:
        raise JobAgentError(
            message="Confirmed profile requires the current resume and parsed review.",
            error_code="invalid_profile_session_state",
            status_code=409,
        )

    if session.confirmed_profile_id:
        existing = confirmed_repository.get(session.confirmed_profile_id, user_id=user_id)
        if existing is not None and existing.profile_draft_id == profile_draft.profile_draft_id:
            _sync_resume_profile(
                existing,
                user_id=user_id or LOCAL_USER_ID,
                resume_repository=resume_repository,
                resume_profile_repository=resume_profile_repository,
            )
            return ConfirmedProfileResponse(
                confirmed_profile=existing,
                profile_session=session,
            )

    existing_for_draft = confirmed_repository.get_current_for_session(
        session_id=session.session_id,
        profile_draft_id=profile_draft.profile_draft_id,
        user_id=user_id,
    )
    if existing_for_draft is not None:
        updated_session = session_repository.attach_confirmed_profile(
            session_id=session.session_id,
            confirmed_profile_id=existing_for_draft.confirmed_profile_id,
        )
        _sync_resume_profile(
            existing_for_draft,
            user_id=user_id or LOCAL_USER_ID,
            resume_repository=resume_repository,
            resume_profile_repository=resume_profile_repository,
        )
        return ConfirmedProfileResponse(
            confirmed_profile=existing_for_draft,
            profile_session=updated_session or session,
        )

    confirmed_profile = confirmed_repository.create_from_draft(
        session_id=session.session_id,
        resume_document_id=session.resume_document_id,
        parsed_review_id=session.parsed_review_id,
        profile_draft=profile_draft,
        user_id=user_id or LOCAL_USER_ID,
    )
    updated_session = session_repository.attach_confirmed_profile(
        session_id=session.session_id,
        confirmed_profile_id=confirmed_profile.confirmed_profile_id,
    )
    _sync_resume_profile(
        confirmed_profile,
        user_id=user_id or LOCAL_USER_ID,
        resume_repository=resume_repository,
        resume_profile_repository=resume_profile_repository,
    )
    return ConfirmedProfileResponse(
        confirmed_profile=confirmed_profile,
        profile_session=updated_session or session,
    )


def get_confirmed_profile(
    confirmed_profile_id: str,
    *,
    user_id: str | None = None,
    session_repository: ProfileSessionRepository = profile_session_repository,
    confirmed_repository: ConfirmedProfileRepository = confirmed_profile_repository,
) -> ConfirmedProfileResponse:
    """读取当前确认画像；历史确认记录不能冒充当前流程输入。"""
    confirmed_profile = confirmed_repository.get(confirmed_profile_id, user_id=user_id)
    if confirmed_profile is None:
        raise JobAgentError(
            message="Confirmed profile not found.",
            error_code="confirmed_profile_not_found",
            status_code=404,
        )
    session = get_profile_session(
        confirmed_profile.session_id,
        repository=session_repository,
        user_id=user_id,
    )
    return ConfirmedProfileResponse(
        confirmed_profile=confirmed_profile,
        profile_session=session,
    )


def _sync_resume_profile(
    confirmed_profile: ConfirmedProfile,
    *,
    user_id: str,
    resume_repository: ResumeDocumentRepository,
    resume_profile_repository: ResumeProfileRepository,
) -> None:
    resume_document = resume_repository.get(
        confirmed_profile.resume_document_id,
        user_id=user_id,
    )
    resume_profile_repository.create_or_update_from_confirmed(
        user_id=user_id,
        confirmed_profile=confirmed_profile,
        raw_resume_text=resume_document.text if resume_document is not None else None,
    )
