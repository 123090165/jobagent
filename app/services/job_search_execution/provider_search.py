from __future__ import annotations

import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from app.schemas.job_search import PlannedQuery
from app.services.job_search_planner import JobSearchPlan
from app.services.job_search_providers import (
    JobSearchProvider,
    JobSearchProviderError,
    RawJobCandidate,
    selected_sources_from_provider_name,
)
from app.services.job_search_providers.cuhksz_career_provider import (
    build_cuhksz_title_terms,
)
from app.services.job_search_recall_metrics import (
    build_source_recall_stats,
    candidate_recall_key,
    dedupe_cross_source_reposts,
)

MAX_PROVIDER_QUERIES_PER_RUN = 6
MAX_PROVIDER_LOCATIONS_PER_RUN = 3
MIN_RECALL_CANDIDATE_POOL = 30
MAX_RECALL_CANDIDATE_POOL = 100
RECALL_POOL_MULTIPLIER = 6
MAX_CONCURRENT_PROVIDER_SOURCES = 4


@dataclass
class ProviderQueryStat:
    source: str
    query: str
    query_type: str
    priority: float
    location: str | None
    requested_limit: int
    returned_count: int
    new_candidate_count: int
    duration_ms: float | None = None

    def to_dict(self) -> dict[str, object]:
        item: dict[str, object] = {
            "source": self.source,
            "query": self.query,
            "query_type": self.query_type,
            "priority": self.priority,
            "location": self.location,
            "requested_limit": self.requested_limit,
            "returned_count": self.returned_count,
            "new_candidate_count": self.new_candidate_count,
        }
        if self.duration_ms is not None:
            item["duration_ms"] = self.duration_ms
        return item


@dataclass(frozen=True)
class ProviderSearchTask:
    provider: JobSearchProvider = field(repr=False)
    source: str
    planned_query: PlannedQuery
    location: str | None
    limit: int


@dataclass(frozen=True)
class _ProviderTaskResult:
    task: ProviderSearchTask
    returned: list[RawJobCandidate]
    duration_ms: float
    error: JobSearchProviderError | None = None


@dataclass
class ProviderRecallResult:
    candidates: list[RawJobCandidate]
    provider_name: str
    provider_kind: str
    query_stats: list[ProviderQueryStat] = field(default_factory=list)
    raw_candidates: list[RawJobCandidate] = field(default_factory=list, repr=False)
    raw_candidate_count: int = 0
    duplicate_count: int = 0
    cross_source_duplicate_count: int = 0
    truncated_candidate_count: int = 0
    candidate_pool_cap: int = 0
    source_attempts: list[dict[str, object]] = field(default_factory=list)

    def details(self) -> dict[str, object]:
        source_stats = build_source_recall_stats(self.raw_candidates, self.candidates)
        logical_source_attempts = len(self.query_stats)
        attempted_source_count = len({item.source for item in self.query_stats})
        return {
            "provider": self.provider_name,
            "source_kind": self.provider_kind,
            "selected_sources": selected_sources_from_provider_name(self.provider_name),
            "source_candidate_counts": dict(Counter(candidate.source_provider for candidate in self.candidates)),
            "source_stats": [item.to_dict() for item in source_stats],
            "query_count": len(self.query_stats),
            "logical_provider_call_count": logical_source_attempts,
            "logical_source_attempt_count": logical_source_attempts,
            "source_execution_mode": (
                "bounded_parallel" if attempted_source_count > 1 else "sequential"
            ),
            "source_concurrency": min(
                MAX_CONCURRENT_PROVIDER_SOURCES,
                max(1, attempted_source_count),
            ),
            "external_http_request_count": None,
            "raw_candidate_count": self.raw_candidate_count,
            "duplicate_count": self.duplicate_count,
            "cross_source_duplicate_count": self.cross_source_duplicate_count,
            "truncated_candidate_count": self.truncated_candidate_count,
            "deduped_candidate_count": len(self.candidates),
            "missing_source_url_count": sum(item.missing_url_count for item in source_stats),
            "missing_detail_count": sum(item.missing_detail_count for item in source_stats),
            "candidate_pool_cap": self.candidate_pool_cap,
            "query_stats": [item.to_dict() for item in self.query_stats],
            "source_attempts": self.source_attempts,
        }


