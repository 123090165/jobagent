from __future__ import annotations

import os

from app.services.job_search_providers.base import (
    JobSearchProvider,
    JobSearchProviderError,
    RawJobCandidate,
)
from app.services.job_search_providers.mock_provider import MockJobSearchProvider
from app.services.job_search_providers.web_provider import WebSearchProvider

DEFAULT_JOB_SEARCH_PROVIDER = "mock"


def normalize_job_search_provider_name(provider_name: str | None = None) -> str:
    normalized = (provider_name or os.getenv("JOBAGENT_JOB_SEARCH_PROVIDER", DEFAULT_JOB_SEARCH_PROVIDER)).strip().lower()
    if normalized in {"mock", "local_mock"}:
        return "mock"
    if normalized in {"web", "tavily"}:
        return "tavily"
    raise JobSearchProviderError(f"Unsupported job search provider: {provider_name}")


def resolve_job_search_provider(provider_name: str | None = None) -> JobSearchProvider:
    normalized = normalize_job_search_provider_name(provider_name)
    if normalized == "mock":
        return MockJobSearchProvider()
    return WebSearchProvider()


__all__ = [
    "DEFAULT_JOB_SEARCH_PROVIDER",
    "JobSearchProvider",
    "JobSearchProviderError",
    "MockJobSearchProvider",
    "RawJobCandidate",
    "WebSearchProvider",
    "normalize_job_search_provider_name",
    "resolve_job_search_provider",
]
