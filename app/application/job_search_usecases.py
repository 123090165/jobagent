from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from uuid import NAMESPACE_URL, uuid5

from fastapi import BackgroundTasks

from app.agents.jd_analysis_agent import run_jd_analysis_agent
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
from app.schemas.confirmed_profile import ConfirmedProfile
from app.schemas.job_search import (
    BrowserHelperJobCandidate,
    BrowserHelperJobSearchRunCreateRequest,
    JobSearchResult,
    JobSearchPreviewResponse,
    JobSearchRun,
    JobSearchRunCreateRequest,
    JobSearchRunResponse,
    JobSearchTraceStep,
)
from app.services.errors import JobAgentError
from app.services.job_candidate_filter import (
    CandidateFilterResult,
    CandidateScorecard,
    filter_candidates,
)
from app.services.job_search_planner import (
    JobSearchPlan,
    build_focused_provider_queries,
    build_search_plan,
)
from app.services.job_search_recall_metrics import (
    build_source_recall_stats,
    candidate_recall_key,
)
from app.services.job_search_providers import (
    BrowserHelperPayloadProvider,
    JobSearchProvider,
    RawJobCandidate,
    encode_selected_sources,
    normalize_job_search_provider_name,
    normalize_job_search_source_name,
    resolve_job_search_provider,
    selected_sources_from_provider_name,
)
from app.services.job_search_providers.cuhksz_career_provider import (
    build_cuhksz_search_url,
    build_cuhksz_title_terms,
)
from app.services.job_search_providers.serper_web_provider import (
    build_serper_preview_search_url,
    configured_serper_search_sites,
)
from app.services.job_search_providers.remoteok_provider import REMOTEOK_API_URL
from app.services.llm_provider import JSONChatLLM, resolve_llm_provider_for_switch

TRACE_STEP_NAMES = [
    "Search planning",
    "Provider search",
    "Candidate filtering",
    "JD analysis",
    "Profile matching",
    "Result assembly",
]

PLANNING_GUARDRAILS = [
    "Only derive job search intent from the confirmed profile.",
    "Do not invent missing work history, domain experience, or credentials.",
]
FILTER_GUARDRAILS = [
    "Only rank candidates returned by the search provider.",
    "Do not create or merge candidates.",
]
ASSEMBLY_GUARDRAILS = [
    "Only return jobs backed by provider results and source metadata.",
    "Do not invent source URLs or provider names.",
]
MAX_PROVIDER_QUERIES_PER_RUN = 3
MAX_PROVIDER_LOCATIONS_PER_RUN = 3
MAX_PROVIDER_PREVIEW_TERMS = 8


@dataclass
class ProviderQueryStat:
    query: str
    location: str | None
    requested_limit: int
    returned_count: int
    new_candidate_count: int
    source_count: int = 1
    logical_request_count: int = 1

    def to_dict(self) -> dict[str, object]:
        return {
            "query": self.query,
            "location": self.location,
            "requested_limit": self.requested_limit,
            "returned_count": self.returned_count,
            "new_candidate_count": self.new_candidate_count,
            "source_count": self.source_count,
            "logical_request_count": self.logical_request_count,
        }


@dataclass
class ProviderRecallResult:
    candidates: list[RawJobCandidate]
    provider_name: str
    provider_kind: str
    query_stats: list[ProviderQueryStat] = field(default_factory=list)
    raw_candidates: list[RawJobCandidate] = field(default_factory=list, repr=False)
    raw_candidate_count: int = 0
    duplicate_count: int = 0
    truncated_candidate_count: int = 0
    candidate_pool_cap: int = 0

    def details(self) -> dict[str, object]:
        source_stats = build_source_recall_stats(self.raw_candidates, self.candidates)
        return {
            "provider": self.provider_name,
            "source_kind": self.provider_kind,
            "selected_sources": selected_sources_from_provider_name(self.provider_name),
            "source_candidate_counts": dict(Counter(candidate.source_provider for candidate in self.candidates)),
            "source_stats": [item.to_dict() for item in source_stats],
            "query_count": len(self.query_stats),
            "logical_provider_call_count": sum(item.logical_request_count for item in self.query_stats),
            "raw_candidate_count": self.raw_candidate_count,
            "duplicate_count": self.duplicate_count,
            "truncated_candidate_count": self.truncated_candidate_count,
            "deduped_candidate_count": len(self.candidates),
            "missing_source_url_count": sum(item.missing_url_count for item in source_stats),
            "missing_detail_count": sum(item.missing_detail_count for item in source_stats),
            "candidate_pool_cap": self.candidate_pool_cap,
            "query_stats": [item.to_dict() for item in self.query_stats],
        }


