from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from fastapi import BackgroundTasks

from app.application.profile_session_usecases import get_profile_session
from app.repositories.confirmed_profile_repository import (
    ConfirmedProfileRepository,
    confirmed_profile_repository,
)
from app.repositories.job_search_repository import (
    JobSearchRepository,
    job_search_repository,
)
from app.repositories.profile_session_repository import (
    ProfileSessionRepository,
    profile_session_repository,
)
from app.repositories.resume_profile_repository import (
    ResumeProfileRepository,
    resume_profile_repository,
)
from app.repositories.search_mission_repository import (
    SearchMissionRepository,
    search_mission_repository,
)
from app.schemas.confirmed_profile import ConfirmedProfile
from app.schemas.job_search import (
    BrowserJobCaptureAnalyzeResponse,
    BrowserJobCaptureRequest,
    BrowserHelperJobSearchRunCreateRequest,
    JobSearchResult,
    JobSearchPreviewResponse,
    JobSearchRun,
    JobSearchRunCreateRequest,
    JobSearchRunResponse,
    JobSearchTraceStep,
)
from app.schemas.search_mission import SearchMission
from app.services.errors import JobAgentError
from app.services.job_candidate_filter import filter_candidates
from app.services.job_search_execution.candidate_analysis import _analyze_candidates
from app.services.job_search_execution.browser_capture import (
    _browser_capture_report,
    _browser_helper_candidate_to_raw,
    _capture_summary,
    _trace_quality_warnings,
    browser_job_capture_to_candidate,
)
from app.services.job_search_execution.preview import (
    _augment_search_plan,
    _augment_search_plan_from_inputs,
    _build_provider_preview_searches,
    _estimate_query_budget,
    _provider_name_from_selected_sources,
    _ranking_signals_from_plan,
    _recall_queries_from_plan,
    _resolve_search_inputs,
    _resolve_selected_sources,
    _search_source_notes,
)
from app.services.job_search_execution.provider_search import (
    MAX_PROVIDER_QUERIES_PER_RUN,
    _provider_source_kind,
    _run_provider_search,
)
from app.services.job_search_execution.trace import (
    ASSEMBLY_GUARDRAILS,
    FILTER_GUARDRAILS,
    PLANNING_GUARDRAILS,
    TRACE_STEP_NAMES,
    _create_initial_trace_steps,
    _ensure_trace_steps,
    _find_running_or_pending_step,
)
from app.services.job_search_planner import (
    JobSearchPlan,
    build_search_plan,
)
from app.services.job_search_execution.result_builder import (
    _assemble_results,
    _build_local_mock_results,
    _match_candidates,
    _source_provider_counts,
)
from app.services.job_search_providers import (
    BrowserHelperPayloadProvider,
    JobSearchProvider,
    normalize_job_search_provider_name,
    normalize_job_search_source_name,
    resolve_job_search_provider,
)
from app.services.job_search_providers.multi_source_provider import MultiSourceJobSearchProvider
from app.services.llm_provider import (
    DEFAULT_LLM_PROVIDER,
    JSONChatLLM,
    LLMProviderName,
    normalize_llm_provider,
    resolve_llm_provider,
)
from app.storage.database import LOCAL_USER_ID

def _uses_job_search_analysis(search_mode: str) -> bool:
    return search_mode in {"live_search", "browser_helper"}


@dataclass(frozen=True)
class JobSearchAnalysisConfig:
    enabled: bool
    provider: LLMProviderName | None = None

    @property
    def mode(self) -> Literal["deterministic", "llm"]:
        return "llm" if self.enabled else "deterministic"


