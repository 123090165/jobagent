from __future__ import annotations

from app.application.application_tracking_usecases import DEFAULT_NEXT_ACTION
from app.repositories.browser_job_capture_repository import (
    BrowserJobCaptureRepository,
    browser_job_capture_repository,
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
from app.repositories.tailored_resume_repository import (
    TailoredResumeRepository,
    tailored_resume_repository,
)
from app.schemas.tailored_resume import (
    TailoredResumeGenerateRequest,
    TailoredResumeUpdateRequest,
    TailoredResumeVersion,
)
from app.schemas.resume_profile import ResumeProfile
from app.services.errors import JobAgentError
from app.services.llm_provider import resolve_llm_provider
from app.services.resume_pdf import render_resume_pdf
from app.services.tailored_resume_generator import (
    ResumeGenerationFailure,
    generate_tailored_resume,
    validate_resume_facts,
)


def generate_application_resume(
    saved_job_id: str,
    payload: TailoredResumeGenerateRequest,
    *,
    user_id: str,
    saved_jobs: SavedJobRepository = saved_job_repository,
    profiles: ResumeProfileRepository = resume_profile_repository,
    applications: JobApplicationRepository = job_application_repository,
    versions: TailoredResumeRepository = tailored_resume_repository,
) -> TailoredResumeVersion:
    job = saved_jobs.get(user_id=user_id, saved_job_id=saved_job_id)
    if job is None:
        raise _not_found("Saved job not found.", "saved_job_not_found")
    profile = _resolve_profile(
        user_id=user_id,
        requested_id=payload.resume_profile_id,
        latest_profile_id=job.latest_analysis.resume_profile_id if job.latest_analysis else None,
        profiles=profiles,
    )
    resolution = resolve_llm_provider(payload.llm_provider)
    if not resolution.configured or resolution.service is None:
        raise JobAgentError(
            message="A configured LLM provider is required to generate a tailored resume.",
            error_code="llm_unavailable",
            status_code=503,
        )
    try:
        generation, validation = generate_tailored_resume(
            job,
            profile,
            llm_service=resolution.service,
        )
    except ResumeGenerationFailure as exc:
        raise JobAgentError(
            message=exc.message,
            error_code=exc.code,
            status_code=422 if exc.code == "generation_validation_failed" else 502,
        ) from exc

    application = applications.get_by_saved_job(user_id=user_id, saved_job_id=saved_job_id)
    item = versions.create(
        user_id=user_id,
        saved_job_id=saved_job_id,
        resume_profile_id=profile.resume_profile_id,
        content=generation.content,
        validation=validation,
        status="needs_review",
        analysis_provider=resolution.provider,
    )
    # 简历属于岗位工作台；只有已经开始求职时才同步更新进度，不能隐式创建 Application。
    if application is not None:
        applications.update_tracking(
            user_id=user_id,
            application_id=application.application_id,
            stage=application.stage,
            next_action="review_resume",
            detail=None,
            source="system",
        )
        applications.add_event(
            application_id=application.application_id,
            user_id=user_id,
            event_type="tailored_resume_generated",
            source="user",
            detail=f"Tailored resume version {item.version} generated.",
            metadata={
                "tailored_resume_id": item.tailored_resume_id,
                "validation_passed": validation.is_valid,
            },
        )
    return item


def generate_browser_capture_resume(
    capture_id: str,
    payload: TailoredResumeGenerateRequest,
    *,
    user_id: str,
    captures: BrowserJobCaptureRepository = browser_job_capture_repository,
) -> TailoredResumeVersion:
    capture = captures.get(user_id=user_id, capture_id=capture_id)
    if capture is None:
        raise _not_found("Browser job capture not found.", "browser_job_capture_not_found")
    # Capture 只保存当前页面快照，简历版本始终归属抓取时建立的岗位主记录。
    return generate_application_resume(capture.saved_job_id, payload, user_id=user_id)


def update_application_resume(
    tailored_resume_id: str,
    payload: TailoredResumeUpdateRequest,
    *,
    user_id: str,
    profiles: ResumeProfileRepository = resume_profile_repository,
    versions: TailoredResumeRepository = tailored_resume_repository,
) -> TailoredResumeVersion:
    existing = versions.get(user_id=user_id, tailored_resume_id=tailored_resume_id)
    if existing is None:
        raise _not_found("Tailored resume not found.", "tailored_resume_not_found")
    if existing.status == "approved":
        raise JobAgentError(
            message="Approved resume versions are immutable. Generate a new version to edit.",
            error_code="tailored_resume_already_approved",
            status_code=409,
        )
    profile = profiles.get(user_id=user_id, resume_profile_id=existing.resume_profile_id)
    if profile is None:
        raise _not_found("Resume profile not found.", "resume_profile_not_found")
    validation = validate_resume_facts(payload.content, profile)
    updated = versions.update_content(
        user_id=user_id,
        tailored_resume_id=tailored_resume_id,
        content=payload.content.strip(),
        validation=validation,
    )
    if updated is None:
        raise _not_found("Tailored resume not found.", "tailored_resume_not_found")
    return updated


def approve_application_resume(
    tailored_resume_id: str,
    *,
    user_id: str,
    applications: JobApplicationRepository = job_application_repository,
    versions: TailoredResumeRepository = tailored_resume_repository,
) -> TailoredResumeVersion:
    existing = versions.get(user_id=user_id, tailored_resume_id=tailored_resume_id)
    if existing is None:
        raise _not_found("Tailored resume not found.", "tailored_resume_not_found")
    if existing.status == "approved":
        return existing
    if not existing.validation.is_valid:
        raise JobAgentError(
            message="Resolve resume fact validation issues before approval.",
            error_code="tailored_resume_validation_failed",
            status_code=409,
        )
    approved = versions.approve(user_id=user_id, tailored_resume_id=tailored_resume_id)
    if approved is None:
        raise _not_found("Tailored resume not found.", "tailored_resume_not_found")
    application = applications.get_by_saved_job(
        user_id=user_id,
        saved_job_id=approved.saved_job_id,
    )
    if application is not None:
        stage = "resume_ready" if application.stage == "resume_requested" else application.stage
        next_action = "send_resume" if stage == "resume_ready" else DEFAULT_NEXT_ACTION[stage]
        applications.update_tracking(
            user_id=user_id,
            application_id=application.application_id,
            stage=stage,
            next_action=next_action,
            detail="Tailored resume approved.",
            source="user",
        )
        applications.add_event(
            application_id=application.application_id,
            user_id=user_id,
            event_type="resume_confirmed",
            source="user",
            detail=f"Tailored resume version {approved.version} approved.",
            metadata={"tailored_resume_id": approved.tailored_resume_id},
        )
    return approved


def export_approved_resume_pdf(
    tailored_resume_id: str,
    *,
    user_id: str,
    versions: TailoredResumeRepository = tailored_resume_repository,
) -> tuple[bytes, str]:
    version = versions.get(user_id=user_id, tailored_resume_id=tailored_resume_id)
    if version is None:
        raise _not_found("Tailored resume not found.", "tailored_resume_not_found")
    if version.status != "approved":
        raise JobAgentError(
            message="Approve the tailored resume before downloading its PDF.",
            error_code="tailored_resume_not_approved",
            status_code=409,
        )
    return render_resume_pdf(version.content), f"tailored-resume-v{version.version}.pdf"


def _resolve_profile(
    *,
    user_id: str,
    requested_id: str | None,
    latest_profile_id: str | None,
    profiles: ResumeProfileRepository,
) -> ResumeProfile:
    if requested_id:
        profile = profiles.get(user_id=user_id, resume_profile_id=requested_id)
        if profile is None or profile.archived_at is not None:
            raise _not_found("Resume profile not found.", "resume_profile_not_found")
        return profile
    if latest_profile_id:
        profile = profiles.get(user_id=user_id, resume_profile_id=latest_profile_id)
        if profile is not None and profile.archived_at is None:
            return profile
    candidates = profiles.list_by_user(user_id)
    if candidates:
        return candidates[0]
    raise _not_found("Create a resume profile before tailoring a resume.", "resume_profile_required")


def _not_found(message: str, error_code: str) -> JobAgentError:
    return JobAgentError(message=message, error_code=error_code, status_code=404)
