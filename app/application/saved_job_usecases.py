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
    PreparationAnswer,
    PreparationGenerationStage,
    PreparationAnswerRequest,
    PreparationGenerateRequest,
)
from app.schemas.saved_job import (
    SavedJob,
    SavedJobAnalysis,
    SavedJobCreateRequest,
    SavedJobFromSearchResultRequest,
    SavedJobOrigin,
    SavedJobUpdateRequest,
)
from app.services.errors import JobAgentError
from app.services.job_brief_generator import generate_job_brief_content
from app.services.interview_preparation_generator import (
    build_external_prompt,
    generate_next_preparation_question,
    generate_preparation_questions,
    generate_recommendations,
    resolve_preparation_answers,
)
from app.services.learning_resource_search import (
    OfficialCatalogResourceSearch,
    resource_error_summary,
    resolve_learning_resource_search,
)
from app.services.llm_provider import resolve_llm_provider
from app.services.llm_observability import langfuse_span
from app.services.preparation_agent import classify_answer_detail, preparation_agent


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
    job = repository.save(user_id=user_id, payload=payload)
    repository.create_origin(
        user_id=user_id,
        saved_job_id=job.saved_job_id,
        origin_key=f"manual:{job.saved_job_id}",
        origin_type="manual",
        source_provider=job.source_provider,
    )
    return job


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