def create_job_search_run(
    payload: JobSearchRunCreateRequest,
    *,
    user_id: str | None = None,
    background_tasks: BackgroundTasks | None = None,
    session_repository: ProfileSessionRepository = profile_session_repository,
    confirmed_repository: ConfirmedProfileRepository = confirmed_profile_repository,
    search_repository: JobSearchRepository = job_search_repository,
    job_search_provider: JobSearchProvider | None = None,
    llm_service: JSONChatLLM | None = None,
    mission_repository: SearchMissionRepository = search_mission_repository,
    resume_profiles: ResumeProfileRepository = resume_profile_repository,
) -> JobSearchRunResponse:
    session = get_profile_session(payload.session_id, repository=session_repository, user_id=user_id)
    if session.confirmed_profile_id is None:
        raise JobAgentError(
            message="Confirmed profile is required before starting job search.",
            error_code="confirmed_profile_required",
            status_code=409,
        )
    if session.current_step not in {"job_search_ready", "job_search_running", "job_search_completed"}:
        raise JobAgentError(
            message="Profile session is not ready for job search.",
            error_code="invalid_profile_session_state",
            status_code=409,
        )

    confirmed_profile = confirmed_repository.get(session.confirmed_profile_id, user_id=user_id)
    if confirmed_profile is None:
        raise JobAgentError(
            message="Confirmed profile not found.",
            error_code="confirmed_profile_not_found",
            status_code=404,
        )

    durable_profile = resume_profiles.get_by_confirmed_profile(
        user_id=user_id or LOCAL_USER_ID,
        confirmed_profile_id=confirmed_profile.confirmed_profile_id,
    )

    query, locations, target_roles, keywords, mission = _resolve_inputs_with_mission(
        payload,
        confirmed_profile,
        user_id=user_id or LOCAL_USER_ID,
        mission_repository=mission_repository,
    )
    if payload.search_mode == "local_mock":
        results = _build_local_mock_results(
            query=query,
            locations=locations,
            target_roles=target_roles,
            keywords=keywords,
            confirmed_profile=confirmed_profile,
        )
        run = search_repository.create(
            session_id=session.session_id,
            confirmed_profile_id=confirmed_profile.confirmed_profile_id,
            resume_profile_id=durable_profile.resume_profile_id if durable_profile else None,
            query=query,
            locations=locations,
            target_roles=target_roles,
            keywords=keywords,
            results=results,
            user_id=user_id or LOCAL_USER_ID,
            search_mission_id=mission.search_mission_id if mission else None,
            search_mission_revision=mission.revision if mission else None,
            mission_constraints=mission.mission.hard_constraints if mission else [],
            mission_excluded_roles=mission.mission.excluded_roles if mission else [],
            mission_ranking_priorities=mission.mission.ranking_priorities if mission else [],
        )
        updated_session = session_repository.mark_job_search_completed(session_id=session.session_id)
        return JobSearchRunResponse(
            job_search_run=run,
            profile_session=updated_session or session,
            steps=[],
        )

    selected_sources = _resolve_selected_sources(payload)
    provider_name = (
        normalize_job_search_provider_name(getattr(job_search_provider, "provider_name", None))
        if job_search_provider is not None
        else _provider_name_from_selected_sources(payload, selected_sources)
    )
    analysis_config = _resolve_job_search_analysis_config(payload)
    run = search_repository.create_pending(
        session_id=session.session_id,
        confirmed_profile_id=confirmed_profile.confirmed_profile_id,
        resume_profile_id=durable_profile.resume_profile_id if durable_profile else None,
        query=query,
        locations=locations,
        target_roles=target_roles,
        keywords=keywords,
        search_mode=payload.search_mode,
        llm_enabled=analysis_config.enabled,
        search_provider=provider_name,
        user_id=user_id or LOCAL_USER_ID,
        search_mission_id=mission.search_mission_id if mission else None,
        search_mission_revision=mission.revision if mission else None,
        mission_constraints=mission.mission.hard_constraints if mission else [],
        mission_excluded_roles=mission.mission.excluded_roles if mission else [],
        mission_ranking_priorities=mission.mission.ranking_priorities if mission else [],
    )
    steps = _create_initial_trace_steps(run.job_search_run_id, search_repository)
    run = search_repository.mark_running(run.job_search_run_id) or run
    updated_session = session_repository.mark_job_search_running(session_id=session.session_id) or session

    if background_tasks is not None:
        background_tasks.add_task(
            execute_job_search_run,
            run.job_search_run_id,
            session_repository=session_repository,
            confirmed_repository=confirmed_repository,
            search_repository=search_repository,
            job_search_provider=job_search_provider,
            llm_service=llm_service,
            analysis_mode=analysis_config.mode,
            llm_provider=analysis_config.provider,
            max_results=payload.max_results,
        )

    return JobSearchRunResponse(
        job_search_run=run,
        profile_session=updated_session,
        steps=steps,
    )


