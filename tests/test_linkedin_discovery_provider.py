"""回归验证linkedin discovery provider的正常链路、失败边界和兼容契约。"""

from __future__ import annotations

from app.services.job_search_providers.base import RawJobCandidate
from app.services.job_search_providers.linkedin_discovery_provider import LinkedInDiscoveryProvider


class FakeSerperProvider:
    """把fakeserper接入统一 Provider 协议。"""
    provider_name = "serper_web"
    provider_kind = "search_engine"
    configured = True

    def search_jobs(self, *, query: str, location: str | None, limit: int) -> list[RawJobCandidate]:
        """提供 FakeSerperProvider.search_jobs 所需的测试行为。"""
        assert query == "brand marketing intern"
        assert location == "Shanghai"
        assert limit == 6
        return [
            RawJobCandidate(
                title="Brand Marketing Intern",
                company="LinkedIn",
                location=location,
                source_url="https://www.linkedin.com/jobs/view/123456",
                source_provider="serper_web",
                snippet="A public LinkedIn job result.",
                raw_description="A public LinkedIn job result.",
                discovery_query=query,
                discovery_rank=1,
                detail_status="search_result_snippet_only",
            ),
            RawJobCandidate(
                title="Hiring Manager Profile",
                company="LinkedIn",
                location=location,
                source_url="https://www.linkedin.com/in/example",
                source_provider="serper_web",
                snippet="Profile page.",
                raw_description="Profile page.",
                discovery_query=query,
                discovery_rank=2,
                detail_status="search_result_snippet_only",
            ),
            RawJobCandidate(
                title="Marketing jobs list",
                company="LinkedIn",
                location=location,
                source_url="https://www.linkedin.com/jobs/marketing-jobs",
                source_provider="serper_web",
                snippet="Broad list page.",
                raw_description="Broad list page.",
                discovery_query=query,
                discovery_rank=3,
                detail_status="search_result_snippet_only",
            ),
        ]


def test_linkedin_discovery_keeps_only_specific_job_view_links() -> None:
    provider = LinkedInDiscoveryProvider(serper_provider=FakeSerperProvider())

    candidates = provider.search_jobs(query="brand marketing intern", location="Shanghai", limit=3)

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.source_provider == "linkedin"
    assert candidate.source_url == "https://www.linkedin.com/jobs/view/123456"
    assert candidate.detail_status == "linkedin_external_link"
    assert any("external link" in warning for warning in candidate.provider_warnings)


def test_linkedin_discovery_exposes_serper_configuration_state() -> None:
    provider = LinkedInDiscoveryProvider(serper_provider=FakeSerperProvider())

    assert provider.configured is True