def create_job_search_run(
    payload: JobSearchRunCreateRequest,
    *,
    background_tasks: BackgroundTasks | None = None,
    session_repository: ProfileSessionRepository = profile_session_repository,
    confirmed_repository: ConfirmedProfileRepository = confirmed_profile_repository,
    search_repository: JobSearchRepository = job_search_repository,
    job_search_provider: JobSearchProvider | None = None,
    llm_service: JSONChatLLM | None = None,
) -> JobSearchRunResponse:
    session = get_profile_session(payload.session_id, repository=session_repository)
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

    confirmed_profile = confirmed_repository.get(session.confirmed_profile_id)
    if confirmed_profile is None:
        raise JobAgentError(
            message="Confirmed profile not found.",
            error_code="confirmed_profile_not_found",
            status_code=404,
        )

    query, locations, target_roles, keywords = _resolve_search_inputs(payload, confirmed_profile)
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
            query=query,
            locations=locations,
            target_roles=target_roles,
            keywords=keywords,
            results=results,
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
    run = search_repository.create_pending(
        session_id=session.session_id,
        confirmed_profile_id=confirmed_profile.confirmed_profile_id,
        query=query,
        locations=locations,
        target_roles=target_roles,
        keywords=keywords,
        search_mode=payload.search_mode,
        llm_enabled=payload.use_llm,
        search_provider=provider_name,
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
    session_repository: ProfileSessionRepository = profile_session_repository,
    confirmed_repository: ConfirmedProfileRepository = confirmed_profile_repository,
    search_repository: JobSearchRepository = job_search_repository,
    llm_service: JSONChatLLM | None = None,
) -> JobSearchRunResponse:
    if not payload.candidates:
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
    run_response = create_job_search_run(
        JobSearchRunCreateRequest(
            session_id=payload.session_id,
            query=payload.query,
            search_mode="browser_helper",
            search_provider=provider.provider_name,
            selected_sources=[],
            use_llm=payload.use_llm,
            locations=payload.locations,
            target_roles=payload.target_roles,
            keywords=payload.keywords,
            max_results=payload.max_results,
        ),
        background_tasks=None,
        session_repository=session_repository,
        confirmed_repository=confirmed_repository,
        search_repository=search_repository,
        job_search_provider=provider,
        llm_service=llm_service,
    )
    return execute_job_search_run(
        run_response.job_search_run.job_search_run_id,
        session_repository=session_repository,
        confirmed_repository=confirmed_repository,
        search_repository=search_repository,
        job_search_provider=provider,
        llm_service=llm_service,
        max_results=payload.max_results,
    )


def execute_job_search_run(
    run_id: str,
    *,
    session_repository: ProfileSessionRepository = profile_session_repository,
    confirmed_repository: ConfirmedProfileRepository = confirmed_profile_repository,
    search_repository: JobSearchRepository = job_search_repository,
    job_search_provider: JobSearchProvider | None = None,
    llm_service: JSONChatLLM | None = None,
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

    llm_resolution = resolve_llm_provider_for_switch(use_deepseek=run.llm_enabled)
    effective_llm_service = llm_service if llm_service is not None else llm_resolution.service
    use_llm_analysis = run.search_mode == "live_search"
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
    session_repository: ProfileSessionRepository = profile_session_repository,
    search_repository: JobSearchRepository = job_search_repository,
) -> JobSearchRunResponse:
    run = search_repository.get(run_id)
    if run is None:
        raise JobAgentError(
            message="Job search run not found.",
            error_code="job_search_run_not_found",
            status_code=404,
        )
    session = get_profile_session(run.session_id, repository=session_repository)
    return JobSearchRunResponse(
        job_search_run=run,
        profile_session=session,
        steps=search_repository.list_trace_steps(run_id),
    )


def list_job_search_trace_steps(
    run_id: str,
    *,
    search_repository: JobSearchRepository = job_search_repository,
) -> list[JobSearchTraceStep]:
    run = search_repository.get(run_id)
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
    session_repository: ProfileSessionRepository = profile_session_repository,
    search_repository: JobSearchRepository = job_search_repository,
) -> list[JobSearchRun]:
    get_profile_session(session_id, repository=session_repository)
    return search_repository.list_recent_by_session(session_id)


def preview_job_search_run(
    payload: JobSearchRunCreateRequest,
    *,
    session_repository: ProfileSessionRepository = profile_session_repository,
    confirmed_repository: ConfirmedProfileRepository = confirmed_profile_repository,
    llm_service: JSONChatLLM | None = None,
) -> JobSearchPreviewResponse:
    session = get_profile_session(payload.session_id, repository=session_repository)
    if session.confirmed_profile_id is None:
        raise JobAgentError(
            message="Confirmed profile is required before previewing job search.",
            error_code="confirmed_profile_required",
            status_code=409,
        )

    confirmed_profile = confirmed_repository.get(session.confirmed_profile_id)
    if confirmed_profile is None:
        raise JobAgentError(
            message="Confirmed profile not found.",
            error_code="confirmed_profile_not_found",
            status_code=404,
        )

    query, locations, target_roles, keywords = _resolve_search_inputs(payload, confirmed_profile)
    use_llm_analysis = payload.search_mode == "live_search"
    llm_provider: str | None = None
    effective_llm_service = llm_service
    if use_llm_analysis:
        llm_resolution = resolve_llm_provider_for_switch(use_deepseek=payload.use_llm)
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
        llm_enabled=payload.use_llm,
        llm_provider=llm_provider,
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
    )


