from __future__ import annotations

from app.repositories.browser_job_capture_repository import (
    BrowserJobCaptureRepository,
    browser_job_capture_repository,
)
from app.repositories.communication_draft_repository import (
    CommunicationDraftRepository,
    communication_draft_repository,
)
from app.repositories.job_application_repository import (
    JobApplicationRepository,
    job_application_repository,
)
from app.repositories.resume_profile_repository import (
    ResumeProfileRepository,
    resume_profile_repository,
)
from app.repositories.saved_job_repository import SavedJobRepository, saved_job_repository
from app.schemas.communication import (
    CommunicationDraft,
    CommunicationDraftGenerateRequest,
    CommunicationDraftUpdateRequest,
    CommunicationSentConfirmation,
    CommunicationSentResult,
)
from app.services.errors import JobAgentError
from app.services.greeting_generator import GreetingGenerationFailure, generate_initial_greeting
from app.services.llm_provider import resolve_llm_provider
from app.storage.database import get_connection, init_database


def generate_browser_greeting_draft(
    capture_id: str,
    payload: CommunicationDraftGenerateRequest,
    *,
    user_id: str,
    captures: BrowserJobCaptureRepository = browser_job_capture_repository,
    profiles: ResumeProfileRepository = resume_profile_repository,
    drafts: CommunicationDraftRepository = communication_draft_repository,
) -> CommunicationDraft:
    capture = captures.get(user_id=user_id, capture_id=capture_id)
    if capture is None:
        raise _not_found("Browser job capture", "browser_job_capture_not_found")
    profile = _resolve_profile(
        user_id=user_id,
        requested_id=payload.resume_profile_id,
        profiles=profiles,
    )
    resolution = resolve_llm_provider(payload.llm_provider)
    if not resolution.configured or resolution.service is None:
        raise JobAgentError(
            message="A configured LLM provider is required to generate a greeting.",
            error_code="llm_unavailable",
            status_code=503,
        )
    try:
        generated = generate_initial_greeting(
            capture,
            profile,
            llm_service=resolution.service,
        )
    except GreetingGenerationFailure as exc:
        raise JobAgentError(
            message=exc.message,
            error_code=exc.code,
            status_code=422 if exc.code == "generation_validation_failed" else 502,
        ) from exc
    return drafts.create(
        user_id=user_id,
        saved_job_id=capture.saved_job_id,
        browser_capture_id=capture_id,
        generated_content=generated.content,
        evidence_used=generated.evidence_used,
        avoid_claims=generated.avoid_claims,
        generation_context={
            "resume_profile_id": profile.resume_profile_id,
            "capture_id": capture_id,
            "saved_job_id": capture.saved_job_id,
            "job_title": capture.title,
            "company": capture.company,
        },
        analysis_provider=resolution.provider,
    )


def update_communication_draft(
    draft_id: str,
    payload: CommunicationDraftUpdateRequest,
    *,
    user_id: str,
    drafts: CommunicationDraftRepository = communication_draft_repository,
) -> CommunicationDraft:
    existing = drafts.get(user_id=user_id, draft_id=draft_id)
    if existing is None:
        raise _not_found("Communication draft", "communication_draft_not_found")
    if existing.status in {"sent", "failed", "dismissed"}:
        raise JobAgentError(
            message="This communication draft can no longer be edited.",
            error_code="communication_draft_finalized",
            status_code=409,
        )
    updated = drafts.update_review(
        user_id=user_id,
        draft_id=draft_id,
        approved_content=payload.approved_content,
        status=payload.status,
    )
    if updated is None:
        raise _not_found("Communication draft", "communication_draft_not_found")
    return updated


