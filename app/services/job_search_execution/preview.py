from __future__ import annotations

from app.schemas.confirmed_profile import ConfirmedProfile
from app.schemas.job_search import JobSearchRun, JobSearchRunCreateRequest
from app.services.job_search_execution.provider_search import (
    MAX_PROVIDER_QUERIES_PER_RUN,
    _effective_provider_locations,
)
from app.services.job_search_planner import (
    JobSearchPlan,
    build_focused_provider_queries,
)
from app.services.job_search_providers import (
    encode_selected_sources,
    normalize_job_search_provider_name,
    normalize_job_search_source_name,
    selected_sources_from_provider_name,
)
from app.services.job_search_providers.cuhksz_career_provider import (
    build_cuhksz_search_url,
    build_cuhksz_title_terms,
)
from app.services.job_search_providers.remoteok_provider import REMOTEOK_API_URL
from app.services.job_search_providers.serper_web_provider import (
    build_serper_preview_search_url,
    configured_serper_search_sites,
)

MAX_PROVIDER_PREVIEW_TERMS = 8


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
