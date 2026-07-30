"""并行调用多个职位来源，去重候选并保留每个来源的部分失败信息。"""

from __future__ import annotations

from app.services.job_search_providers.base import (
    JobSearchProvider,
    JobSearchProviderError,
    RawJobCandidate,
)


class MultiSourceJobSearchProvider:
    """把multi来源职位搜索接入统一 Provider 协议。"""
    provider_name = "multi_source"
    provider_kind = "hybrid"
    detail_strategy = "mixed_source_strategy"

    def __init__(self, providers: list[JobSearchProvider]) -> None:
        self.providers = providers
        self.source_names = [getattr(provider, "provider_name", "unknown") for provider in providers]
        self.provider_name = "multi_source:" + ",".join(self.source_names) if self.source_names else "multi_source"
        self.source_attempts: list[dict[str, object]] = []

    def search_jobs(self, *, query: str, location: str | None, limit: int) -> list[RawJobCandidate]:
        candidates: list[RawJobCandidate] = []
        for provider in self.providers:
            source_name = getattr(provider, "provider_name", "unknown")
            try:
                returned = provider.search_jobs(query=query, location=location, limit=limit)
                candidates.extend(returned)
                self.source_attempts.append(
                    {
                        "source": source_name,
                        "query": query,
                        "location": location,
                        "requested_limit": limit,
                        "returned_count": len(returned),
                        "error": None,
                    }
                )
            except JobSearchProviderError as exc:
                self.source_attempts.append(
                    {
                        "source": source_name,
                        "query": query,
                        "location": location,
                        "requested_limit": limit,
                        "returned_count": 0,
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
                continue
        return candidates
