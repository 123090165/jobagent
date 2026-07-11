from __future__ import annotations

from app.repositories.job_search_repository import (
    JobSearchRepository,
    job_search_repository,
)
from app.repositories.resume_profile_repository import (
    ResumeProfileRepository,
    resume_profile_repository,
)
from app.repositories.saved_job_repository import (
    SavedJobRepository,
    saved_job_repository,
)
from app.schemas.job_search import JobSearchResult
from app.schemas.saved_job import (
    SavedJob,
    SavedJobAnalysis,
    SavedJobCreateRequest,
    SavedJobFromBrowserCaptureRequest,
    SavedJobFromSearchResultRequest,
    SavedJobUpdateRequest,
)
from app.services.errors import JobAgentError


def list_saved_jobs(
    *,
    user_id: str,
    include_archived: bool = False,
    repository: SavedJobRepository = saved_job_repository,
) -> list[SavedJob]:
    return repository.list_by_user(user_id, include_archived=include_archived)


def create_saved_job(
    payload: SavedJobCreateRequest,
    *,
    user_id: str,
    repository: SavedJobRepository = saved_job_repository,
) -> SavedJob:
    return repository.save(user_id=user_id, payload=payload)


def get_saved_job(
    saved_job_id: str,
    *,
    user_id: str,
    repository: SavedJobRepository = saved_job_repository,
) -> SavedJob:
    job = repository.get(user_id=user_id, saved_job_id=saved_job_id)
    if job is None:
        raise _not_found()
    return job


def list_saved_job_analyses(
    saved_job_id: str,
    *,
    user_id: str,
    repository: SavedJobRepository = saved_job_repository,
) -> list[SavedJobAnalysis]:
    if repository.get(user_id=user_id, saved_job_id=saved_job_id) is None:
        raise _not_found()
    return repository.list_analyses(user_id=user_id, saved_job_id=saved_job_id)


def update_saved_job(
    saved_job_id: str,
    payload: SavedJobUpdateRequest,
    *,
    user_id: str,
    repository: SavedJobRepository = saved_job_repository,
) -> SavedJob:
    job = repository.update(user_id=user_id, saved_job_id=saved_job_id, payload=payload)
    if job is None:
        raise _not_found()
    return job


def archive_saved_job(
    saved_job_id: str,
    *,
    user_id: str,
    repository: SavedJobRepository = saved_job_repository,
) -> SavedJob:
    job = repository.archive(user_id=user_id, saved_job_id=saved_job_id)
    if job is None:
        raise _not_found()
    return job


def save_job_from_search_result(
    payload: SavedJobFromSearchResultRequest,
    *,
    user_id: str,
    search_repository: JobSearchRepository = job_search_repository,
    resume_profiles: ResumeProfileRepository = resume_profile_repository,
    saved_jobs: SavedJobRepository = saved_job_repository,
) -> SavedJob:
    run = search_repository.get(payload.job_search_run_id, user_id=user_id)
    if run is None:
        raise JobAgentError(
            message="Job search run not found.",
            error_code="job_search_run_not_found",
            status_code=404,
        )
    result = next(
        (item for item in run.results if item.job_result_id == payload.job_result_id),
        None,
    )
    if result is None:
        raise JobAgentError(
            message="Job search result not found.",
            error_code="job_search_result_not_found",
            status_code=404,
        )

    resume_profile_id = payload.resume_profile_id
    if resume_profile_id is None:
        profile = resume_profiles.get_by_confirmed_profile(
            user_id=user_id,
            confirmed_profile_id=run.confirmed_profile_id,
        )
        resume_profile_id = profile.resume_profile_id if profile is not None else None

    job = saved_jobs.save(
        user_id=user_id,
        payload=SavedJobCreateRequest(
            source_provider=result.source_provider or result.source,
            source_url=result.source_url,
            title=result.title,
            company=result.company,
            location=result.location,
            raw_jd_text=result.description,
            structured_jd=_structured_jd_from_result(result),
            tags=payload.tags,
            status=payload.status,
            notes=payload.notes,
        ),
    )
    saved_jobs.create_analysis(
        user_id=user_id,
        saved_job_id=job.saved_job_id,
        resume_profile_id=resume_profile_id,
        source_job_search_run_id=run.job_search_run_id,
        source_job_result_id=result.job_result_id,
        match_score=result.match_score,
        confidence_label=result.confidence_label,
        recommendation=result.recommended_action,
        matched_strengths=result.match_reasons + result.matched_keywords,
        critical_gaps=result.risks,
        resume_actions=[result.recommended_action] if result.recommended_action else [],
        interview_questions=[],
        analysis=result.model_dump(mode="json"),
        analysis_mode=result.analysis_mode,
    )
    saved = saved_jobs.get(user_id=user_id, saved_job_id=job.saved_job_id)
    if saved is None:
        raise RuntimeError("Saved job disappeared after analysis creation.")
    return saved


def save_job_from_browser_capture(
    payload: SavedJobFromBrowserCaptureRequest,
    *,
    user_id: str,
    repository: SavedJobRepository = saved_job_repository,
) -> SavedJob:
    job = repository.save(user_id=user_id, payload=payload)
    if payload.analysis is not None:
        repository.create_analysis(
            user_id=user_id,
            saved_job_id=job.saved_job_id,
            resume_profile_id=payload.resume_profile_id,
            match_score=payload.match_score,
            confidence_label=payload.confidence_label,
            recommendation=payload.recommendation,
            matched_strengths=[],
            critical_gaps=[],
            resume_actions=[payload.recommendation] if payload.recommendation else [],
            interview_questions=[],
            analysis=payload.analysis,
            analysis_mode=str(payload.analysis.get("analysis_mode") or "browser_capture"),
        )
        saved = repository.get(user_id=user_id, saved_job_id=job.saved_job_id)
        if saved is not None:
            return saved
    return job


def _structured_jd_from_result(result: JobSearchResult) -> dict[str, object]:
    return {
        "title": result.title,
        "company": result.company,
        "location": result.location,
        "source": result.source,
        "source_provider": result.source_provider,
        "source_url": result.source_url,
        "raw_snippet": result.raw_snippet,
        "matched_keywords": result.matched_keywords,
        "match_reasons": result.match_reasons,
        "risks": result.risks,
        "score_breakdown": result.score_breakdown,
        "evidence_quotes": result.evidence_quotes,
    }


def _not_found() -> JobAgentError:
    return JobAgentError(
        message="Saved job not found.",
        error_code="saved_job_not_found",
        status_code=404,
    )