def _resolve_search_inputs(
    payload: JobSearchRunCreateRequest,
    confirmed_profile: ConfirmedProfile,
) -> tuple[str, list[str], list[str], list[str]]:
    locations = _clean_list(payload.locations) or _clean_list(confirmed_profile.preferred_locations)
    target_roles = _clean_list(payload.target_roles) or _clean_list(confirmed_profile.target_roles)
    keywords = (
        _clean_list(payload.keywords)
        or _clean_list(confirmed_profile.search_keywords)
        or _clean_list(confirmed_profile.core_skills)
    )
    query = (payload.query or "").strip()
    if not query:
        query = (target_roles[0] if target_roles else " ".join(keywords[:3])).strip()
    if not query:
        query = "Software Engineer"
    return query, locations, target_roles, keywords


def _resolve_selected_sources(payload: JobSearchRunCreateRequest) -> list[str]:
    if payload.search_mode == "local_mock":
        return []
    if payload.selected_sources:
        return _clean_list([normalize_job_search_source_name(source) for source in payload.selected_sources])
    provider_name = normalize_job_search_provider_name(payload.search_provider)
    provider_sources = selected_sources_from_provider_name(provider_name)
    if provider_sources:
        return provider_sources
    if provider_name == "multi_source":
        return ["cuhksz_career"]
    return []


def _provider_name_from_selected_sources(
    payload: JobSearchRunCreateRequest,
    selected_sources: list[str],
) -> str:
    if selected_sources:
        return encode_selected_sources(selected_sources)
    return normalize_job_search_provider_name(payload.search_provider)


def _build_provider_preview_searches(
    provider_name: str | None,
    provider_queries: list[str],
    *,
    selected_sources: list[str] | None = None,
) -> tuple[list[str], list[str]]:
    if selected_sources and (provider_name or "").startswith("multi_source:"):
        terms: list[str] = []
        urls: list[str] = []
        for source in selected_sources:
            source_terms, source_urls = _build_provider_preview_searches(
                source,
                provider_queries,
                selected_sources=None,
            )
            terms.extend(source_terms)
            urls.extend(source_urls)
        return _clean_list(terms)[:MAX_PROVIDER_PREVIEW_TERMS * max(1, len(selected_sources))], _clean_list(urls)
    if provider_name == "linkedin":
        queries = _clean_list(provider_queries)[:MAX_PROVIDER_QUERIES_PER_RUN]
        return queries, [
            build_serper_preview_search_url(query, search_sites=["linkedin.com/jobs"])
            for query in queries
        ]
    if provider_name == "remoteok":
        queries = _clean_list(provider_queries)[:MAX_PROVIDER_QUERIES_PER_RUN]
        return queries, [REMOTEOK_API_URL]
    if provider_name == "serper_web":
        queries = _clean_list(provider_queries)[:MAX_PROVIDER_QUERIES_PER_RUN]
        sites = configured_serper_search_sites()
        return queries, [
            build_serper_preview_search_url(query, search_sites=sites)
            for query in queries
        ]
    if provider_name != "cuhksz_career":
        return [], []
    terms: list[str] = []
    for query in provider_queries[:MAX_PROVIDER_QUERIES_PER_RUN]:
        terms.extend(build_cuhksz_title_terms(query))
    terms = _clean_list(terms)[:MAX_PROVIDER_PREVIEW_TERMS]
    return terms, [build_cuhksz_search_url(term) for term in terms]


def _provider_source_kind(provider_name: str | None, search_mode: str) -> str:
    if search_mode == "local_mock" or provider_name == "mock":
        return "mock"
    if search_mode == "browser_helper" or (provider_name or "").startswith("browser_helper"):
        return "browser_helper"
    if (provider_name or "").startswith("multi_source:") or provider_name == "multi_source":
        return "hybrid"
    if provider_name in {"serper_web", "linkedin"}:
        return "search_engine"
    if provider_name == "remoteok":
        return "native_api"
    if provider_name == "cuhksz_career":
        return "native_job_board"
    return "direct_crawler"


def _search_source_notes(provider_name: str | None, source_kind: str) -> list[str]:
    if source_kind == "mock":
        return ["Local mock source; no external search is executed."]
    if provider_name == "serper_web":
        return [
            "Search engine discovery broadens recall by finding public job pages and keeping source links.",
            "Result snippets are retained even when a detail page is not fetched.",
            "Optional site filters come from JOBAGENT_WEB_SEARCH_SITES, not hardcoded platform logic.",
        ]
    if provider_name == "cuhksz_career":
        return [
            "Native job board search uses short recall terms for provider-side retrieval.",
            "Profile-specific skills are treated as ranking signals instead of mandatory title keywords.",
            "Detail pages are fetched when the provider exposes stable public links.",
        ]
    if provider_name == "linkedin":
        return [
            "LinkedIn is used as search-engine discovery only.",
            "Profile pages and broad LinkedIn list pages are filtered out.",
            "Result links are preserved for the user to open; detail scraping is not performed.",
        ]
    if provider_name == "remoteok":
        return [
            "RemoteOK uses its public JSON API rather than HTML search-page scraping.",
            "RemoteOK source links and attribution warnings are preserved.",
        ]
    if provider_name == "multi_source" or (provider_name or "").startswith("multi_source:"):
        return [
            "Selected sources are searched as one candidate pool.",
            "CUHKSZ uses direct public list/detail crawling, LinkedIn uses external-link discovery, and RemoteOK uses its public API.",
            "Each candidate keeps its own source provider for downstream ranking and display.",
        ]
    return [
        "Provider is treated as a pluggable direct crawler/search source.",
        "Candidate preservation and downstream ranking use the shared provider contract.",
    ]


