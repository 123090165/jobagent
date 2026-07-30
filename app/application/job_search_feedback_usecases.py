"""编排 搜索结果反馈 的所有权检查、状态转换、领域服务和持久化操作。"""

from __future__ import annotations

from app.repositories.job_search_feedback_repository import (
    JobSearchFeedbackRepository,
    job_search_feedback_repository,
)
from app.repositories.job_search_repository import JobSearchRepository, job_search_repository
from app.repositories.resume_profile_repository import ResumeProfileRepository, resume_profile_repository
from app.schemas.job_search_feedback import (
    JobSearchResultFeedback,
    JobSearchResultFeedbackUpsertRequest,
)
from app.services.errors import JobAgentError


def list_result_feedback(
    run_id: str,
    *,
    user_id: str,
    runs: JobSearchRepository = job_search_repository,
    feedback: JobSearchFeedbackRepository = job_search_feedback_repository,
) -> list[JobSearchResultFeedback]:
    _owned_run(run_id, user_id=user_id, runs=runs)
    return feedback.list_for_run(user_id=user_id, job_search_run_id=run_id)


def upsert_result_feedback(
    run_id: str,
    result_id: str,
    payload: JobSearchResultFeedbackUpsertRequest,
    *,
    user_id: str,
    runs: JobSearchRepository = job_search_repository,
    profiles: ResumeProfileRepository = resume_profile_repository,
    feedback: JobSearchFeedbackRepository = job_search_feedback_repository,
) -> JobSearchResultFeedback:
    run = _owned_run(run_id, user_id=user_id, runs=runs)
    result = next((item for item in run.results if item.job_result_id == result_id), None)
    if result is None:
        raise JobAgentError(
            message="Job search result not found.",
            error_code="job_search_result_not_found",
            status_code=404,
        )
    resume_profile = profiles.get_by_confirmed_profile(
        user_id=user_id,
        confirmed_profile_id=run.confirmed_profile_id,
    )
    return feedback.upsert(
        user_id=user_id,
        job_search_run_id=run.job_search_run_id,
        job_result_id=result.job_result_id,
        confirmed_profile_id=run.confirmed_profile_id,
        resume_profile_id=resume_profile.resume_profile_id if resume_profile else None,
        source_provider=result.source_provider or result.source,
        feedback_type=payload.feedback_type,
        note=payload.note,
    )


def _owned_run(run_id: str, *, user_id: str, runs: JobSearchRepository):
    run = runs.get(run_id, user_id=user_id)
    if run is None:
        raise JobAgentError(
            message="Job search run not found.",
            error_code="job_search_run_not_found",
            status_code=404,
        )
    return run
