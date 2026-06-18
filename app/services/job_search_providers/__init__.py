from __future__ import annotations

import os
from dataclasses import asdict, dataclass

from app.services.job_search_providers.base import (
    JobSearchProvider,
    JobSearchProviderError,
    RawJobCandidate,
)
from app.services.job_search_providers.curated_crawler_provider import (
    CuratedCrawlerProvider,
    get_curated_job_domains,
)
from app.services.job_search_providers.mock_provider import MockJobSearchProvider
from app.services.job_search_providers.web_provider import WebSearchProvider

DEFAULT_JOB_SEARCH_PROVIDER = "curated_crawler"
AVAILABLE_JOB_SEARCH_PROVIDERS = ["mock", "tavily", "curated_crawler"]


@dataclass(frozen=True)
class JobSearchProviderStatus:
    provider: str
    configured: bool
    available_providers: list[str]
    reason: str | None
    allowlisted_domains: list[str]


def normalize_job_search_provider_name(provider_name: str | None = None) -> str:
    normalized = (provider_name or os.getenv("JOBAGENT_JOB_SEARCH_PROVIDER", DEFAULT_JOB_SEARCH_PROVIDER)).strip().lower()
    if normalized in {"mock", "local_mock"}:
        return "mock"
    if normalized in {"web", "tavily"}:
        return "tavily"
    if normalized in {"curated", "curated_crawler", "crawler"}:
        return "curated_crawler"
    raise JobSearchProviderError(f"Unsupported job search provider: {provider_name}")


def resolve_job_search_provider(provider_name: str | None = None) -> JobSearchProvider:
    normalized = normalize_job_search_provider_name(provider_name)
    if normalized == "mock":
        return MockJobSearchProvider()
    if normalized == "tavily":
        return WebSearchProvider()
    return CuratedCrawlerProvider()


def get_job_search_provider_status(provider_name: str | None = None) -> dict[str, object]:
    normalized = normalize_job_search_provider_name(provider_name)
    if normalized == "mock":
        status = JobSearchProviderStatus(
            provider="mock",
            configured=True,
            available_providers=AVAILABLE_JOB_SEARCH_PROVIDERS,
            reason="In-process deterministic provider for demos and tests.",
            allowlisted_domains=[],
        )
        return asdict(status)
    if normalized == "tavily":
        configured = bool(os.getenv("TAVILY_API_KEY"))
        status = JobSearchProviderStatus(
            provider="tavily",
            configured=configured,
            available_providers=AVAILABLE_JOB_SEARCH_PROVIDERS,
            reason=None if configured else "TAVILY_API_KEY is empty.",
            allowlisted_domains=[],
        )
        return asdict(status)

    curated_status = CuratedCrawlerProvider.status()
    status = JobSearchProviderStatus(
        provider="curated_crawler",
        configured=curated_status.configured,
        available_providers=AVAILABLE_JOB_SEARCH_PROVIDERS,
        reason=curated_status.reason,
        allowlisted_domains=curated_status.allowlisted_domains,
    )
    return asdict(status)


__all__ = [
    "AVAILABLE_JOB_SEARCH_PROVIDERS",
    "DEFAULT_JOB_SEARCH_PROVIDER",
    "CuratedCrawlerProvider",
    "JobSearchProvider",
    "JobSearchProviderError",
    "JobSearchProviderStatus",
    "MockJobSearchProvider",
    "RawJobCandidate",
    "WebSearchProvider",
    "get_curated_job_domains",
    "get_job_search_provider_status",
    "normalize_job_search_provider_name",
    "resolve_job_search_provider",
]