def _estimate_query_budget(
    *,
    provider_name: str,
    search_mode: str,
    provider_queries: list[str],
    locations: list[str],
    max_results: int,
    llm_planning_enabled: bool,
    llm_filtering_enabled: bool,
    llm_analysis_enabled: bool,
) -> dict[str, object]:
    if search_mode == "local_mock" or provider_name == "mock":
        return {
            "provider_query_count": 0,
            "estimated_provider_requests": 0,
            "estimated_candidate_pool_size": 0,
            "estimated_llm_planning_requests": 0,
            "estimated_llm_filtering_requests": 0,
            "estimated_llm_analysis_requests": 0,
            "estimated_total_llm_requests": 0,
            "query_strategy_notes": ["Local mock search does not call external providers or LLMs."],
        }

    executable_queries = _clean_list(provider_queries)[:MAX_PROVIDER_QUERIES_PER_RUN]
    executable_locations = _effective_provider_locations(provider_name, locations)
    per_call_limit = max(1, min(max_results, 5))
    source_count = max(1, len(selected_sources_from_provider_name(provider_name)))
    candidate_pool_size = min(
        max_results * 2,
        len(executable_queries) * len(executable_locations) * per_call_limit * source_count,
    )
    list_request_count = len(executable_queries) * len(executable_locations) * source_count
    notes = [
        f"Provider search executes at most {MAX_PROVIDER_QUERIES_PER_RUN} provider query groups.",
        f"Candidate pool is capped at roughly 2x max_results before filtering.",
    ]
    detail_request_count = 0

    if provider_name == "cuhksz_career":
        title_terms: list[str] = []
        for query in executable_queries:
            title_terms.extend(build_cuhksz_title_terms(query))
        unique_title_terms = _clean_list(title_terms)
        list_request_count = len(unique_title_terms)
        detail_request_count = candidate_pool_size
        notes.append("CUHKSZ expands provider queries into deduped title search terms.")
        notes.append("CUHKSZ location preferences are used for ranking context, not repeated live URL calls.")
    elif provider_name in {"serper_web", "linkedin"}:
        notes.append("Search engine discovery keeps provider queries broad and preserves public result links.")
        if provider_name == "linkedin":
            notes.append("LinkedIn discovery filters out profile pages and broad list pages.")
        elif configured_serper_search_sites():
            notes.append("Search engine site filters are loaded from JOBAGENT_WEB_SEARCH_SITES.")
        else:
            notes.append("No search engine site filter is configured; results may be broader.")
    elif provider_name == "remoteok":
        list_request_count = 1
        notes.append("RemoteOK uses its public JSON API and filters the returned feed locally.")
    elif provider_name == "multi_source" or provider_name.startswith("multi_source:"):
        selected_sources = selected_sources_from_provider_name(provider_name)
        list_request_count = 0
        detail_request_count = 0
        for source in selected_sources:
            if source == "cuhksz_career":
                title_terms = []
                for query in executable_queries:
                    title_terms.extend(build_cuhksz_title_terms(query))
                list_request_count += len(_clean_list(title_terms))
                detail_request_count += candidate_pool_size
            elif source == "remoteok":
                list_request_count += 1
            else:
                list_request_count += len(executable_queries) * len(executable_locations)
        notes.append("Multi-source search runs selected providers into one deduped candidate pool.")
        notes.append("LinkedIn candidates are external links; CUHKSZ and RemoteOK can provide structured details.")

    estimated_provider_requests = list_request_count + detail_request_count
    notes.append(
        f"Estimated provider requests split: search/list {list_request_count}, detail {detail_request_count}."
    )
    planning_requests = 1 if llm_planning_enabled else 0
    filtering_requests = 1 if llm_filtering_enabled and candidate_pool_size else 0
    analysis_requests = min(max_results, candidate_pool_size) if llm_analysis_enabled else 0
    total_llm_requests = planning_requests + filtering_requests + analysis_requests
    return {
        "provider_query_count": len(executable_queries),
        "estimated_provider_requests": estimated_provider_requests,
        "estimated_candidate_pool_size": candidate_pool_size,
        "estimated_llm_planning_requests": planning_requests,
        "estimated_llm_filtering_requests": filtering_requests,
        "estimated_llm_analysis_requests": analysis_requests,
        "estimated_total_llm_requests": total_llm_requests,
        "query_strategy_notes": notes,
    }