def _run_provider_search(
    provider: JobSearchProvider,
    *,
    search_plan: JobSearchPlan,
    max_results: int,
) -> ProviderRecallResult:
    provider_name = getattr(provider, "provider_name", "mock")
    provider_kind = getattr(provider, "provider_kind", _provider_source_kind(provider_name, "live_search"))
    per_call_limit = max(1, min(max_results, 5))
    candidate_pool_cap = candidate_pool_cap_for(max_results)
    tasks = build_provider_search_tasks(
        provider,
        search_plan=search_plan,
        per_call_limit=per_call_limit,
        browser_limit=candidate_pool_cap,
    )
    is_multi_source = len(_source_providers(provider)) > 1
    deduped: dict[str, RawJobCandidate] = {}
    seen_keys: set[str] = set()
    stats: list[ProviderQueryStat] = []
    raw_candidates: list[RawJobCandidate] = []
    duplicate_count = 0
    source_attempts: list[dict[str, object]] = []
    for task_result in _execute_provider_tasks(tasks, concurrent=is_multi_source):
        task = task_result.task
        before_count = len(deduped)
        if task_result.error is not None:
            source_attempts.append(
                _source_attempt(
                    task,
                    returned_count=0,
                    error=f"{type(task_result.error).__name__}: {task_result.error}",
                )
            )
            stats.append(
                ProviderQueryStat(
                    source=task.source,
                    query=task.planned_query.query,
                    query_type=task.planned_query.query_type,
                    priority=task.planned_query.priority,
                    location=task.location,
                    requested_limit=task.limit,
                    returned_count=0,
                    new_candidate_count=0,
                    duration_ms=task_result.duration_ms,
                )
            )
            continue
        returned = task_result.returned
        source_attempts.append(_source_attempt(task, returned_count=len(returned)))
        raw_candidates.extend(returned)
        for candidate in returned:
            key = candidate_recall_key(candidate)
            if key in seen_keys:
                duplicate_count += 1
                continue
            seen_keys.add(key)
            deduped[key] = candidate
        stats.append(
            ProviderQueryStat(
                source=task.source,
                query=task.planned_query.query,
                query_type=task.planned_query.query_type,
                priority=task.planned_query.priority,
                location=task.location,
                requested_limit=task.limit,
                returned_count=len(returned),
                new_candidate_count=max(0, len(deduped) - before_count),
                duration_ms=task_result.duration_ms,
            )
        )
    clustered, cross_source_duplicate_count = dedupe_cross_source_reposts(
        deduped.values()
    )
    retained = clustered[:candidate_pool_cap]
    return ProviderRecallResult(
        candidates=retained,
        provider_name=provider_name,
        provider_kind=provider_kind,
        query_stats=stats,
        raw_candidates=raw_candidates,
        raw_candidate_count=len(raw_candidates),
        duplicate_count=duplicate_count + cross_source_duplicate_count,
        cross_source_duplicate_count=cross_source_duplicate_count,
        truncated_candidate_count=max(0, len(clustered) - len(retained)),
        candidate_pool_cap=candidate_pool_cap,
        source_attempts=source_attempts,
    )


