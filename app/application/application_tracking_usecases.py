from __future__ import annotations

from app.repositories.job_application_repository import (
    JobApplicationRepository,
    job_application_repository,
)
from app.repositories.communication_draft_repository import (
    CommunicationDraftRepository,
    communication_draft_repository,
)
from app.repositories.saved_job_repository import SavedJobRepository, saved_job_repository
from app.repositories.tailored_resume_repository import (
    TailoredResumeRepository,
    tailored_resume_repository,
)
from app.schemas.job_application import (
    ApplicationEvent,
    ApplicationNextAction,
    ApplicationStage,
    JobApplication,
    JobApplicationCreateRequest,
    JobApplicationUpdateRequest,
    SavedJobWorkspace,
)
from app.services.errors import JobAgentError

DEFAULT_NEXT_ACTION: dict[ApplicationStage, ApplicationNextAction] = {
    "not_started": "generate_greeting",
    "contacted": "wait_for_reply",
    "recruiter_replied": "review_reply",
    "resume_requested": "generate_resume",
    "resume_ready": "review_resume",
    "resume_sent": "wait_for_reply",
    "interview": "prepare_interview",
    "closed": "none",
}

ALLOWED_STAGE_TRANSITIONS: dict[ApplicationStage, set[ApplicationStage]] = {
    "not_started": {"contacted", "resume_requested", "closed"},
    "contacted": {"recruiter_replied", "resume_requested", "interview", "closed"},
    "recruiter_replied": {"resume_requested", "resume_sent", "interview", "closed"},
    "resume_requested": {"resume_ready", "resume_sent", "closed"},
    "resume_ready": {"resume_sent", "closed"},
    "resume_sent": {"recruiter_replied", "interview", "closed"},
    "interview": {"closed"},
    "closed": {"not_started"},
}


def create_job_application(
    saved_job_id: str,
    payload: JobApplicationCreateRequest,
    *,
    user_id: str,
    saved_jobs: SavedJobRepository = saved_job_repository,
    applications: JobApplicationRepository = job_application_repository,
) -> JobApplication:
    if saved_jobs.get(user_id=user_id, saved_job_id=saved_job_id) is None:
        raise _saved_job_not_found()
    return applications.create_for_job(
        user_id=user_id,
        saved_job_id=saved_job_id,
        next_action=payload.next_action,
        source="user",
    )


def update_job_application(
    application_id: str,
    payload: JobApplicationUpdateRequest,
    *,
    user_id: str,
    applications: JobApplicationRepository = job_application_repository,
) -> JobApplication:
    existing = applications.get(user_id=user_id, application_id=application_id)
    if existing is None:
        raise _application_not_found()
    stage = payload.stage or existing.stage
    if stage != existing.stage and stage not in ALLOWED_STAGE_TRANSITIONS[existing.stage]:
        raise JobAgentError(
            message=f"Cannot move application from {existing.stage} to {stage}.",
            error_code="application_stage_transition_invalid",
            status_code=409,
        )
    next_action = payload.next_action
    if next_action is None:
        next_action = DEFAULT_NEXT_ACTION[stage] if stage != existing.stage else existing.next_action
    updated = applications.update_tracking(
        user_id=user_id,
        application_id=application_id,
        stage=stage,
        next_action=next_action,
        detail=payload.detail,
        source="user",
    )
    if updated is None:
        raise _application_not_found()
    return updated


def get_saved_job_workspace(
    saved_job_id: str,
    *,
    user_id: str,
    saved_jobs: SavedJobRepository = saved_job_repository,
    applications: JobApplicationRepository = job_application_repository,
    drafts: CommunicationDraftRepository = communication_draft_repository,
    tailored_resumes: TailoredResumeRepository = tailored_resume_repository,
) -> SavedJobWorkspace:
    job = saved_jobs.get(user_id=user_id, saved_job_id=saved_job_id)
    if job is None:
        raise _saved_job_not_found()
    application = applications.get_by_saved_job(
        user_id=user_id,
        saved_job_id=saved_job_id,
    )
    events: list[ApplicationEvent] = []
    communication_draft = drafts.latest_for_saved_job(
        user_id=user_id,
        saved_job_id=saved_job_id,
    )
    tailored_resume = tailored_resumes.latest_for_saved_job(
        user_id=user_id,
        saved_job_id=saved_job_id,
    )
    if application is not None:
        events = applications.list_events(
            user_id=user_id,
            application_id=application.application_id,
        )
    return SavedJobWorkspace(
        job=job,
        application=application,
        latest_analysis=job.latest_analysis,
        communication_draft=communication_draft,
        tailored_resume=tailored_resume,
        allowed_stage_transitions=(
            sorted(ALLOWED_STAGE_TRANSITIONS[application.stage])
            if application is not None
            else []
        ),
        events=events,
    )


def _saved_job_not_found() -> JobAgentError:
    return JobAgentError(
        message="Saved job not found.",
        error_code="saved_job_not_found",
        status_code=404,
    )


def _application_not_found() -> JobAgentError:
    return JobAgentError(
        message="Job application not found.",
        error_code="job_application_not_found",
        status_code=404,
    )