def create_browser_helper_job_search_run(
    payload: BrowserHelperJobSearchRunCreateRequest,
    *,
    user_id: str | None = None,
    background_tasks: BackgroundTasks | None = None,
    session_repository: ProfileSessionRepository = profile_session_repository,
    confirmed_repository: ConfirmedProfileRepository = confirmed_profile_repository,
    search_repository: JobSearchRepository = job_search_repository,
    llm_service: JSONChatLLM | None = None,
) -> JobSearchRunResponse:
    selected_sources = _clean_list(
        [normalize_job_search_source_name(source) for source in payload.selected_sources]
    )
    if not payload.candidates and not selected_sources:
        raise JobAgentError(
            message="Browser helper returned no candidates.",
            error_code="browser_helper_candidates_required",
            status_code=400,
        )

    raw_candidates = [_browser_helper_candidate_to_raw(candidate) for candidate in payload.candidates]
    provider = BrowserHelperPayloadProvider(
        candidates=raw_candidates,
        platforms=payload.platforms,
        helper_version=payload.helper_version,
    )
    if selected_sources:
        provider = _compose_browser_helper_provider(provider, selected_sources)
    analysis_config = _resolve_browser_helper_analysis_config(payload)
    run_response = create_job_search_run(
        JobSearchRunCreateRequest(
            session_id=payload.session_id,
            query=payload.query,
            search_mode="browser_helper",
            search_provider=provider.provider_name,
            selected_sources=payload.selected_sources,
            analysis_mode=analysis_config.mode,
            llm_provider=analysis_config.provider,
            use_llm=payload.use_llm,
            locations=payload.locations,
            target_roles=payload.target_roles,
            keywords=payload.keywords,
            max_results=payload.max_results,
        ),
        background_tasks=background_tasks,
        session_repository=session_repository,
        confirmed_repository=confirmed_repository,
        search_repository=search_repository,
        job_search_provider=provider,
        llm_service=llm_service,
        user_id=user_id,
    )
    if background_tasks is not None:
        return run_response
    return execute_job_search_run(
        run_response.job_search_run.job_search_run_id,
        session_repository=session_repository,
        confirmed_repository=confirmed_repository,
        search_repository=search_repository,
        job_search_provider=provider,
        llm_service=llm_service,
        analysis_mode=analysis_config.mode,
        llm_provider=analysis_config.provider,
        max_results=payload.max_results,
    )


def analyze_browser_job_capture(
    payload: BrowserJobCaptureRequest,
    *,
    user_id: str | None = None,
    session_repository: ProfileSessionRepository = profile_session_repository,
    confirmed_repository: ConfirmedProfileRepository = confirmed_profile_repository,
    search_repository: JobSearchRepository = job_search_repository,
    llm_service: JSONChatLLM | None = None,
) -> BrowserJobCaptureAnalyzeResponse:
    candidate = browser_job_capture_to_candidate(payload)
    run_response = create_browser_helper_job_search_run(
        BrowserHelperJobSearchRunCreateRequest(
            session_id=payload.session_id,
            query=payload.title or payload.page_title,
            helper_version=payload.extractor_version,
            platforms=[payload.source],
            analysis_mode=payload.analysis_mode,
            llm_provider=payload.llm_provider,
            use_llm=payload.use_llm,
            max_results=1,
            candidates=[candidate],
        ),
        session_repository=session_repository,
        confirmed_repository=confirmed_repository,
        search_repository=search_repository,
        llm_service=llm_service,
        user_id=user_id,
    )
    run = run_response.job_search_run
    if run.status == "failed":
        raise JobAgentError(
            message=run.error_message or "Browser job capture analysis failed.",
            error_code="browser_job_capture_analysis_failed",
            status_code=500,
        )
    if not run.results:
        raise JobAgentError(
            message="Browser job capture did not produce an analysis result.",
            error_code="browser_job_capture_no_result",
            status_code=422,
        )

    result = run.results[0]
    return BrowserJobCaptureAnalyzeResponse(
        capture=_capture_summary(payload),
        report=_browser_capture_report(result),
        warnings=_clean_list(
            payload.warnings
            + candidate.provider_warnings
            + _trace_quality_warnings(run_response.steps)
        ),
        job_search_run_id=run.job_search_run_id,
        job_result_id=result.job_result_id,
    )