def _build_local_mock_results(
    *,
    query: str,
    locations: list[str],
    target_roles: list[str],
    keywords: list[str],
    confirmed_profile: ConfirmedProfile,
) -> list[JobSearchResult]:
    role_catalog = [
        {
            "role": "Backend Engineer",
            "company": "Maple Stack",
            "description": "Build internal APIs, data services, and workflow automation for product teams.",
            "signals": ["python", "fastapi", "sql", "api", "backend"],
            "risks": ["May expect deeper database tuning experience."],
        },
        {
            "role": "AI Application Engineer",
            "company": "Northstar Agents",
            "description": "Ship agent workflows, prompt tooling, and retrieval-backed internal assistants.",
            "signals": ["llm", "rag", "agent", "evaluation", "prompt"],
            "risks": ["May expect hands-on evaluation and prompt iteration examples."],
        },
        {
            "role": "Data Engineer",
            "company": "Riverlane Metrics",
            "description": "Maintain ETL pipelines, analytics datasets, and platform data contracts.",
            "signals": ["sql", "python", "etl", "data", "warehouse"],
            "risks": ["May expect stronger pipeline orchestration evidence."],
        },
        {
            "role": "Embedded Software Engineer",
            "company": "Harbor Embedded",
            "description": "Develop firmware-adjacent services and device integration tooling.",
            "signals": ["stm32", "rtos", "embedded", "c++", "uart"],
            "risks": ["May expect hardware bring-up or board-level debugging examples."],
        },
        {
            "role": "Full Stack Developer",
            "company": "Cedar Product Studio",
            "description": "Deliver end-to-end product features across API and frontend surfaces.",
            "signals": ["vue", "typescript", "python", "api", "product"],
            "risks": ["Role may lean more frontend than the profile prefers."],
        },
        {
            "role": "Platform Engineer",
            "company": "Granite Cloud",
            "description": "Improve developer workflows, service deployment, and internal platform reliability.",
            "signals": ["docker", "ci", "testing", "platform", "python"],
            "risks": ["May expect production infrastructure ownership examples."],
        },
    ]
    normalized_keywords = _clean_list(
        keywords + confirmed_profile.core_skills + confirmed_profile.supporting_skills
    )
    normalized_roles = _clean_list(target_roles)
    derived_locations = locations or ["Remote", "Tokyo", "Shenzhen"]

    results: list[JobSearchResult] = []
    for index, item in enumerate(role_catalog):
        matched_keywords = [
            keyword
            for keyword in normalized_keywords
            if any(signal in keyword.lower() or keyword.lower() in signal for signal in item["signals"])
        ]
        role_match = any(
            item["role"].lower() in role.lower() or role.lower() in item["role"].lower()
            for role in normalized_roles
        )
        if role_match and item["role"] not in normalized_roles:
            matched_keywords = matched_keywords or [item["role"]]
        score = min(95, 60 + len(matched_keywords) * 5 + (10 if role_match else 0))
        match_reasons = []
        if role_match:
            match_reasons.append(f"Target role overlap with {item['role']}.")
        if matched_keywords:
            match_reasons.append("Matched keywords: " + ", ".join(matched_keywords[:4]) + ".")
        if confirmed_profile.work_arrangements:
            match_reasons.append("Can be filtered later by preferred work arrangements.")
        if not match_reasons:
            match_reasons.append("Broad software profile alignment from confirmed profile.")

        location = derived_locations[index % len(derived_locations)]
        result_id = str(uuid5(NAMESPACE_URL, f"{query}:{item['role']}:{item['company']}:{location}"))
        results.append(
            JobSearchResult(
                job_result_id=result_id,
                title=item["role"],
                company=item["company"],
                location=location,
                source="local_mock",
                source_provider="local_mock",
                source_url=None,
                raw_snippet=item["description"],
                description=item["description"],
                matched_keywords=matched_keywords[:6],
                match_reasons=match_reasons,
                risks=item["risks"],
                match_score=score,
                recommended_action="Review fit, then tailor resume bullets before applying.",
                analysis_mode="mock",
                confidence_label=_confidence_label_for_score(score),
            )
        )

    results.sort(key=lambda item: item.match_score, reverse=True)
    return results[:6]


def _create_initial_trace_steps(
    run_id: str,
    repository: JobSearchRepository,
) -> list[JobSearchTraceStep]:
    return [
        repository.create_trace_step(
            job_search_run_id=run_id,
            step_index=index + 1,
            name=name,
            status="pending",
            mode="deterministic",
            summary="Queued.",
        )
        for index, name in enumerate(TRACE_STEP_NAMES)
    ]


def _ensure_trace_steps(run_id: str, repository: JobSearchRepository) -> list[JobSearchTraceStep]:
    steps = repository.list_trace_steps(run_id)
    if steps:
        return steps
    return _create_initial_trace_steps(run_id, repository)


def _augment_search_plan(plan: JobSearchPlan, run: JobSearchRun) -> JobSearchPlan:
    return _augment_search_plan_from_inputs(
        plan,
        query=run.query,
        locations=run.locations,
        target_roles=run.target_roles,
        keywords=run.keywords,
    )


