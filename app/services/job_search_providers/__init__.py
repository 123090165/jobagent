from __future__ import annotations

import os
from dataclasses import asdict, dataclass

from app.services.job_search_providers.base import (
    JobSearchProvider,
    JobSearchProviderError,
    RawJobCandidate,
)
from app.services.job_search_providers.cuhksz_career_provider import (
    CUHKSZ_CAREER_ALLOWED_DOMAINS,
    CUHKSZ_CAREER_BASE_URL,
    CUHKSZ_CAREER_SEARCH_URL,
    CUHKSZCareerProvider,
)
from app.services.job_search_providers.mock_provider import MockJobSearchProvider

DEFAULT_JOB_SEARCH_PROVIDER = "cuhksz_career"
AVAILABLE_JOB_SEARCH_PROVIDERS = ["mock", "cuhksz_career"]


@dataclass(frozen=True)
class JobSearchProviderStatus:
    provider: str
    configured: bool
    available_providers: list[str]
    reason: str | None
    base_url: str | None
    search_url: str | None
    allowlisted_domains: list[str]


def normalize_job_search_provider_name(provider_name: str | None = None) -> str:
    normalized = (
        provider_name or os.getenv("JOBAGENT_JOB_SEARCH_PROVIDER", DEFAULT_JOB_SEARCH_PROVIDER)
    ).strip().lower()
    if normalized in {"mock", "local_mock"}:
        return "mock"
    if normalized in {"cuhksz", "cuhksz_career", "cuhk", "career_cuhk"}:
        return "cuhksz_career"
    raise JobSearchProviderError(f"Unsupported job search provider: {provider_name}")


def resolve_job_search_provider(provider_name: str | None = None) -> JobSearchProvider:
    normalized = normalize_job_search_provider_name(provider_name)
    if normalized == "mock":
        return MockJobSearchProvider()
    return CUHKSZCareerProvider()


def get_job_search_provider_status(provider_name: str | None = None) -> dict[str, object]:
    normalized = normalize_job_search_provider_name(provider_name)
    if normalized == "mock":
        status = JobSearchProviderStatus(
            provider="mock",
            configured=True,
            available_providers=AVAILABLE_JOB_SEARCH_PROVIDERS,
            reason="In-process deterministic provider for demos and tests.",
            base_url=None,
            search_url=None,
            allowlisted_domains=[],
        )
        return asdict(status)
    status = JobSearchProviderStatus(
        provider="cuhksz_career",
        configured=True,
        available_providers=AVAILABLE_JOB_SEARCH_PROVIDERS,
        reason=None,
        base_url=CUHKSZ_CAREER_BASE_URL,
        search_url=CUHKSZ_CAREER_SEARCH_URL,
        allowlisted_domains=CUHKSZ_CAREER_ALLOWED_DOMAINS,
    )
    return asdict(status)


__all__ = [
    "AVAILABLE_JOB_SEARCH_PROVIDERS",
    "CUHKSZCareerProvider",
    "DEFAULT_JOB_SEARCH_PROVIDER",
    "JobSearchProvider",
    "JobSearchProviderError",
    "JobSearchProviderStatus",
    "MockJobSearchProvider",
    "RawJobCandidate",
    "get_job_search_provider_status",
    "normalize_job_search_provider_name",
    "resolve_job_search_provider",
]