def _execute_provider_tasks(
    tasks: list[ProviderSearchTask],
    *,
    concurrent: bool,
) -> list[_ProviderTaskResult]:
    if not tasks:
        return []
    if not concurrent:
        results: list[_ProviderTaskResult] = []
        for task in tasks:
            result = _execute_provider_task(task)
            if result.error is not None:
                raise result.error
            results.append(result)
        return results

    groups: dict[str, list[tuple[int, ProviderSearchTask]]] = {}
    for index, task in enumerate(tasks):
        groups.setdefault(task.source, []).append((index, task))
    with ThreadPoolExecutor(
        max_workers=min(MAX_CONCURRENT_PROVIDER_SOURCES, len(groups)),
        thread_name_prefix="job-search-source",
    ) as executor:
        indexed_results = [
            item
            for source_results in executor.map(_execute_source_tasks, groups.values())
            for item in source_results
        ]
    return [result for _, result in sorted(indexed_results, key=lambda item: item[0])]


def _execute_source_tasks(
    indexed_tasks: list[tuple[int, ProviderSearchTask]],
) -> list[tuple[int, _ProviderTaskResult]]:
    return [(index, _execute_provider_task(task)) for index, task in indexed_tasks]


def _execute_provider_task(task: ProviderSearchTask) -> _ProviderTaskResult:
    search_start = time.perf_counter()
    try:
        returned = task.provider.search_jobs(
            query=task.planned_query.query,
            location=task.location,
            limit=task.limit,
        )
        return _ProviderTaskResult(
            task=task,
            returned=returned,
            duration_ms=_elapsed_ms(search_start),
        )
    except JobSearchProviderError as exc:
        return _ProviderTaskResult(
            task=task,
            returned=[],
            duration_ms=_elapsed_ms(search_start),
            error=exc,
        )


def build_provider_search_tasks(
    provider: JobSearchProvider,
    *,
    search_plan: JobSearchPlan,
    per_call_limit: int,
    browser_limit: int | None = None,
) -> list[ProviderSearchTask]:
    selected_queries = select_provider_queries(search_plan)
    task_groups = [
        _tasks_for_source(
            source_provider,
            selected_queries=selected_queries,
            locations=search_plan.locations,
            per_call_limit=per_call_limit,
            browser_limit=browser_limit,
        )
        for source_provider in _source_providers(provider)
    ]
    return _round_robin(task_groups)


def _tasks_for_source(
    provider: JobSearchProvider,
    *,
    selected_queries: list[PlannedQuery],
    locations: list[str],
    per_call_limit: int,
    browser_limit: int | None,
) -> list[ProviderSearchTask]:
    source = getattr(provider, "provider_name", "unknown")
    queries = _translate_queries_for_source(source, selected_queries)
    effective_locations = _effective_provider_locations(source, locations)
    pairs = _query_location_pairs(source, queries, effective_locations)
    return [
        ProviderSearchTask(
            provider=provider,
            source=source,
            planned_query=planned_query,
            location=location,
            limit=(
                browser_limit
                if source.startswith("browser_helper") and browser_limit is not None
                else per_call_limit
            ),
        )
        for planned_query, location in pairs[: _max_tasks_for_source(source)]
    ]


def _translate_queries_for_source(
    source: str,
    selected_queries: list[PlannedQuery],
) -> list[PlannedQuery]:
    if source.startswith("browser_helper"):
        return selected_queries[:1]
    if source == "remoteok":
        for query_type in ("broad", "user", "role_domain", "evidence", "tool", "fallback"):
            match = next(
                (item for item in selected_queries if item.query_type == query_type),
                None,
            )
            if match is not None:
                return [match]
        return selected_queries[:1]
    if source == "cuhksz_career":
        translated: list[PlannedQuery] = []
        seen: set[str] = set()
        for planned_query in selected_queries:
            if planned_query.query_type == "tool":
                continue
            for term in build_cuhksz_title_terms(planned_query.query):
                key = term.casefold()
                if key in seen:
                    continue
                seen.add(key)
                translated.append(
                    planned_query.model_copy(
                        update={
                            "query": term,
                            "rationale": f"CUHKSZ title term translated from: {planned_query.query}",
                        }
                    )
                )
                if len(translated) >= _max_tasks_for_source(source):
                    return translated
        return translated or selected_queries[:1]
    if source == "linkedin":
        translated = [
            item
            for item in selected_queries
            if item.query_type not in {"tool", "fallback"}
        ]
        return translated or selected_queries[:1]
    return selected_queries


