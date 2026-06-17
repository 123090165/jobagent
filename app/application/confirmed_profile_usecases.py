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
from app.repositories.profile_session_repository import (
    ProfileSessionRepository,
    profile_session_repository,
)
from app.schemas.confirmed_profile import ConfirmedProfileResponse
from app.services.errors import JobAgentError


def confirm_profile_draft(
    draft_id: str,
    *,
    session_repository: ProfileSessionRepository = profile_session_repository,
    draft_repository: ProfileDraftRepository = profile_draft_repository,
    confirmed_repository: ConfirmedProfileRepository = confirmed_profile_repository,
) -> ConfirmedProfileResponse:
    profile_draft = draft_repository.get(draft_id)
    if profile_draft is None:
        raise JobAgentError(
            message="Profile draft not found.",
            error_code="profile_draft_not_found",
            status_code=404,
        )

    session = get_profile_session(profile_draft.session_id, repository=session_repository)
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
        existing = confirmed_repository.get(session.confirmed_profile_id)
        if existing is not None and existing.profile_draft_id == profile_draft.profile_draft_id:
            return ConfirmedProfileResponse(
                confirmed_profile=existing,
                profile_session=session,
            )

    existing_for_draft = confirmed_repository.get_current_for_session(
        session_id=session.session_id,
        profile_draft_id=profile_draft.profile_draft_id,
    )
    if existing_for_draft is not None:
        updated_session = session_repository.attach_confirmed_profile(
            session_id=session.session_id,
            confirmed_profile_id=existing_for_draft.confirmed_profile_id,
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
    )
    updated_session = session_repository.attach_confirmed_profile(
        session_id=session.session_id,
        confirmed_profile_id=confirmed_profile.confirmed_profile_id,
    )
    return ConfirmedProfileResponse(
        confirmed_profile=confirmed_profile,
        profile_session=updated_session or session,
    )


def get_confirmed_profile(
    confirmed_profile_id: str,
    *,
    session_repository: ProfileSessionRepository = profile_session_repository,
    confirmed_repository: ConfirmedProfileRepository = confirmed_profile_repository,
) -> ConfirmedProfileResponse:
    confirmed_profile = confirmed_repository.get(confirmed_profile_id)
    if confirmed_profile is None:
        raise JobAgentError(
            message="Confirmed profile not found.",
            error_code="confirmed_profile_not_found",
            status_code=404,
        )
    session = get_profile_session(confirmed_profile.session_id, repository=session_repository)
    return ConfirmedProfileResponse(
        confirmed_profile=confirmed_profile,
        profile_session=session,
    )