def list_saved_job_contexts(
    saved_job_id: str,
    *,
    user_id: str,
    repository: SavedJobRepository = saved_job_repository,
) -> list[SavedJobOrigin]:
    if repository.get(user_id=user_id, saved_job_id=saved_job_id) is None:
        raise _not_found()
    return repository.list_origins(user_id=user_id, saved_job_id=saved_job_id)


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
    gaps, questions, question_generation = generate_preparation_questions(
        job, profile, analysis, llm_service=resolution.service
    )
    question_generation = question_generation.model_copy(
        update={"provider": resolution.provider}
    )
    workspace = preparations.create(
        user_id=user_id, saved_job_id=saved_job_id,
        resume_profile_id=profile.resume_profile_id if profile else None,
        source_analysis_id=analysis.saved_job_analysis_id if analysis else None,
        skill_gaps=gaps, questions=questions, learning_resources=[],
        analysis_mode=question_generation.mode, analysis_provider=resolution.provider,
        fallback_reason=question_generation.fallback_reason,
        question_generation=question_generation,
        resource_mode="pending_answers",
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
    submitted_answers = _merge_preparation_answers(item.answers, payload.answers)
    resolution = resolve_llm_provider(payload.llm_provider)
    if payload.action == "advance":
        if len(payload.answers) != 1:
            raise JobAgentError(
                message="Advance exactly one preparation question at a time.",
                error_code="preparation_advance_invalid", status_code=400,
            )
        question_id = payload.answers[0].question_id
        was_committed = any(
            answer.question_id == question_id and answer.committed for answer in item.answers
        )
        current = [answer for answer in submitted_answers if answer.question_id == question_id]
        try:
            routed = resolve_preparation_answers(
                item.questions, current, llm_service=resolution.service,
                classify_free_text=True,
            )
        except ValueError as exc:
            raise JobAgentError(
                message=str(exc), error_code="preparation_answer_invalid", status_code=400,
            ) from exc
        normalized = _classify_answer_details(routed)
        transition = preparation_agent.resume(
            item.preparation_id, normalized, "advance", questions=item.questions,
        )
        transitioned = [
            PreparationAnswer.model_validate(answer)
            for answer in transition.get("answers", [])
        ]
        merged_answers = _merge_preparation_answers(item.answers, transitioned)
        updated_gaps = _apply_preparation_answers(
            item.skill_gaps, item.questions, merged_answers
        )
        if transition["status"] == "paused":
            return preparations.save_answers(
                item.model_copy(update={"skill_gaps": updated_gaps}),
                answers=merged_answers, status="paused",
            )
        questions = list(item.questions)
        if not was_committed and len(questions) < 5:
            next_question, _ = await asyncio.to_thread(
                generate_next_preparation_question,
                updated_gaps, questions, merged_answers,
                llm_service=resolution.service,
            )
            if next_question is not None:
                questions.append(next_question)
        return preparations.save_answers(
            item.model_copy(update={
                "skill_gaps": updated_gaps,
                "questions": questions,
            }),
            answers=merged_answers, status="questions_ready",
        )
    try:
        routed_answers = resolve_preparation_answers(
            item.questions,
            submitted_answers,
            llm_service=resolution.service,
            classify_free_text=payload.action == "complete",
        )
    except ValueError as exc:
        raise JobAgentError(
            message=str(exc),
            error_code="preparation_answer_invalid",
            status_code=400,
        ) from exc
    normalized_answers = _classify_answer_details(routed_answers)
    if payload.action == "complete":
        _validate_complete_preparation_answers(item.questions, normalized_answers)
    transition = preparation_agent.resume(
        item.preparation_id,
        normalized_answers,
        payload.action,
        questions=item.questions,
    )
    normalized_answers = [
        PreparationAnswer.model_validate(answer)
        for answer in transition.get("answers", [])
    ]
    updated_gaps = _apply_preparation_answers(item.skill_gaps, item.questions, normalized_answers)
    if transition["status"] != "completed":
        return preparations.save_answers(
            item.model_copy(update={"skill_gaps": updated_gaps}),
            answers=normalized_answers,
            status=transition["status"],
        )
    recommendation_task = asyncio.to_thread(
        generate_recommendations,
        updated_gaps,
        item.questions,
        normalized_answers,
        llm_service=resolution.service,
    )
    resource_task = _resources_for_preparation_answers(
        updated_gaps, item.questions, normalized_answers
    )
    (recommendations, recommendation_generation), resource_result = await asyncio.gather(
        recommendation_task, resource_task
    )
    recommendation_generation = recommendation_generation.model_copy(
        update={"provider": resolution.provider}
    )
    mode, fallback_reason = _summarize_generation_stages(
        item.question_generation,
        recommendation_generation,
    )
    resources, resource_mode, resource_warning = resource_result
    recommendations = _bind_resources_to_recommendations(recommendations, resources)
    return preparations.complete(
        item.model_copy(update={"skill_gaps": updated_gaps}),
        answers=normalized_answers, recommendations=recommendations,
        analysis_mode=mode, analysis_provider=resolution.provider,
        fallback_reason=fallback_reason,
        recommendation_generation=recommendation_generation,
        learning_resources=resources, resource_mode=resource_mode,
        resource_warning=resource_warning,
    )


def _summarize_generation_stages(
    question_generation: PreparationGenerationStage | None,
    recommendation_generation: PreparationGenerationStage | None,
) -> tuple[str, str | None]:
    stages = [
        ("questions", question_generation),
        ("recommendations", recommendation_generation),
    ]
    available = [(name, stage) for name, stage in stages if stage is not None]
    if not available:
        return "deterministic", None
    if any(stage.mode == "fallback" for _, stage in available):
        mode = "fallback"
    elif any(stage.mode == "llm" for _, stage in available):
        mode = "llm"
    else:
        mode = "deterministic"
    reasons = [
        f"{name}: {stage.fallback_reason}"
        for name, stage in available
        if stage.fallback_reason
    ]
    return mode, "; ".join(reasons) or None


def _apply_preparation_answers(skill_gaps, questions, answers):
    question_by_id = {question.question_id: question for question in questions}
    answers_by_skill = {}
    for answer in answers:
        question = question_by_id.get(answer.question_id)
        if question is not None:
            answers_by_skill.setdefault(question.skill, []).append((question, answer))
    updated = []
    for gap in skill_gaps:
        skill_answers = answers_by_skill.get(gap.skill, [])
        if not skill_answers:
            updated.append(gap)
            continue
        dimensions = {item.dimension_id: item for item in gap.dimensions}
        evidence_status = gap.evidence_status
        skill_type = gap.skill_type
        for question, answer in skill_answers:
            level = answer.experience_level
            evidence_status = answer.evidence_transition
            if evidence_status is None and level in {"work_experience", "project_experience"}:
                evidence_status = "supported" if (answer.detail or answer.free_text or answer.answer) else "partial"
            elif evidence_status is None and level in {"practice_only", "conceptual_only"}:
                evidence_status = "partial"
            elif evidence_status is None and level == "no_experience":
                evidence_status = "missing"
            elif evidence_status is None:
                evidence_status = "unknown"
            option = next(
                (item for item in question.options if item.option_id == answer.selected_option_id),
                None,
            )
            for effect in option.state_effects if option is not None else []:
                current = dimensions.get(effect.dimension_id)
                if current is not None:
                    state = "supported" if answer.evidence_transition == "supported" else effect.state
                    evidence = list(current.evidence)
                    evidence.append(f"User selected: {option.label}")
                    dimensions[effect.dimension_id] = current.model_copy(update={
                        "state": state, "evidence": list(dict.fromkeys(evidence)),
                    })
            if answer.route == "learning":
                skill_type = "knowledge"
        updated.append(gap.model_copy(update={
            "evidence_status": evidence_status,
            "evidence_origin": "user_reported",
            "skill_type": skill_type,
            "dimensions": list(dimensions.values()),
        }))
    return updated


def _classify_answer_details(answers):
    normalized = []
    for answer in answers:
        quality = classify_answer_detail(answer)
        normalized.append(answer.model_copy(update={"detail_quality": quality}))
    return normalized


def _merge_preparation_answers(existing, submitted):
    """Accept incremental follow-up submissions while preserving prior answers."""
    submitted_by_id = {item.question_id: item for item in submitted}
    merged = []
    for previous in existing:
        replacement = submitted_by_id.pop(previous.question_id, None)
        if replacement is None:
            merged.append(previous)
            continue
        backend_state = {}
        if "follow_up_count" not in replacement.model_fields_set:
            backend_state["follow_up_count"] = previous.follow_up_count
        if "pending_prompt" not in replacement.model_fields_set:
            backend_state["pending_prompt"] = previous.pending_prompt
        if "committed" not in replacement.model_fields_set:
            backend_state["committed"] = previous.committed
        merged.append(replacement.model_copy(update=backend_state))
    merged.extend(submitted_by_id.values())
    return merged


def _validate_complete_preparation_answers(questions, answers) -> None:
    answer_by_id = {item.question_id: item for item in answers}
    missing = [
        item.question_id for item in questions if item.question_id not in answer_by_id
    ]
    if missing:
        raise JobAgentError(
            message="Complete every preparation question before generating the summary.",
            error_code="preparation_answers_incomplete",
            status_code=400,
        )


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
    with langfuse_span(
        "preparation.search_learning_resources",
        as_type="retriever",
        metadata={"topics": topics, "topic_count": len(topics)},
    ) as span:
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
                warnings.append(f"{topic}: {resource_error_summary(result)}")
                resources.extend(await catalog.search(topic, limit=2))
            else:
                resources.extend(result or await catalog.search(topic, limit=2))
        if warnings and mode == "catalog_mcp":
            mode = "catalog_mcp_fallback"
        if span is not None:
            span.update(output={
                "resource_count": len(resources[:6]),
                "mode": mode if topics else "not_needed",
                "warning_count": len(warnings),
            })
        return resources[:6], mode if topics else "not_needed", "; ".join(warnings) or None


def _bind_resources_to_recommendations(recommendations, resources):
    resources_by_topic = {}
    for resource in resources:
        resources_by_topic.setdefault(resource.topic.casefold(), []).append(resource)
    bound = []
    for item in recommendations:
        matches = resources_by_topic.get((item.skill or "").casefold(), [])
        if item.action_type != "learning" or not matches:
            bound.append(item)
            continue
        urls = [resource.url for resource in matches]
        titles = ", ".join(f'"{resource.title}"' for resource in matches)
        bound.append(item.model_copy(update={
            "resource_urls": urls,
            "action": f"{item.action.rstrip()} Start with the linked resource(s): {titles}.",
        }))
    return bound


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

    profile = None
    resume_profile_id = payload.resume_profile_id or run.resume_profile_id
    if resume_profile_id is not None:
        profile = resume_profiles.get(user_id=user_id, resume_profile_id=resume_profile_id)
        if profile is None or profile.archived_at is not None:
            raise JobAgentError(
                message="Resume profile not found or archived.",
                error_code="resume_profile_not_found",
                status_code=404,
            )
    else:
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
            notes=payload.notes,
        ),
    )
    analysis = saved_jobs.create_analysis(
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
    saved_jobs.create_origin(
        user_id=user_id,
        saved_job_id=job.saved_job_id,
        origin_key=f"search:{run.job_search_run_id}:{result.job_result_id}:{resume_profile_id or 'none'}",
        origin_type="search_result",
        resume_profile_id=resume_profile_id,
        job_search_run_id=run.job_search_run_id,
        job_search_result_id=result.job_result_id,
        saved_job_analysis_id=analysis.saved_job_analysis_id,
        profile_label=profile.name if profile else None,
        search_query=run.query,
        source_provider=result.source_provider or result.source,
    )
    saved = saved_jobs.get(user_id=user_id, saved_job_id=job.saved_job_id)
    if saved is None:
        raise RuntimeError("Saved job disappeared after analysis creation.")
    return saved


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
        "requirements": [
            requirement.model_dump(mode="json")
            for requirement in result.job_requirements
        ],
        "unknowns": result.unknowns,
        "hard_constraint_status": result.hard_constraint_status,
    }


def _not_found() -> JobAgentError:
    return JobAgentError(
        message="Saved job not found.",
        error_code="saved_job_not_found",
        status_code=404,
    )
