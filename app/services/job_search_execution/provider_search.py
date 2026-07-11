from __future__ import annotations

import time
from collections import Counter
from dataclasses import dataclass, field

from app.services.job_search_planner import JobSearchPlan
from app.services.job_search_providers import (
    JobSearchProvider,
    RawJobCandidate,
    selected_sources_from_provider_name,
)
from app.services.job_search_recall_metrics import (
    build_source_recall_stats,
    candidate_recall_key,
)

MAX_PROVIDER_QUERIES_PER_RUN = 3
MAX_PROVIDER_LOCATIONS_PER_RUN = 3


@dataclass
class ProviderQueryStat:
    query: str
    location: str | None
    requested_limit: int
    returned_count: int
    new_candidate_count: int
    source_count: int = 1
    logical_request_count: int = 1
    duration_ms: float | None = None

    def to_dict(self) -> dict[str, object]:
        item: dict[str, object] = {
            "query": self.query,
            "location": self.location,
            "requested_limit": self.requested_limit,
            "returned_count": self.returned_count,
            "new_candidate_count": self.new_candidate_count,
            "source_count": self.source_count,
            "logical_request_count": self.logical_request_count,
        }
        if self.duration_ms is not None:
            item["duration_ms"] = self.duration_ms
        return item


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
    source_attempts: list[dict[str, object]] = field(default_factory=list)

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
    queries = search_plan.queries[: max(1, min(len(search_plan.queries), MAX_PROVIDER_QUERIES_PER_RUN))]
    locations = _effective_provider_locations(provider_name, search_plan.locations)
    per_call_limit = max(1, min(max_results, 5))
    candidate_pool_cap = max_results * 2
    if provider_kind == "browser_helper":
        query = queries[0] if queries else ""
        location = locations[0] if locations else None
        search_start = time.perf_counter()
        returned = provider.search_jobs(query=query, location=location, limit=candidate_pool_cap)
        search_duration_ms = _elapsed_ms(search_start)
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
                    duration_ms=search_duration_ms,
                )
            ],
            raw_candidates=returned,
            raw_candidate_count=len(returned),
            duplicate_count=duplicate_count,
            truncated_candidate_count=truncated_candidate_count,
            candidate_pool_cap=candidate_pool_cap,
            source_attempts=_provider_source_attempts(provider),
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
            search_start = time.perf_counter()
            returned = provider.search_jobs(query=query, location=location, limit=per_call_limit)
            search_duration_ms = _elapsed_ms(search_start)
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
                    duration_ms=search_duration_ms,
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
        source_attempts=_provider_source_attempts(provider),
    )


def _provider_source_attempts(provider: JobSearchProvider) -> list[dict[str, object]]:
    attempts = getattr(provider, "source_attempts", None)
    if not isinstance(attempts, list):
        return []
    return [dict(item) for item in attempts if isinstance(item, dict)]


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
