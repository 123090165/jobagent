from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urlparse

from app.services.job_search_providers.adapters import (
    GreenhouseAdapter,
    JobSiteAdapter,
    LeverAdapter,
)
from app.services.job_search_providers.base import (
    JobSearchProviderError,
    RawJobCandidate,
)


@dataclass(frozen=True)
class CuratedCrawlerStatus:
    configured: bool
    reason: str | None
    allowlisted_domains: list[str]


class CuratedCrawlerProvider:
    provider_name = "curated_crawler"

    def __init__(
        self,
        *,
        adapters: list[JobSiteAdapter] | None = None,
        allowlisted_domains: list[str] | None = None,
    ) -> None:
        self.adapters = adapters or [GreenhouseAdapter(), LeverAdapter()]
        self.allowlisted_domains = allowlisted_domains or get_curated_job_domains()
        self.active_adapters = [
            adapter
            for adapter in self.adapters
            if _adapter_allowed(adapter, self.allowlisted_domains)
        ]
        self.configured = bool(self.active_adapters)
        self.reason = None if self.configured else "No allowlisted adapter domains are enabled."

    def search_jobs(self, *, query: str, location: str | None, limit: int) -> list[RawJobCandidate]:
        if not self.active_adapters:
            raise JobSearchProviderError("Curated crawler has no active adapters for the allowlisted domains.")

        per_adapter_limit = max(1, limit)
        deduped: dict[str, RawJobCandidate] = {}
        for adapter in self.active_adapters:
            candidates = adapter.search_jobs(query=query, location=location, limit=per_adapter_limit)
            for candidate in candidates:
                enriched = self._enrich_candidate(adapter, candidate)
                key = (enriched.source_url or f"{enriched.title}:{enriched.company}:{enriched.location}").lower()
                deduped.setdefault(key, enriched)
                if len(deduped) >= limit:
                    return list(deduped.values())[:limit]
        return list(deduped.values())[:limit]

    @classmethod
    def status(cls, *, allowlisted_domains: list[str] | None = None) -> CuratedCrawlerStatus:
        provider = cls(allowlisted_domains=allowlisted_domains)
        return CuratedCrawlerStatus(
            configured=provider.configured,
            reason=provider.reason,
            allowlisted_domains=provider.allowlisted_domains,
        )

    @classmethod
    def default_allowlisted_domains(cls) -> list[str]:
        return get_curated_job_domains()

    def _enrich_candidate(self, adapter: JobSiteAdapter, candidate: RawJobCandidate) -> RawJobCandidate:
        try:
            return adapter.fetch_job_detail(candidate)
        except Exception as exc:
            return candidate.model_copy(
                update={
                    "provider_warnings": candidate.provider_warnings + [f"Detail fetch skipped: {type(exc).__name__}."],
                }
            )


def get_curated_job_domains() -> list[str]:
    raw = os.getenv("JOBAGENT_CURATED_JOB_DOMAINS", "")
    if raw.strip():
        values = [_normalize_domain(item) for item in raw.split(",")]
        return sorted({value for value in values if value})
    domains: set[str] = set()
    for adapter in [GreenhouseAdapter(), LeverAdapter()]:
        domains.update(adapter.allowed_domains)
        for url in adapter.listing_urls:
            host = _normalize_domain(urlparse(url).netloc)
            if host:
                domains.add(host)
    return sorted(domains)


def _adapter_allowed(adapter: JobSiteAdapter, allowlisted_domains: list[str]) -> bool:
    adapter_domains = {_normalize_domain(domain) for domain in adapter.allowed_domains}
    return any(domain in allowlisted_domains for domain in adapter_domains)


def _normalize_domain(value: str) -> str:
    text = value.strip().lower()
    if not text:
        return ""
    if "://" in text:
        return urlparse(text).netloc.lower().replace("www.", "")
    return text.replace("www.", "")
