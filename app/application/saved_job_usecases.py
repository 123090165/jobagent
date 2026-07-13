from __future__ import annotations

import asyncio

from app.repositories.job_search_repository import (
    JobSearchRepository,
    job_search_repository,
)
from app.repositories.job_brief_repository import (
    JobBriefRepository,
    job_brief_repository,
)
from app.repositories.interview_preparation_repository import (
    InterviewPreparationRepository,
    interview_preparation_repository,
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
from app.schemas.job_brief import JobBrief, JobBriefGenerateRequest
from app.schemas.interview_preparation import (
    InterviewPreparationWorkspace,
    PreparationAnswerRequest,
    PreparationGenerateRequest,
)
from app.schemas.saved_job import (
    SavedJob,
    SavedJobAnalysis,
    SavedJobCreateRequest,
    SavedJobFromBrowserCaptureRequest,
    SavedJobFromSearchResultRequest,
    SavedJobUpdateRequest,
    SavedJobStatusEvent,
)
from app.services.errors import JobAgentError
from app.services.job_brief_generator import generate_job_brief_content
from app.services.interview_preparation_generator import (
    build_external_prompt,
    generate_preparation_questions,
    generate_recommendations,
)
from app.services.learning_resource_search import (
    OfficialCatalogResourceSearch,
    resolve_learning_resource_search,
)
from app.services.llm_provider import resolve_llm_provider
from app.services.preparation_agent import preparation_agent


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


def list_saved_job_status_events(
    saved_job_id: str,
    *,
    user_id: str,
    repository: SavedJobRepository = saved_job_repository,
) -> list[SavedJobStatusEvent]:
    if repository.get(user_id=user_id, saved_job_id=saved_job_id) is None:
        raise _not_found()
    return repository.list_status_events(user_id=user_id, saved_job_id=saved_job_id)


def list_job_briefs(
    saved_job_id: str,
    *,
    user_id: str,
    saved_jobs: SavedJobRepository = saved_job_repository,
    briefs: JobBriefRepository = job_brief_repository,
) -> list[JobBrief]:
    if saved_jobs.get(user_id=user_id, saved_job_id=saved_job_id) is None:
        raise _not_found()
    return briefs.list_by_job(user_id=user_id, saved_job_id=saved_job_id)


def generate_job_brief(
    saved_job_id: str,
    payload: JobBriefGenerateRequest,
    *,
    user_id: str,
    saved_jobs: SavedJobRepository = saved_job_repository,
    resume_profiles: ResumeProfileRepository = resume_profile_repository,
    briefs: JobBriefRepository = job_brief_repository,
) -> JobBrief:
    job = saved_jobs.get(user_id=user_id, saved_job_id=saved_job_id)
    if job is None:
        raise _not_found()
    analysis = saved_jobs.latest_analysis(user_id=user_id, saved_job_id=saved_job_id)
    profile_id = payload.resume_profile_id or (analysis.resume_profile_id if analysis else None)
    profile = None
    if profile_id is not None:
        profile = resume_profiles.get(user_id=user_id, resume_profile_id=profile_id)
        if profile is None or profile.archived_at is not None:
            raise JobAgentError(
                message="Resume profile not found or archived.",
                error_code="resume_profile_not_found",
                status_code=404,
            )
    else:
        profile = next(
            (item for item in resume_profiles.list_by_user(user_id) if item.is_default),
            None,
        )
    resolution = resolve_llm_provider(payload.llm_provider)
    content, mode, fallback_reason = generate_job_brief_content(
        job, profile, analysis, llm_service=resolution.service
    )
    return briefs.create(
        user_id=user_id,
        saved_job_id=saved_job_id,
        resume_profile_id=profile.resume_profile_id if profile else None,
        source_analysis_id=analysis.saved_job_analysis_id if analysis else None,
        content=content,
        analysis_mode=mode,
        analysis_provider=resolution.provider,
        fallback_reason=fallback_reason,
    )


async def generate_interview_preparation(
    saved_job_id: str,
    payload: PreparationGenerateRequest,
    *,
    user_id: str,
    saved_jobs: SavedJobRepository = saved_job_repository,
    resume_profiles: ResumeProfileRepository = resume_profile_repository,
    preparations: InterviewPreparationRepository = interview_preparation_repository,
) -> InterviewPreparationWorkspace:
    job = saved_jobs.get(user_id=user_id, saved_job_id=saved_job_id)
    if job is None:
        raise _not_found()
    analysis = saved_jobs.latest_analysis(user_id=user_id, saved_job_id=saved_job_id)
    profile = _resolve_preparation_profile(
        user_id=user_id, requested_id=payload.resume_profile_id,
        analysis=analysis, resume_profiles=resume_profiles,
    )
    resolution = resolve_llm_provider(payload.llm_provider)
    gaps, questions, mode, fallback_reason = generate_preparation_questions(
        job, profile, analysis, llm_service=resolution.service
    )
    workspace = preparations.create(
        user_id=user_id, saved_job_id=saved_job_id,
        resume_profile_id=profile.resume_profile_id if profile else None,
        source_analysis_id=analysis.saved_job_analysis_id if analysis else None,
        skill_gaps=gaps, questions=questions, learning_resources=[],
        analysis_mode=mode, analysis_provider=resolution.provider,
        fallback_reason=fallback_reason, resource_mode="pending_answers",
        resource_warning=None,
    )
    preparation_agent.start(workspace.preparation_id, workspace.questions)
    return workspace


def get_interview_preparation(
    saved_job_id: str, *, user_id: str,
    saved_jobs: SavedJobRepository = saved_job_repository,
    preparations: InterviewPreparationRepository = interview_preparation_repository,
) -> InterviewPreparationWorkspace:
    if saved_jobs.get(user_id=user_id, saved_job_id=saved_job_id) is None:
        raise _not_found()
    item = preparations.get(user_id=user_id, saved_job_id=saved_job_id)
    if item is None:
        raise JobAgentError(
            message="Interview preparation workspace not found.",
            error_code="interview_preparation_not_found", status_code=404,
        )
    return item


async def complete_interview_preparation(
    saved_job_id: str, payload: PreparationAnswerRequest, *, user_id: str,
    preparations: InterviewPreparationRepository = interview_preparation_repository,
) -> InterviewPreparationWorkspace:
    item = get_interview_preparation(saved_job_id, user_id=user_id, preparations=preparations)
    valid_ids = {question.question_id for question in item.questions}
    if (payload.action != "stop" and not payload.answers) or any(
        answer.question_id not in valid_ids for answer in payload.answers
    ):
        raise JobAgentError(
            message="Answers must reference questions in this preparation workspace.",
            error_code="preparation_answer_invalid", status_code=400,
        )
    normalized_answers = _classify_answer_details(payload.answers)
    transition = preparation_agent.resume(
        item.preparation_id,
        normalized_answers,
        payload.action,
        questions=item.questions,
    )
    updated_gaps = _apply_preparation_answers(item.skill_gaps, item.questions, normalized_answers)
    if payload.action in {"save", "stop"}:
        return preparations.save_answers(
            item.model_copy(update={"skill_gaps": updated_gaps}),
            answers=normalized_answers,
            status=transition["status"],
        )
    resolution = resolve_llm_provider(payload.llm_provider)
    recommendations, mode, fallback_reason = generate_recommendations(
        updated_gaps, item.questions, normalized_answers, llm_service=resolution.service
    )
    resources, resource_mode, resource_warning = await _resources_for_preparation_answers(
        updated_gaps, item.questions, normalized_answers
    )
    return preparations.complete(
        item.model_copy(update={"skill_gaps": updated_gaps}),
        answers=normalized_answers, recommendations=recommendations,
        analysis_mode=mode, analysis_provider=resolution.provider,
        fallback_reason=fallback_reason,
        learning_resources=resources, resource_mode=resource_mode,
        resource_warning=resource_warning,
    )


def _apply_preparation_answers(skill_gaps, questions, answers):
    question_by_id = {question.question_id: question for question in questions}
    answer_by_skill = {
        question_by_id[answer.question_id].skill: answer
        for answer in answers if answer.question_id in question_by_id
    }
    updated = []
    for gap in skill_gaps:
        answer = answer_by_skill.get(gap.skill)
        if answer is None:
            updated.append(gap)
            continue
        level = answer.experience_level
        if level in {"work_experience", "project_experience"}:
            evidence_status = "supported" if (answer.detail or answer.answer) else "partial"
        elif level in {"practice_only", "conceptual_only", "uncertain"}:
            evidence_status = "partial"
        elif level == "no_experience":
            evidence_status = "missing"
        else:
            evidence_status = "partial"
        updated.append(gap.model_copy(update={
            "evidence_status": evidence_status,
            "evidence_origin": "user_reported",
        }))
    return updated


def _classify_answer_details(answers):
    specific_markers = ("built", "created", "implemented", "used", "reduced", "increased", "result", "team")
    normalized = []
    for answer in answers:
        detail = (answer.detail or answer.answer or "").strip()
        quality = "not_provided"
        if detail:
            quality = "specific" if len(detail) >= 40 and any(
                marker in detail.casefold() for marker in specific_markers
            ) else "vague"
        normalized.append(answer.model_copy(update={"detail_quality": quality}))
    return normalized


async def _resources_for_preparation_answers(gaps, questions, answers):
    question_by_id = {question.question_id: question for question in questions}
    learning_levels = {"practice_only", "conceptual_only", "no_experience"}
    skills = {
        question_by_id[answer.question_id].skill
        for answer in answers
        if answer.question_id in question_by_id and answer.experience_level in learning_levels
    }
    topics = [
        gap.skill for gap in gaps
        if gap.skill in skills and gap.skill_type == "knowledge"
    ][:3]
    search, mode = resolve_learning_resource_search()
    results = await asyncio.gather(
        *(search.search(topic, limit=2) for topic in topics),
        return_exceptions=True,
    )
    resources = []
    warnings = []
    catalog = OfficialCatalogResourceSearch()
    for topic, result in zip(topics, results):
        if isinstance(result, Exception):
            warnings.append(f"{topic}: {type(result).__name__}")
            resources.extend(await catalog.search(topic, limit=2))
        else:
            resources.extend(result or await catalog.search(topic, limit=2))
    if warnings and mode == "catalog_mcp":
        mode = "catalog_mcp_fallback"
    return resources[:6], mode if topics else "not_needed", "; ".join(warnings) or None


def export_interview_preparation_prompt(
    saved_job_id: str, *, user_id: str,
    saved_jobs: SavedJobRepository = saved_job_repository,
    resume_profiles: ResumeProfileRepository = resume_profile_repository,
    preparations: InterviewPreparationRepository = interview_preparation_repository,
) -> str:
    item = get_interview_preparation(
        saved_job_id, user_id=user_id, saved_jobs=saved_jobs, preparations=preparations
    )
    job = get_saved_job(saved_job_id, user_id=user_id, repository=saved_jobs)
    profile = (
        resume_profiles.get(user_id=user_id, resume_profile_id=item.resume_profile_id)
        if item.resume_profile_id else None
    )
    return build_external_prompt(job, profile, item.skill_gaps, item.questions)


def _resolve_preparation_profile(
    *, user_id: str, requested_id: str | None, analysis: SavedJobAnalysis | None,
    resume_profiles: ResumeProfileRepository,
):
    profile_id = requested_id or (analysis.resume_profile_id if analysis else None)
    if profile_id:
        profile = resume_profiles.get(user_id=user_id, resume_profile_id=profile_id)
        if profile is None or profile.archived_at is not None:
            raise JobAgentError(
                message="Resume profile not found or archived.",
                error_code="resume_profile_not_found", status_code=404,
            )
        return profile
    return next((item for item in resume_profiles.list_by_user(user_id) if item.is_default), None)


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


def delete_saved_job(
    saved_job_id: str,
    *,
    user_id: str,
    repository: SavedJobRepository = saved_job_repository,
) -> None:
    if not repository.delete(user_id=user_id, saved_job_id=saved_job_id):
        raise _not_found()


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