def _compose_browser_helper_provider(
    helper_provider: BrowserHelperPayloadProvider,
    selected_sources: list[str],
) -> JobSearchProvider:
    providers: list[JobSearchProvider] = [
        helper_provider,
        *[resolve_job_search_provider(source) for source in selected_sources],
    ]
    provider = MultiSourceJobSearchProvider(providers)
    source_names = _clean_list(helper_provider.source_names + selected_sources)
    provider.provider_kind = "hybrid"
    provider.detail_strategy = "browser_extension_payload_plus_selected_sources"
    provider.provider_name = f"browser_helper:{','.join(source_names)}"
    provider.source_names = source_names
    return provider


def execute_job_search_run(
    run_id: str,
    *,
    session_repository: ProfileSessionRepository = profile_session_repository,
    confirmed_repository: ConfirmedProfileRepository = confirmed_profile_repository,
    search_repository: JobSearchRepository = job_search_repository,
    job_search_provider: JobSearchProvider | None = None,
    llm_service: JSONChatLLM | None = None,
    analysis_mode: str | None = None,
    llm_provider: str | None = None,
    max_results: int = 10,
) -> JobSearchRunResponse:
    run = search_repository.get(run_id)
    if run is None:
        raise JobAgentError(
            message="Job search run not found.",
            error_code="job_search_run_not_found",
            status_code=404,
        )

    confirmed_profile = confirmed_repository.get(run.confirmed_profile_id)
    if confirmed_profile is None:
        search_repository.fail_run(run_id, "Confirmed profile not found for this run.")
        raise JobAgentError(
            message="Confirmed profile not found.",
            error_code="confirmed_profile_not_found",
            status_code=404,
        )

    use_llm_analysis = _resolve_execution_analysis_enabled(run, analysis_mode=analysis_mode)
    requested_llm_provider = _resolve_execution_llm_provider(
        analysis_enabled=use_llm_analysis,
        llm_provider=llm_provider,
    )
    llm_resolution = (
        resolve_llm_provider(requested_llm_provider)
        if requested_llm_provider is not None
        else None
    )
    effective_llm_service = (
        llm_service
        if llm_service is not None
        else llm_resolution.service if llm_resolution is not None else None
    )
    provider = job_search_provider or resolve_job_search_provider(run.search_provider)
    steps = _ensure_trace_steps(run_id, search_repository)
    session_repository.mark_job_search_running(session_id=run.session_id)
    search_repository.mark_running(run_id)

    try:
        planning_step = steps[0]
        search_repository.mark_trace_step_running(
            planning_step.step_id,
            mode="llm" if use_llm_analysis else "deterministic",
            summary="Building search plan from the confirmed profile.",
            guardrails=PLANNING_GUARDRAILS,
        )
        search_plan = build_search_plan(
            confirmed_profile,
            use_llm=use_llm_analysis,
            llm_service=effective_llm_service,
        )
        search_plan = _augment_search_plan(search_plan, run)
        search_repository.complete_trace_step(
            planning_step.step_id,
            mode=search_plan.mode,
            summary=f"Prepared {len(search_plan.queries)} search querie(s).",
            fallback_reason=search_plan.fallback_reason,
            guardrails=PLANNING_GUARDRAILS,
            quality_warnings=search_plan.quality_warnings,
            details={
                "provider_queries": search_plan.queries,
                "recall_queries": _recall_queries_from_plan(search_plan),
                "ranking_signals": _ranking_signals_from_plan(search_plan),
                "target_roles": search_plan.target_roles,
                "locations": search_plan.locations,
                "planning_mode": search_plan.mode,
                "analysis_mode": "llm" if use_llm_analysis else "deterministic",
                "llm_provider": requested_llm_provider,
                "llm_configured": llm_resolution.configured if llm_resolution is not None else None,
                "timings_ms": search_plan.diagnostics.get("timings_ms", {}),
                "payload_stats": search_plan.diagnostics.get("payload_stats", {}),
            },
        )

        provider_step = steps[1]
        provider_name = getattr(provider, "provider_name", "mock")
        provider_mode = "mock" if provider_name == "mock" else "provider"
        search_repository.mark_trace_step_running(
            provider_step.step_id,
            mode=provider_mode,
            summary=f"Collecting provider-backed job candidates from {provider_name}.",
            guardrails=ASSEMBLY_GUARDRAILS,
        )
        recall_result = _run_provider_search(
            provider,
            search_plan=search_plan,
            max_results=max_results,
        )
        raw_candidates = recall_result.candidates
        search_repository.complete_trace_step(
            provider_step.step_id,
            mode=provider_mode,
            summary=(
                f"Collected {recall_result.raw_candidate_count} raw candidates from {provider_name}; "
                f"{len(raw_candidates)} remained after URL/title dedupe."
            ),
            guardrails=ASSEMBLY_GUARDRAILS,
            details=recall_result.details(),
        )

        filter_step = steps[2]
        search_repository.mark_trace_step_running(
            filter_step.step_id,
            mode="llm" if use_llm_analysis else "deterministic",
            summary="Ranking the provider candidates for profile fit.",
            guardrails=FILTER_GUARDRAILS,
        )
        filtered = filter_candidates(
            confirmed_profile,
            search_plan,
            raw_candidates,
            use_llm=use_llm_analysis,
            llm_service=effective_llm_service,
            limit=max_results,
        )
        search_repository.complete_trace_step(
            filter_step.step_id,
            mode=filtered.mode,
            summary=f"Selected {len(filtered.selected_candidates)} candidate(s) for analysis.",
            fallback_reason=filtered.fallback_reason,
            guardrails=FILTER_GUARDRAILS,
            quality_warnings=filtered.quality_warnings,
            details={
                "input_candidate_count": len(raw_candidates),
                "selected_candidate_count": len(filtered.selected_candidates),
                "selected_indexes": filtered.selected_indexes,
                "llm_request_count": 1 if use_llm_analysis and raw_candidates else 0,
                "analysis_mode": "llm" if use_llm_analysis else "deterministic",
                "llm_provider": requested_llm_provider,
                "timings_ms": filtered.diagnostics.get("timings_ms", {}),
                "payload_stats": filtered.diagnostics.get("payload_stats", {}),
                "fallback_diagnostics": filtered.diagnostics.get("fallback_diagnostics", {}),
            },
        )

        jd_step = steps[3]
        search_repository.mark_trace_step_running(
            jd_step.step_id,
            mode="llm" if use_llm_analysis else "mock",
            summary="Analyzing candidate descriptions with the JD analysis agent.",
            guardrails=ASSEMBLY_GUARDRAILS,
        )
        analyses = _analyze_candidates(
            filtered,
            use_llm=use_llm_analysis,
            llm_service=effective_llm_service,
        )
        search_repository.complete_trace_step(
            jd_step.step_id,
            mode=analyses["mode"],
            summary=f"Analyzed {len(analyses['items'])} candidate description(s).",
            fallback_reason=analyses["fallback_reason"],
            guardrails=analyses["guardrails"],
            quality_warnings=analyses["quality_warnings"],
            details={
                "analyzed_candidate_count": len(analyses["items"]),
                "llm_request_count": len(analyses["items"]) if use_llm_analysis else 0,
                "analysis_concurrency": analyses["concurrency"],
                "fallback_count": analyses["fallback_count"],
                "analysis_mode_counts": analyses["mode_counts"],
                "llm_provider": requested_llm_provider,
                "timings_ms": analyses["timings_ms"],
                "candidate_runs": analyses["candidate_runs"],
                "fallback_reasons": analyses["fallback_reasons"],
            },
        )

        matching_step = steps[4]
        matching_mode = "llm" if filtered.mode == "llm" else "deterministic"
        search_repository.mark_trace_step_running(
            matching_step.step_id,
            mode=matching_mode,
            summary="Applying candidate scorecards against analyzed candidates.",
            guardrails=ASSEMBLY_GUARDRAILS,
        )
        matched_items = _match_candidates(
            confirmed_profile,
            search_plan,
            analyses["items"],
        )
        search_repository.complete_trace_step(
            matching_step.step_id,
            mode=matching_mode,
            summary=f"Scored {len(matched_items)} candidate fit profile(s).",
            guardrails=ASSEMBLY_GUARDRAILS,
            details={
                "scored_candidate_count": len(matched_items),
                "top_scores": [int(item["match_score"]) for item in matched_items[:5]],
            },
        )

        assembly_step = steps[5]
        search_repository.mark_trace_step_running(
            assembly_step.step_id,
            mode="deterministic",
            summary="Assembling final job cards from provider-backed candidates.",
            guardrails=ASSEMBLY_GUARDRAILS,
        )
        results = _assemble_results(matched_items, source="live_search")
        completed_run = search_repository.complete_run(run_id, results) or run
        updated_session = session_repository.mark_job_search_completed(session_id=run.session_id)
        search_repository.complete_trace_step(
            assembly_step.step_id,
            mode="deterministic",
            summary=f"Assembled {len(results)} final job result(s).",
            guardrails=ASSEMBLY_GUARDRAILS,
            details={
                "final_result_count": len(results),
                "visible_top_count": min(len(results), max_results),
                "source_providers": _source_provider_counts(results),
            },
        )
        return JobSearchRunResponse(
            job_search_run=completed_run,
            profile_session=updated_session or get_profile_session(run.session_id, repository=session_repository),
            steps=search_repository.list_trace_steps(run_id),
        )
    except Exception as exc:
        failed_step = _find_running_or_pending_step(search_repository.list_trace_steps(run_id))
        if failed_step is not None:
            search_repository.fail_trace_step(
                failed_step.step_id,
                mode=failed_step.mode,
                summary=f"Step failed: {type(exc).__name__}.",
                fallback_reason=type(exc).__name__,
                guardrails=failed_step.guardrails,
                quality_warnings=failed_step.quality_warnings,
            )
        failed_run = search_repository.fail_run(run_id, str(exc) or type(exc).__name__)
        session = get_profile_session(run.session_id, repository=session_repository)
        return JobSearchRunResponse(
            job_search_run=failed_run or run,
            profile_session=session,
            steps=search_repository.list_trace_steps(run_id),
        )


