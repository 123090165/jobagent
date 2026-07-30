"""按配置选择单一或多来源职位 Provider，并统一来源别名、状态与选择编码。"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass

from app.services.job_search_providers.base import (
    JobSearchProvider,
    JobSearchProviderError,
    RawJobCandidate,
)
from app.services.job_search_providers.browser_helper_provider import (
    BROWSER_HELPER_PROVIDER_PREFIX,
    BrowserHelperPayloadProvider,
)
from app.services.job_search_providers.cuhksz_career_provider import (
    CUHKSZ_CAREER_ALLOWED_DOMAINS,
    CUHKSZ_CAREER_BASE_URL,
    CUHKSZ_CAREER_SEARCH_URL,
    CUHKSZCareerProvider,
)
from app.services.job_search_providers.linkedin_discovery_provider import (
    LINKEDIN_SEARCH_SITE,
    LinkedInDiscoveryProvider,
)
from app.services.job_search_providers.mock_provider import MockJobSearchProvider
from app.services.job_search_providers.multi_source_provider import MultiSourceJobSearchProvider
from app.services.job_search_providers.remoteok_provider import REMOTEOK_API_URL, RemoteOKProvider
from app.services.job_search_providers.serper_web_provider import (
    SERPER_SEARCH_URL,
    SerperWebSearchProvider,
    configured_serper_search_sites,
)

DEFAULT_JOB_SEARCH_PROVIDER = "cuhksz_career"
MULTI_SOURCE_PREFIX = "multi_source:"
AVAILABLE_JOB_SEARCH_PROVIDERS = [
    "mock",
    "cuhksz_career",
    "linkedin",
    "remoteok",
    "serper_web",
    "browser_helper",
    "multi_source",
]
AVAILABLE_JOB_SEARCH_SOURCES = ["cuhksz_career", "linkedin", "remoteok"]


@dataclass(frozen=True)
class JobSearchProviderStatus:
    provider: str
    configured: bool
    available_providers: list[str]
    reason: str | None
    base_url: str | None
    search_url: str | None
    allowlisted_domains: list[str]
    source_kind: str
    detail_strategy: str


def normalize_job_search_provider_name(provider_name: str | None = None) -> str:
    normalized = (
        provider_name or os.getenv("JOBAGENT_JOB_SEARCH_PROVIDER", DEFAULT_JOB_SEARCH_PROVIDER)
    ).strip().lower()
    if normalized in {"mock", "local_mock"}:
        return "mock"
    if normalized in {"cuhksz", "cuhksz_career", "cuhk", "career_cuhk"}:
        return "cuhksz_career"
    if normalized in {"serper", "serper_web", "web", "web_search", "search_engine"}:
        return "serper_web"
    if normalized in {"linkedin", "linkedin_jobs"}:
        return "linkedin"
    if normalized in {"remoteok", "remote_ok"}:
        return "remoteok"
    if normalized == BROWSER_HELPER_PROVIDER_PREFIX or normalized.startswith(f"{BROWSER_HELPER_PROVIDER_PREFIX}:"):
        return normalized
    if normalized == "multi_source" or normalized.startswith(MULTI_SOURCE_PREFIX):
        return normalized
    raise JobSearchProviderError(f"Unsupported job search provider: {provider_name}")


def normalize_job_search_source_name(source_name: str) -> str:
    normalized = normalize_job_search_provider_name(source_name)
    if normalized not in AVAILABLE_JOB_SEARCH_SOURCES:
        raise JobSearchProviderError(f"Unsupported job search source: {source_name}")
    return normalized


def encode_selected_sources(sources: list[str]) -> str:
    normalized = _dedupe_sources([normalize_job_search_source_name(source) for source in sources])
    if not normalized:
        return DEFAULT_JOB_SEARCH_PROVIDER
    if len(normalized) == 1:
        return normalized[0]
    return MULTI_SOURCE_PREFIX + ",".join(normalized)


def selected_sources_from_provider_name(provider_name: str | None) -> list[str]:
    if not provider_name:
        return [DEFAULT_JOB_SEARCH_PROVIDER]
    normalized = normalize_job_search_provider_name(provider_name)
    if normalized.startswith(MULTI_SOURCE_PREFIX):
        raw_sources = normalized[len(MULTI_SOURCE_PREFIX) :].split(",")
        return _dedupe_sources([normalize_job_search_source_name(source) for source in raw_sources if source])
    if normalized.startswith(f"{BROWSER_HELPER_PROVIDER_PREFIX}:"):
        raw_sources = normalized[len(BROWSER_HELPER_PROVIDER_PREFIX) + 1 :].split(",")
        return _dedupe_sources(
            [source for source in raw_sources if source in AVAILABLE_JOB_SEARCH_SOURCES]
        )
    if normalized in AVAILABLE_JOB_SEARCH_SOURCES:
        return [normalized]
    return []


def resolve_job_search_provider(provider_name: str | None = None) -> JobSearchProvider:
    normalized = normalize_job_search_provider_name(provider_name)
    if normalized == "mock":
        return MockJobSearchProvider()
    if normalized.startswith(MULTI_SOURCE_PREFIX) or normalized == "multi_source":
        sources = selected_sources_from_provider_name(normalized)
        if not sources:
            sources = [DEFAULT_JOB_SEARCH_PROVIDER]
        return MultiSourceJobSearchProvider([resolve_job_search_provider(source) for source in sources])
    if normalized == "serper_web":
        return SerperWebSearchProvider()
    if normalized == "linkedin":
        return LinkedInDiscoveryProvider()
    if normalized == "remoteok":
        return RemoteOKProvider()
    if normalized == BROWSER_HELPER_PROVIDER_PREFIX or normalized.startswith(f"{BROWSER_HELPER_PROVIDER_PREFIX}:"):
        raise JobSearchProviderError("browser_helper provider requires payload candidates.")
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
            source_kind="mock",
            detail_strategy="mock_inline",
        )
        return asdict(status)
    if normalized == "serper_web":
        provider = SerperWebSearchProvider()
        status = JobSearchProviderStatus(
            provider="serper_web",
            configured=provider.configured,
            available_providers=AVAILABLE_JOB_SEARCH_PROVIDERS,
            reason=None if provider.configured else "Set SERPER_API_KEY or JOBAGENT_SERPER_API_KEY.",
            base_url=None,
            search_url=SERPER_SEARCH_URL,
            allowlisted_domains=configured_serper_search_sites(),
            source_kind="search_engine",
            detail_strategy="search_result_snippet_only",
        )
        return asdict(status)
    if normalized == "linkedin":
        provider = LinkedInDiscoveryProvider()
        status = JobSearchProviderStatus(
            provider="linkedin",
            configured=provider.configured,
            available_providers=AVAILABLE_JOB_SEARCH_PROVIDERS,
            reason=None if provider.configured else "Set SERPER_API_KEY or JOBAGENT_SERPER_API_KEY.",
            base_url=None,
            search_url=SERPER_SEARCH_URL,
            allowlisted_domains=[LINKEDIN_SEARCH_SITE],
            source_kind="search_engine",
            detail_strategy="search_result_snippet_only",
        )
        return asdict(status)
    if normalized == "remoteok":
        status = JobSearchProviderStatus(
            provider="remoteok",
            configured=True,
            available_providers=AVAILABLE_JOB_SEARCH_PROVIDERS,
            reason="Uses RemoteOK public JSON API and preserves source attribution.",
            base_url="https://remoteok.com",
            search_url=REMOTEOK_API_URL,
            allowlisted_domains=["remoteok.com"],
            source_kind="native_api",
            detail_strategy="official_json_api",
        )
        return asdict(status)
    if normalized == BROWSER_HELPER_PROVIDER_PREFIX or normalized.startswith(f"{BROWSER_HELPER_PROVIDER_PREFIX}:"):
        status = JobSearchProviderStatus(
            provider="browser_helper",
            configured=True,
            available_providers=AVAILABLE_JOB_SEARCH_PROVIDERS,
            reason="Requires the JobAgent Browser Helper extension in Chrome or Edge for BOSS login-assisted search.",
            base_url=None,
            search_url=None,
            allowlisted_domains=["zhipin.com"],
            source_kind="browser_helper",
            detail_strategy="browser_extension_payload",
        )
        return asdict(status)
    if normalized == "multi_source" or normalized.startswith(MULTI_SOURCE_PREFIX):
        status = JobSearchProviderStatus(
            provider="multi_source",
            configured=True,
            available_providers=AVAILABLE_JOB_SEARCH_PROVIDERS,
            reason="Aggregates selected source providers; LinkedIn requires Serper configuration.",
            base_url=None,
            search_url=None,
            allowlisted_domains=["career.cuhk.edu.cn", LINKEDIN_SEARCH_SITE, "remoteok.com"],
            source_kind="hybrid",
            detail_strategy="mixed_source_strategy",
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
        source_kind="native_job_board",
        detail_strategy="native_list_and_detail_crawl",
    )
    return asdict(status)


def _dedupe_sources(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = value.strip()
        if not item or item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


__all__ = [
    "AVAILABLE_JOB_SEARCH_PROVIDERS",
    "AVAILABLE_JOB_SEARCH_SOURCES",
    "CUHKSZCareerProvider",
    "DEFAULT_JOB_SEARCH_PROVIDER",
    "JobSearchProvider",
    "JobSearchProviderError",
    "JobSearchProviderStatus",
    "LinkedInDiscoveryProvider",
    "MockJobSearchProvider",
    "MultiSourceJobSearchProvider",
    "BrowserHelperPayloadProvider",
    "RawJobCandidate",
    "RemoteOKProvider",
    "SerperWebSearchProvider",
    "encode_selected_sources",
    "get_job_search_provider_status",
    "normalize_job_search_provider_name",
    "normalize_job_search_source_name",
    "resolve_job_search_provider",
    "selected_sources_from_provider_name",
]