def _augment_search_plan_from_inputs(
    plan: JobSearchPlan,
    *,
    query: str,
    locations: list[str],
    target_roles: list[str],
    keywords: list[str],
) -> JobSearchPlan:
    input_queries = build_focused_provider_queries(target_roles, keywords)
    queries = _clean_list([query] + input_queries + plan.queries)
    merged_locations = _clean_list(locations + plan.locations)
    merged_roles = _clean_list(target_roles + plan.target_roles)
    must_have = _clean_list(keywords + plan.must_have_signals)
    return plan.model_copy(
        update={
            "queries": queries,
            "locations": merged_locations,
            "target_roles": merged_roles,
            "must_have_signals": must_have,
        }
    )


def _run_provider_search(
    provider: JobSearchProvider,
    *,
    search_plan: JobSearchPlan,
    max_results: int,
) -> ProviderRecallResult:
    provider_name = getattr(provider, "provider_name", "mock")
    provider_kind = getattr(provider, "provider_kind", _provider_source_kind(provider_name, "live_search"))
    queries = search_plan.queries[: max(1, min(len(search_plan.queries), MAX_PROVIDER_QUERIES_PER_RUN))]
    locations = _effective_provider_locations(provider_name, search_plan.locations)
    per_call_limit = max(1, min(max_results, 5))
    candidate_pool_cap = max_results * 2
    if provider_kind == "browser_helper":
        query = queries[0] if queries else ""
        location = locations[0] if locations else None
        returned = provider.search_jobs(query=query, location=location, limit=candidate_pool_cap)
        deduped: dict[str, RawJobCandidate] = {}
        duplicate_count = 0
        truncated_candidate_count = 0
        for candidate in returned:
            key = candidate_recall_key(candidate)
            if key in deduped:
                duplicate_count += 1
                continue
            if len(deduped) >= candidate_pool_cap:
                truncated_candidate_count += 1
                continue
            deduped[key] = candidate
        return ProviderRecallResult(
            candidates=list(deduped.values()),
            provider_name=provider_name,
            provider_kind=provider_kind,
            query_stats=[
                ProviderQueryStat(
                    query=query,
                    location=location,
                    requested_limit=candidate_pool_cap,
                    returned_count=len(returned),
                    new_candidate_count=len(deduped),
                    source_count=_provider_source_count(provider, provider_name),
                    logical_request_count=1,
                )
            ],
            raw_candidates=returned,
            raw_candidate_count=len(returned),
            duplicate_count=duplicate_count,
            truncated_candidate_count=truncated_candidate_count,
            candidate_pool_cap=candidate_pool_cap,
        )
    deduped: dict[str, RawJobCandidate] = {}
    seen_keys: set[str] = set()
    stats: list[ProviderQueryStat] = []
    raw_candidates: list[RawJobCandidate] = []
    raw_candidate_count = 0
    duplicate_count = 0
    truncated_candidate_count = 0
    source_count = _provider_source_count(provider, provider_name)
    for query in queries:
        for location in locations:
            before_count = len(deduped)
            returned = provider.search_jobs(query=query, location=location, limit=per_call_limit)
            raw_candidates.extend(returned)
            raw_candidate_count += len(returned)
            for candidate in returned:
                key = candidate_recall_key(candidate)
                if key in seen_keys:
                    duplicate_count += 1
                    continue
                seen_keys.add(key)
                if len(deduped) >= candidate_pool_cap:
                    truncated_candidate_count += 1
                else:
                    deduped[key] = candidate
            stats.append(
                ProviderQueryStat(
                    query=query,
                    location=location,
                    requested_limit=per_call_limit,
                    returned_count=len(returned),
                    new_candidate_count=max(0, len(deduped) - before_count),
                    source_count=source_count,
                    logical_request_count=source_count,
                )
            )
            if len(deduped) >= candidate_pool_cap:
                break
        if len(deduped) >= candidate_pool_cap:
            break
    return ProviderRecallResult(
        candidates=list(deduped.values())[:candidate_pool_cap],
        provider_name=provider_name,
        provider_kind=provider_kind,
        query_stats=stats,
        raw_candidates=raw_candidates,
        raw_candidate_count=raw_candidate_count,
        duplicate_count=duplicate_count,
        truncated_candidate_count=truncated_candidate_count,
        candidate_pool_cap=candidate_pool_cap,
    )


def _provider_source_count(provider: JobSearchProvider, provider_name: str) -> int:
    source_names = getattr(provider, "source_names", None)
    if isinstance(source_names, list) and source_names:
        return len(source_names)
    return max(1, len(selected_sources_from_provider_name(provider_name)) or 1)


def _effective_provider_locations(provider_name: str | None, locations: list[str]) -> list[str | None]:
    if provider_name == "cuhksz_career":
        return [None]
    if provider_name in {"remoteok", "linkedin"}:
        return locations[:1] or [None]
    if provider_name == "multi_source" or (provider_name or "").startswith("multi_source:"):
        return locations[:1] or [None]
    return locations[:MAX_PROVIDER_LOCATIONS_PER_RUN] or [None]


