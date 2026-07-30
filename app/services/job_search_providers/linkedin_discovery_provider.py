"""通过受控搜索引擎发现 LinkedIn 职位链接，不直接绕过站点登录或反爬。"""

from __future__ import annotations

from urllib.parse import urlparse

from app.services.job_search_providers.base import RawJobCandidate
from app.services.job_search_providers.serper_web_provider import SerperWebSearchProvider

LINKEDIN_SEARCH_SITE = "linkedin.com/jobs"


class LinkedInDiscoveryProvider:
    """把linkedindiscovery接入统一 Provider 协议。"""
    provider_name = "linkedin"
    provider_kind = "search_engine"
    detail_strategy = "search_result_snippet_only"

    def __init__(self, *, serper_provider: SerperWebSearchProvider | None = None) -> None:
        self.serper_provider = serper_provider or SerperWebSearchProvider(search_sites=[LINKEDIN_SEARCH_SITE])

    @property
    def configured(self) -> bool:
        return self.serper_provider.configured

    def search_jobs(self, *, query: str, location: str | None, limit: int) -> list[RawJobCandidate]:
        raw_items = self.serper_provider.search_jobs(query=query, location=location, limit=max(limit * 2, limit))
        candidates: list[RawJobCandidate] = []
        for item in raw_items:
            if not _is_linkedin_job_view(item.source_url):
                continue
            candidates.append(
                item.model_copy(
                    update={
                        "source_provider": self.provider_name,
                        "company": item.company or "LinkedIn",
                        "detail_status": "linkedin_external_link",
                        "provider_warnings": item.provider_warnings
                        + ["LinkedIn result is preserved as an external link; detail scraping is not performed."],
                    }
                )
            )
            if len(candidates) >= limit:
                break
        return candidates


def _is_linkedin_job_view(url: str | None) -> bool:
    if not url:
        return False
    parsed = urlparse(url)
    host = parsed.netloc.lower().removeprefix("www.")
    if not (host == "linkedin.com" or host.endswith(".linkedin.com")):
        return False
    path = parsed.path.lower()
    if path.startswith("/in/") or path.startswith("/company/"):
        return False
    return path.startswith("/jobs/view/")