def get_job_search_run(
    run_id: str,
    *,
    user_id: str | None = None,
    session_repository: ProfileSessionRepository = profile_session_repository,
    search_repository: JobSearchRepository = job_search_repository,
) -> JobSearchRunResponse:
    run = search_repository.get(run_id, user_id=user_id)
    if run is None:
        raise JobAgentError(
            message="Job search run not found.",
            error_code="job_search_run_not_found",
            status_code=404,
        )
    session = get_profile_session(run.session_id, repository=session_repository, user_id=user_id)
    return JobSearchRunResponse(
        job_search_run=run,
        profile_session=session,
        steps=search_repository.list_trace_steps(run_id),
    )


def list_job_search_trace_steps(
    run_id: str,
    *,
    user_id: str | None = None,
    search_repository: JobSearchRepository = job_search_repository,
) -> list[JobSearchTraceStep]:
    run = search_repository.get(run_id, user_id=user_id)
    if run is None:
        raise JobAgentError(
            message="Job search run not found.",
            error_code="job_search_run_not_found",
            status_code=404,
        )
    return search_repository.list_trace_steps(run_id)


def list_job_search_runs(
    session_id: str,
    *,
    user_id: str | None = None,
    session_repository: ProfileSessionRepository = profile_session_repository,
    search_repository: JobSearchRepository = job_search_repository,
) -> list[JobSearchRun]:
    get_profile_session(session_id, repository=session_repository, user_id=user_id)
    return search_repository.list_recent_by_session(session_id, user_id=user_id)