def _query_location_pairs(
    source: str,
    queries: list[PlannedQuery],
    locations: list[str | None],
) -> list[tuple[PlannedQuery, str | None]]:
    if not queries:
        return []
    if source in {"linkedin", "serper_web"}:
        coverage = [(queries[0], location) for location in locations]
        fill = [(query, locations[0]) for query in queries[1:]]
        return coverage + fill
    return [(query, location) for query in queries for location in locations]


def _max_tasks_for_source(source: str) -> int:
    if source.startswith("browser_helper") or source == "remoteok":
        return 1
    if source in {"cuhksz_career", "linkedin"}:
        return 4
    return MAX_PROVIDER_QUERIES_PER_RUN


def _source_providers(provider: JobSearchProvider) -> list[JobSearchProvider]:
    providers = getattr(provider, "providers", None)
    if isinstance(providers, list) and providers:
        return providers
    return [provider]


def _round_robin(groups: list[list[ProviderSearchTask]]) -> list[ProviderSearchTask]:
    tasks: list[ProviderSearchTask] = []
    for index in range(max((len(group) for group in groups), default=0)):
        tasks.extend(group[index] for group in groups if index < len(group))
    return tasks


def _source_attempt(
    task: ProviderSearchTask,
    *,
    returned_count: int,
    error: str | None = None,
) -> dict[str, object]:
    return {
        "source": task.source,
        "query": task.planned_query.query,
        "location": task.location,
        "requested_limit": task.limit,
        "returned_count": returned_count,
        "error": error,
    }


def select_provider_queries(search_plan: JobSearchPlan) -> list[PlannedQuery]:
    """Select a balanced, deterministic query set instead of taking list order."""
    planned = search_plan.planned_queries
    if not planned:
        planned = [
            PlannedQuery(
                query="Internship",
                query_type="fallback",
                priority=0.4,
                rationale="Empty legacy plan fallback.",
            )
        ]
    quotas = {
        "user": 1,
        "broad": 1,
        "role_domain": 2,
        "evidence": 2,
        "tool": 1,
        "fallback": 1,
    }
    type_order = ("user", "role_domain", "evidence", "broad", "tool", "fallback")
    selected: list[PlannedQuery] = []
    selected_keys: set[str] = set()
    for query_type in type_order:
        candidates = sorted(
            (item for item in planned if item.query_type == query_type),
            key=lambda item: -item.priority,
        )
        for item in candidates[: quotas[query_type]]:
            if len(selected) >= MAX_PROVIDER_QUERIES_PER_RUN:
                break
            key = item.query.strip().lower()
            if key and key not in selected_keys:
                selected.append(item)
                selected_keys.add(key)

    remaining = sorted(planned, key=lambda item: -item.priority)
    for item in remaining:
        if len(selected) >= MAX_PROVIDER_QUERIES_PER_RUN:
            break
        key = item.query.strip().lower()
        if key and key not in selected_keys:
            selected.append(item)
            selected_keys.add(key)
    return selected[:MAX_PROVIDER_QUERIES_PER_RUN]


def candidate_pool_cap_for(max_results: int) -> int:
    return min(
        MAX_RECALL_CANDIDATE_POOL,
        max(MIN_RECALL_CANDIDATE_POOL, max_results * RECALL_POOL_MULTIPLIER),
    )


def _effective_provider_locations(provider_name: str | None, locations: list[str]) -> list[str | None]:
    if provider_name == "cuhksz_career":
        return [None]
    if provider_name == "remoteok":
        return locations[:1] or [None]
    if provider_name == "multi_source" or (provider_name or "").startswith("multi_source:"):
        return locations[:1] or [None]
    return locations[:MAX_PROVIDER_LOCATIONS_PER_RUN] or [None]


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


def _elapsed_ms(start: float) -> float:
    return round((time.perf_counter() - start) * 1000.0, 3)
