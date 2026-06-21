from __future__ import annotations

from collections import Counter
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
    filter_candidates,
)
from app.services.job_search_planner import (
    JobSearchPlan,
    build_focused_provider_queries,
    build_search_plan,
)
from app.services.job_search_providers import (
    JobSearchProvider,
    RawJobCandidate,
    normalize_job_search_provider_name,
    resolve_job_search_provider,
)
from app.services.job_search_providers.cuhksz_career_provider import (
    build_cuhksz_search_url,
    build_cuhksz_title_terms,
)
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

    provider_name = normalize_job_search_provider_name(
        getattr(job_search_provider, "provider_name", None) or payload.search_provider
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
        raw_candidates = _run_provider_search(
            provider,
            search_plan=search_plan,
            max_results=max_results,
        )
        search_repository.complete_trace_step(
            provider_step.step_id,
            mode=provider_mode,
            summary=f"Collected {len(raw_candidates)} candidates from {provider_name}.",
            guardrails=ASSEMBLY_GUARDRAILS,
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
        )

        matching_step = steps[4]
        search_repository.mark_trace_step_running(
            matching_step.step_id,
            mode="deterministic",
            summary="Scoring profile fit against analyzed candidates.",
            guardrails=ASSEMBLY_GUARDRAILS,
        )
        matched_items = _match_candidates(
            confirmed_profile,
            search_plan,
            analyses["items"],
        )
        search_repository.complete_trace_step(
            matching_step.step_id,
            mode="deterministic",
            summary=f"Scored {len(matched_items)} candidate fit profile(s).",
            guardrails=ASSEMBLY_GUARDRAILS,
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

    provider_name = normalize_job_search_provider_name(payload.search_provider)
    provider_search_terms, provider_search_urls = _build_provider_preview_searches(
        provider_name,
        search_plan.queries,
    )

    return JobSearchPreviewResponse(
        session_id=session.session_id,
        confirmed_profile_id=confirmed_profile.confirmed_profile_id,
        search_mode=payload.search_mode,
        search_provider=provider_name,
        llm_enabled=payload.use_llm,
        llm_provider=llm_provider,
        query=query,
        locations=search_plan.locations,
        target_roles=search_plan.target_roles,
        keywords=keywords,
        provider_queries=search_plan.queries,
        provider_search_terms=provider_search_terms,
        provider_search_urls=provider_search_urls,
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


def _build_provider_preview_searches(
    provider_name: str | None,
    provider_queries: list[str],
) -> tuple[list[str], list[str]]:
    if provider_name != "cuhksz_career":
        return [], []
    terms: list[str] = []
    for query in provider_queries[:3]:
        terms.extend(build_cuhksz_title_terms(query))
    terms = _clean_list(terms)[:8]
    return terms, [build_cuhksz_search_url(term) for term in terms]


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
) -> list[RawJobCandidate]:
    queries = search_plan.queries[: max(1, min(len(search_plan.queries), 3))]
    locations = search_plan.locations[:3] or [None]
    per_call_limit = max(1, min(max_results, 5))
    deduped: dict[str, RawJobCandidate] = {}
    for query in queries:
        for location in locations:
            for candidate in provider.search_jobs(query=query, location=location, limit=per_call_limit):
                key = (candidate.source_url or f"{candidate.title}:{candidate.company}:{candidate.location}").lower()
                deduped.setdefault(key, candidate)
                if len(deduped) >= max_results * 2:
                    break
            if len(deduped) >= max_results * 2:
                break
        if len(deduped) >= max_results * 2:
            break
    return list(deduped.values())[: max_results * 2]


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
    for candidate in filtered.selected_candidates:
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
                recommended_action=_recommended_action(score),
                analysis_mode=item["analysis_mode"],
                confidence_label=item["confidence_label"],
            )
        )
    return results


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