def list_user_job_search_runs(
    *,
    user_id: str,
    limit: int = 100,
    search_repository: JobSearchRepository = job_search_repository,
) -> list[JobSearchRun]:
    return search_repository.list_recent_by_user(user_id, limit=limit)


def delete_job_search_run(
    run_id: str,
    *,
    user_id: str,
    search_repository: JobSearchRepository = job_search_repository,
) -> None:
    run = search_repository.get(run_id, user_id=user_id)
    if run is None:
        raise JobAgentError(
            message="Job search run not found.",
            error_code="job_search_run_not_found",
            status_code=404,
        )
    if run.status in {"pending", "running"}:
        raise JobAgentError(
            message="A running job search cannot be deleted.",
            error_code="job_search_run_active",
            status_code=409,
        )
    if not search_repository.delete(user_id=user_id, run_id=run_id):
        raise JobAgentError(
            message="Job search run not found.",
            error_code="job_search_run_not_found",
            status_code=404,
        )


def preview_job_search_run(
    payload: JobSearchRunCreateRequest,
    *,
    user_id: str | None = None,
    session_repository: ProfileSessionRepository = profile_session_repository,
    confirmed_repository: ConfirmedProfileRepository = confirmed_profile_repository,
    llm_service: JSONChatLLM | None = None,
    mission_repository: SearchMissionRepository = search_mission_repository,
) -> JobSearchPreviewResponse:
    session = get_profile_session(payload.session_id, repository=session_repository, user_id=user_id)
    if session.confirmed_profile_id is None:
        raise JobAgentError(
            message="Confirmed profile is required before previewing job search.",
            error_code="confirmed_profile_required",
            status_code=409,
        )

    confirmed_profile = confirmed_repository.get(session.confirmed_profile_id, user_id=user_id)
    if confirmed_profile is None:
        raise JobAgentError(
            message="Confirmed profile not found.",
            error_code="confirmed_profile_not_found",
            status_code=404,
        )

    query, locations, target_roles, keywords, mission = _resolve_inputs_with_mission(
        payload,
        confirmed_profile,
        user_id=user_id or LOCAL_USER_ID,
        mission_repository=mission_repository,
    )
    analysis_config = _resolve_job_search_analysis_config(payload)
    use_llm_analysis = analysis_config.enabled
    llm_provider: str | None = analysis_config.provider
    effective_llm_service = llm_service
    if use_llm_analysis:
        llm_resolution = resolve_llm_provider(llm_provider)
        llm_provider = llm_resolution.provider
        effective_llm_service = llm_service if llm_service is not None else llm_resolution.service

    search_plan = build_search_plan(
        confirmed_profile,
        use_llm=use_llm_analysis,
        llm_service=effective_llm_service,
    )
    search_plan = _augment_search_plan_from_inputs(
        search_plan,
        query=query,
        locations=locations,
        target_roles=target_roles,
        keywords=keywords,
    )

    selected_sources = _resolve_selected_sources(payload)
    provider_name = (
        "mock"
        if payload.search_mode == "local_mock"
        else _provider_name_from_selected_sources(payload, selected_sources)
    )
    provider_search_terms, provider_search_urls = _build_provider_preview_searches(
        provider_name,
        search_plan.queries,
        selected_sources=selected_sources,
    )
    source_kind = _provider_source_kind(provider_name, payload.search_mode)
    query_budget = _estimate_query_budget(
        provider_name=provider_name,
        search_mode=payload.search_mode,
        provider_queries=search_plan.queries,
        locations=search_plan.locations,
        max_results=payload.max_results,
        llm_planning_enabled=use_llm_analysis and effective_llm_service is not None,
        llm_filtering_enabled=use_llm_analysis and effective_llm_service is not None,
        llm_analysis_enabled=use_llm_analysis and effective_llm_service is not None,
    )

    return JobSearchPreviewResponse(
        session_id=session.session_id,
        confirmed_profile_id=confirmed_profile.confirmed_profile_id,
        search_mode=payload.search_mode,
        search_provider=provider_name,
        selected_sources=selected_sources,
        llm_enabled=use_llm_analysis,
        llm_provider=llm_provider,
        analysis_mode=analysis_config.mode,
        query=query,
        locations=search_plan.locations,
        target_roles=search_plan.target_roles,
        keywords=keywords,
        provider_queries=search_plan.queries,
        search_intent=search_plan.search_intent,
        search_source_kind=source_kind,
        search_source_notes=_search_source_notes(provider_name, source_kind),
        recall_queries=_recall_queries_from_plan(search_plan),
        ranking_signals=_ranking_signals_from_plan(search_plan),
        provider_search_terms=provider_search_terms,
        provider_search_urls=provider_search_urls,
        provider_query_count=query_budget["provider_query_count"],
        estimated_provider_requests=query_budget["estimated_provider_requests"],
        estimated_candidate_pool_size=query_budget["estimated_candidate_pool_size"],
        estimated_llm_planning_requests=query_budget["estimated_llm_planning_requests"],
        estimated_llm_filtering_requests=query_budget["estimated_llm_filtering_requests"],
        estimated_llm_analysis_requests=query_budget["estimated_llm_analysis_requests"],
        estimated_total_llm_requests=query_budget["estimated_total_llm_requests"],
        query_strategy_notes=query_budget["query_strategy_notes"],
        search_signal_terms=search_plan.must_have_signals,
        excluded_signals=search_plan.avoid_signals,
        ranking_policy=search_plan.ranking_policy,
        planning_mode=search_plan.mode,
        fallback_reason=search_plan.fallback_reason,
        quality_warnings=search_plan.quality_warnings,
        search_mission_id=mission.search_mission_id if mission else None,
        search_mission_revision=mission.revision if mission else None,
        mission_constraints=mission.mission.hard_constraints if mission else [],
        mission_excluded_roles=mission.mission.excluded_roles if mission else [],
    )