def _analyze_candidates(
    filtered: CandidateFilterResult,
    *,
    use_llm: bool,
    llm_service: JSONChatLLM | None,
) -> dict[str, object]:
    items: list[dict[str, object]] = []
    mode_counter: Counter[str] = Counter()
    guardrails: list[str] = []
    quality_warnings: list[str] = []
    fallback_reason: str | None = None
    scorecards_by_index = {scorecard.candidate_index: scorecard for scorecard in filtered.scorecards}
    for candidate_index, candidate in zip(filtered.selected_indexes, filtered.selected_candidates):
        text = candidate.raw_description or candidate.snippet
        result = run_jd_analysis_agent(
            text,
            use_llm=use_llm,
            service=llm_service,  # type: ignore[arg-type]
        )
        metadata = result.metadata
        mode_counter[metadata.mode] += 1
        if metadata.fallback_reason and fallback_reason is None:
            fallback_reason = metadata.fallback_reason
        for item in metadata.guardrails:
            if item not in guardrails:
                guardrails.append(item)
        for item in metadata.quality_warnings:
            if item not in quality_warnings:
                quality_warnings.append(item)
        items.append(
            {
                "candidate": candidate,
                "analysis": result.output,
                "analysis_mode": metadata.mode,
                "scorecard": scorecards_by_index.get(candidate_index),
            }
        )
    return {
        "items": items,
        "mode": _summarize_analysis_mode(mode_counter),
        "fallback_reason": fallback_reason,
        "guardrails": guardrails,
        "quality_warnings": quality_warnings + filtered.quality_warnings,
    }


def _summarize_analysis_mode(mode_counter: Counter[str]) -> str:
    if not mode_counter:
        return "mock"
    if mode_counter.get("fallback"):
        return "fallback"
    if mode_counter.get("llm"):
        return "llm"
    return "mock"


def _match_candidates(
    confirmed_profile: ConfirmedProfile,
    search_plan: JobSearchPlan,
    analyzed_items: list[dict[str, object]],
) -> list[dict[str, object]]:
    profile_terms = _clean_list(
        confirmed_profile.target_roles
        + confirmed_profile.search_keywords
        + confirmed_profile.core_skills
        + confirmed_profile.supporting_skills
        + search_plan.must_have_signals
    )
    target_roles = [item.lower() for item in _clean_list(confirmed_profile.target_roles + search_plan.target_roles)]

    matched_items: list[dict[str, object]] = []
    for item in analyzed_items:
        candidate = item["candidate"]
        analysis = item["analysis"]
        scorecard = item.get("scorecard")
        if isinstance(scorecard, CandidateScorecard):
            matched_items.append(
                {
                    "candidate": candidate,
                    "analysis": analysis,
                    "analysis_mode": item["analysis_mode"],
                    "match_score": scorecard.match_score,
                    "score_breakdown": scorecard.score_breakdown,
                    "evidence_quotes": scorecard.evidence_quotes,
                    "matched_keywords": scorecard.matched_keywords[:6],
                    "match_reasons": (
                        scorecard.match_reasons
                        or ["Candidate was selected by the shared LLM scoring rubric."]
                    ),
                    "risks": _clean_list(scorecard.risks + _metadata_risks(candidate, confirmed_profile)),
                    "confidence_label": scorecard.confidence_label,
                }
            )
            continue
        text_parts = [
            getattr(candidate, "title", "") or "",
            getattr(candidate, "company", "") or "",
            getattr(candidate, "location", "") or "",
            getattr(candidate, "snippet", "") or "",
            getattr(analysis, "raw_jd", "") or "",
            " ".join(getattr(analysis, "keywords", []) or []),
            " ".join(getattr(analysis, "required_skills", []) or []),
            " ".join(getattr(analysis, "preferred_skills", []) or []),
        ]
        combined_text = " ".join(text_parts).lower()
        matched_keywords = [term for term in profile_terms if term.lower() in combined_text]
        role_overlap = any(role in combined_text for role in target_roles)
        required_skill_count = len(set(matched_keywords))
        score = min(98, 45 + required_skill_count * 7 + (15 if role_overlap else 0))
        risks = []
        if not getattr(candidate, "source_url", None):
            risks.append("Source URL is missing.")
        if not matched_keywords:
            risks.append("Limited explicit keyword overlap with the confirmed profile.")
        if getattr(candidate, "location", None) is None and confirmed_profile.preferred_locations:
            risks.append("Location metadata is incomplete.")

        match_reasons = []
        if role_overlap:
            match_reasons.append("Target role language overlaps with the confirmed profile.")
        if matched_keywords:
            match_reasons.append("Matched profile signals: " + ", ".join(matched_keywords[:5]) + ".")
        if not match_reasons:
            match_reasons.append("Candidate remains in scope based on broad search-plan alignment.")

        matched_items.append(
            {
                "candidate": candidate,
                "analysis": analysis,
                "analysis_mode": item["analysis_mode"],
                "match_score": score,
                "score_breakdown": {},
                "evidence_quotes": [],
                "matched_keywords": matched_keywords[:6],
                "match_reasons": match_reasons,
                "risks": _clean_list(risks),
                "confidence_label": _confidence_label_for_score(score),
            }
        )

    matched_items.sort(key=lambda item: int(item["match_score"]), reverse=True)
    return matched_items