def confirm_greeting_sent(
    draft_id: str,
    payload: CommunicationSentConfirmation,
    *,
    user_id: str,
    captures: BrowserJobCaptureRepository = browser_job_capture_repository,
    drafts: CommunicationDraftRepository = communication_draft_repository,
    saved_jobs: SavedJobRepository = saved_job_repository,
    applications: JobApplicationRepository = job_application_repository,
) -> CommunicationSentResult:
    draft = drafts.get(user_id=user_id, draft_id=draft_id)
    if draft is None:
        raise _not_found("Communication draft", "communication_draft_not_found")
    if draft.status == "sent":
        if draft.application_id is None:
            raise RuntimeError("Sent communication draft has no application.")
        application = applications.get(user_id=user_id, application_id=draft.application_id)
        if application is None:
            raise RuntimeError("Sent communication draft application is missing.")
        return CommunicationSentResult(
            draft=draft,
            saved_job_id=application.saved_job_id,
            application_id=application.application_id,
        )
    if draft.status != "approved":
        raise JobAgentError(
            message="Approve the final greeting before confirming it as sent.",
            error_code="communication_draft_not_approved",
            status_code=409,
        )
    if draft.browser_capture_id is None:
        raise JobAgentError(
            message="The communication draft is not linked to a captured job.",
            error_code="communication_capture_missing",
            status_code=409,
        )
    capture = captures.get(user_id=user_id, capture_id=draft.browser_capture_id)
    if capture is None:
        raise _not_found("Browser job capture", "browser_job_capture_not_found")
    if capture.saved_job_id != draft.saved_job_id:
        raise JobAgentError(
            message="Communication draft and browser capture refer to different jobs.",
            error_code="communication_job_mismatch",
            status_code=409,
        )

    # 发送确认只推进申请状态；岗位主记录在抓取时已经建立，避免再次复制岗位数据。
    with get_connection() as connection:
        init_database(connection)
        job = saved_jobs.get(user_id=user_id, saved_job_id=draft.saved_job_id)
        if job is None:
            raise _not_found("Saved job", "saved_job_not_found")
        application = applications.create_for_job(
            user_id=user_id,
            saved_job_id=draft.saved_job_id,
            source="browser_helper",
            connection=connection,
        )
        if application.stage not in {"not_started", "contacted"}:
            raise JobAgentError(
                message="This application has already progressed beyond initial contact.",
                error_code="initial_greeting_duplicate",
                status_code=409,
            )
        application = applications.update_tracking(
            user_id=user_id,
            application_id=application.application_id,
            stage="contacted",
            next_action="wait_for_reply",
            detail="Initial greeting sent through Browser Helper.",
            source="browser_helper",
            connection=connection,
        )
        if application is None:
            raise RuntimeError("Application disappeared during send confirmation.")
        sent_draft = drafts.mark_sent(
            connection=connection,
            user_id=user_id,
            draft_id=draft_id,
            application_id=application.application_id,
            sent_content=payload.sent_content,
            sent_at=payload.sent_at,
        )
        applications.add_event(
            application_id=application.application_id,
            user_id=user_id,
            event_type="greeting_sent",
            source="browser_helper",
            detail="Initial greeting was verified as sent.",
            metadata={"draft_id": draft_id},
            connection=connection,
        )
        connection.commit()
    return CommunicationSentResult(
        draft=sent_draft,
        saved_job_id=draft.saved_job_id,
        application_id=application.application_id,
    )


def _resolve_profile(
    *,
    user_id: str,
    requested_id: str | None,
    profiles: ResumeProfileRepository,
):
    if requested_id is not None:
        profile = profiles.get(user_id=user_id, resume_profile_id=requested_id)
        if profile is None or profile.archived_at is not None:
            raise _not_found("Resume profile", "resume_profile_not_found")
        return profile
    available = profiles.list_by_user(user_id)
    profile = next((item for item in available if item.is_default), available[0] if available else None)
    if profile is None:
        raise JobAgentError(
            message="Create a confirmed resume profile before generating a greeting.",
            error_code="resume_profile_required",
            status_code=409,
        )
    return profile


def _not_found(resource: str, error_code: str) -> JobAgentError:
    return JobAgentError(
        message=f"{resource} not found.",
        error_code=error_code,
        status_code=404,
    )