def _resolve_inputs_with_mission(
    payload: JobSearchRunCreateRequest,
    confirmed_profile: ConfirmedProfile,
    *,
    user_id: str,
    mission_repository: SearchMissionRepository,
) -> tuple[str, list[str], list[str], list[str], SearchMission | None]:
    query, locations, target_roles, keywords = _resolve_search_inputs(payload, confirmed_profile)
    mission = mission_repository.get(user_id=user_id, session_id=payload.session_id)
    if mission is None or mission.status != "confirmed":
        return query, locations, target_roles, keywords, None
    interpreted = mission.mission
    resolved_roles = payload.target_roles or interpreted.target_roles or target_roles
    resolved_locations = payload.locations or interpreted.locations or locations
    mission_signals = (
        interpreted.must_have
        + interpreted.nice_to_have
        + interpreted.preferred_industries
        + interpreted.ranking_priorities
    )
    resolved_keywords = payload.keywords or mission_signals or keywords
    resolved_query = (payload.query or "").strip()
    if not resolved_query:
        resolved_query = " ".join((resolved_roles[:1] + resolved_keywords[:3])).strip() or query
    return resolved_query, resolved_locations, resolved_roles, resolved_keywords, mission


def _resolve_job_search_analysis_config(payload: JobSearchRunCreateRequest) -> JobSearchAnalysisConfig:
    if not _uses_job_search_analysis(payload.search_mode):
        return JobSearchAnalysisConfig(enabled=False)
    if payload.analysis_mode == "deterministic":
        return JobSearchAnalysisConfig(enabled=False)
    return JobSearchAnalysisConfig(
        enabled=True,
        provider=_resolve_requested_llm_provider(
            llm_provider=payload.llm_provider,
            legacy_use_llm=payload.use_llm,
        ),
    )


