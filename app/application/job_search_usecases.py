from __future__ import annotations

from uuid import uuid5, NAMESPACE_URL

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
    JobSearchRun,
    JobSearchRunCreateRequest,
    JobSearchRunResponse,
)
from app.services.errors import JobAgentError


def create_job_search_run(
    payload: JobSearchRunCreateRequest,
    *,
    session_repository: ProfileSessionRepository = profile_session_repository,
    confirmed_repository: ConfirmedProfileRepository = confirmed_profile_repository,
    search_repository: JobSearchRepository = job_search_repository,
) -> JobSearchRunResponse:
    session = get_profile_session(payload.session_id, repository=session_repository)
    if session.confirmed_profile_id is None:
        raise JobAgentError(
            message="Confirmed profile is required before starting job search.",
            error_code="confirmed_profile_required",
            status_code=409,
        )
    if session.current_step not in {"job_search_ready", "job_search_completed"}:
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
    return JobSearchRunResponse(job_search_run=run, profile_session=session)


def list_job_search_runs(
    session_id: str,
    *,
    session_repository: ProfileSessionRepository = profile_session_repository,
    search_repository: JobSearchRepository = job_search_repository,
) -> list[JobSearchRun]:
    get_profile_session(session_id, repository=session_repository)
    return search_repository.list_recent_by_session(session_id)


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
        query = " ".join((target_roles + keywords)[:8]).strip()
    if not query:
        query = "Software Engineer"
    return query, locations, target_roles, keywords


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
            "signals": ["llm", "langchain", "langgraph", "rag", "agent"],
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
    normalized_keywords = _clean_list(keywords + confirmed_profile.core_skills + confirmed_profile.supporting_skills)
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
            match_reasons.append(
                "Matched keywords: " + ", ".join(matched_keywords[:4]) + "."
            )
        if confirmed_profile.work_arrangements:
            match_reasons.append(
                "Can be filtered later by preferred work arrangements."
            )
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
                description=item["description"],
                matched_keywords=matched_keywords[:6],
                match_reasons=match_reasons,
                risks=item["risks"],
                match_score=score,
                recommended_action="Review fit, then tailor resume bullets before applying.",
            )
        )

    results.sort(key=lambda item: item.match_score, reverse=True)
    return results[:6]


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
