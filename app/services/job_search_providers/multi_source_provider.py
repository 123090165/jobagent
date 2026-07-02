from __future__ import annotations

from app.services.job_search_providers.base import (
    JobSearchProvider,
    JobSearchProviderError,
    RawJobCandidate,
)


class MultiSourceJobSearchProvider:
    provider_name = "multi_source"
    provider_kind = "hybrid"
    detail_strategy = "mixed_source_strategy"

    def __init__(self, providers: list[JobSearchProvider]) -> None:
        self.providers = providers
        self.source_names = [getattr(provider, "provider_name", "unknown") for provider in providers]
        self.provider_name = "multi_source:" + ",".join(self.source_names) if self.source_names else "multi_source"

    def search_jobs(self, *, query: str, location: str | None, limit: int) -> list[RawJobCandidate]:
        candidates: list[RawJobCandidate] = []
        for provider in self.providers:
            try:
                candidates.extend(provider.search_jobs(query=query, location=location, limit=limit))
            except JobSearchProviderError:
                continue
        return candidates