def _resolve_browser_helper_analysis_config(
    payload: BrowserHelperJobSearchRunCreateRequest,
) -> JobSearchAnalysisConfig:
    if payload.analysis_mode == "deterministic":
        return JobSearchAnalysisConfig(enabled=False)
    return JobSearchAnalysisConfig(
        enabled=True,
        provider=_resolve_requested_llm_provider(
            llm_provider=payload.llm_provider,
            legacy_use_llm=payload.use_llm,
        ),
    )


def _resolve_requested_llm_provider(
    *,
    llm_provider: str | None,
    legacy_use_llm: bool | None,
) -> LLMProviderName:
    if llm_provider is not None:
        return normalize_llm_provider(llm_provider)
    if legacy_use_llm is not None:
        return "deepseek" if legacy_use_llm else "ollama"
    return DEFAULT_LLM_PROVIDER


def _resolve_execution_analysis_enabled(
    run: JobSearchRun,
    *,
    analysis_mode: str | None,
) -> bool:
    if not _uses_job_search_analysis(run.search_mode):
        return False
    if analysis_mode is not None:
        return analysis_mode == "llm"
    return run.llm_enabled


def _resolve_execution_llm_provider(
    *,
    analysis_enabled: bool,
    llm_provider: str | None,
) -> LLMProviderName | None:
    if not analysis_enabled:
        return None
    if llm_provider is not None:
        return normalize_llm_provider(llm_provider)
    return DEFAULT_LLM_PROVIDER


def _clean_list(values: list[str]) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = str(value).strip()
        if not item:
            continue
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(item)
    return cleaned