def _assemble_results(
    matched_items: list[dict[str, object]],
    *,
    source: str,
) -> list[JobSearchResult]:
    results: list[JobSearchResult] = []
    for item in matched_items:
        candidate = item["candidate"]
        analysis = item["analysis"]
        description = getattr(candidate, "snippet", None) or getattr(analysis, "raw_jd", "")
        source_url = getattr(candidate, "source_url", None)
        title = getattr(candidate, "title", None) or getattr(analysis, "job_title", None) or "Untitled role"
        company = getattr(candidate, "company", None) or getattr(analysis, "company", None) or "Unknown company"
        location = getattr(candidate, "location", None) or getattr(analysis, "location", None) or "Unspecified"
        result_id = str(uuid5(NAMESPACE_URL, f"{source}:{title}:{company}:{location}:{source_url or description}"))
        score = int(item["match_score"])
        results.append(
            JobSearchResult(
                job_result_id=result_id,
                title=title,
                company=company,
                location=location,
                source=source,
                source_provider=getattr(candidate, "source_provider", None),
                source_url=source_url,
                raw_snippet=getattr(candidate, "snippet", None),
                description=description,
                matched_keywords=list(item["matched_keywords"]),
                match_reasons=list(item["match_reasons"]),
                risks=list(item["risks"]),
                match_score=score,
                score_breakdown=dict(item.get("score_breakdown", {})),
                evidence_quotes=list(item.get("evidence_quotes", [])),
                recommended_action=_recommended_action(score),
                analysis_mode=item["analysis_mode"],
                confidence_label=item["confidence_label"],
            )
        )
    return results


def _metadata_risks(candidate: object, confirmed_profile: ConfirmedProfile) -> list[str]:
    risks: list[str] = []
    if not getattr(candidate, "source_url", None):
        risks.append("Source URL is missing.")
    if getattr(candidate, "location", None) is None and confirmed_profile.preferred_locations:
        risks.append("Location metadata is incomplete.")
    for warning in getattr(candidate, "provider_warnings", []) or []:
        risks.append(str(warning))
    return risks


def _find_running_or_pending_step(steps: list[JobSearchTraceStep]) -> JobSearchTraceStep | None:
    for status in ("running", "pending"):
        for step in steps:
            if step.status == status:
                return step
    return None


def _confidence_label_for_score(score: int) -> str:
    if score >= 85:
        return "strong"
    if score >= 72:
        return "medium"
    if score >= 58:
        return "limited"
    return "weak"


def _recommended_action(score: int) -> str:
    if score >= 85:
        return "Prioritize this role and tailor resume bullets before applying."
    if score >= 72:
        return "Worth reviewing closely and tailoring before applying."
    if score >= 58:
        return "Review the requirements carefully before investing more time."
    return "Keep as a lower-priority option unless the role is especially attractive."


def _recall_queries_from_plan(search_plan: JobSearchPlan) -> list[str]:
    if search_plan.search_intent is None:
        return _clean_list(search_plan.queries[:MAX_PROVIDER_QUERIES_PER_RUN])
    intent = search_plan.search_intent
    return _clean_list(
        intent.broad_queries
        + intent.domain_queries
        + search_plan.target_roles
        + search_plan.queries
    )[:MAX_PROVIDER_PREVIEW_TERMS]


def _ranking_signals_from_plan(search_plan: JobSearchPlan) -> list[str]:
    if search_plan.search_intent is None:
        return _clean_list(search_plan.must_have_signals)
    intent = search_plan.search_intent
    return _clean_list(
        intent.industry_domains
        + intent.evidence_skills
        + intent.generic_tools
        + search_plan.must_have_signals
    )[:16]


def _source_provider_counts(results: list[JobSearchResult]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for result in results:
        counts[result.source_provider or result.source] += 1
    return dict(counts)


def _browser_helper_candidate_to_raw(candidate: BrowserHelperJobCandidate) -> RawJobCandidate:
    source_provider = candidate.source_provider.strip() or "browser_helper"
    warnings = [
        *candidate.provider_warnings,
        "Candidate came from browser helper payload; platform cookies are not stored by backend.",
    ]
    return RawJobCandidate(
        title=candidate.title.strip(),
        company=(candidate.company or "").strip() or None,
        location=(candidate.location or "").strip() or None,
        source_url=(candidate.source_url or "").strip() or None,
        source_provider=source_provider,
        snippet=candidate.snippet.strip(),
        raw_description=(candidate.raw_description or "").strip() or candidate.snippet.strip(),
        discovery_query=(candidate.discovery_query or "").strip() or None,
        discovery_rank=candidate.discovery_rank,
        detail_status=(candidate.detail_status or "").strip() or "browser_helper_payload",
        provider_warnings=_clean_list(warnings),
    )


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
