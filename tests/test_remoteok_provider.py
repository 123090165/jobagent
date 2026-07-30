"""回归验证remoteok provider的正常链路、失败边界和兼容契约。"""

from __future__ import annotations

import json
from urllib.request import Request

import pytest

from app.services.job_search_providers import JobSearchProviderError
from app.services.job_search_providers.remoteok_provider import REMOTEOK_API_URL, RemoteOKProvider


def test_remoteok_provider_maps_api_records_to_candidates() -> None:
    def fake_fetcher(request: Request) -> bytes:
        assert request.full_url == REMOTEOK_API_URL
        return json.dumps(
            [
                {"legal": "metadata row without id is ignored"},
                {
                    "id": "job-1",
                    "company": "Acme Remote",
                    "position": "Marketing Operations Intern",
                    "location": "Remote",
                    "tags": ["marketing", "research", "operations"],
                    "description": "<p>Support market research and campaign analysis.</p>",
                    "url": "https://remoteok.com/remote-jobs/job-1",
                    "salary_min": 1000,
                    "salary_max": 2000,
                },
            ]
        ).encode("utf-8")

    provider = RemoteOKProvider(fetcher=fake_fetcher)

    candidates = provider.search_jobs(query="marketing intern", location=None, limit=5)

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.title == "Marketing Operations Intern"
    assert candidate.company == "Acme Remote"
    assert candidate.location == "Remote"
    assert candidate.source_provider == "remoteok"
    assert candidate.source_url == "https://remoteok.com/remote-jobs/job-1"
    assert candidate.detail_status == "official_json_api"
    assert "Support market research" in (candidate.raw_description or "")
    assert any("RemoteOK API source" in warning for warning in candidate.provider_warnings)


def test_remoteok_provider_filters_by_query_without_inventing_matches() -> None:
    payload = [
        {
            "id": "job-1",
            "company": "Acme Remote",
            "position": "Backend Engineer",
            "location": "Remote",
            "tags": ["python"],
            "description": "Build APIs.",
            "url": "https://remoteok.com/remote-jobs/job-1",
        }
    ]
    provider = RemoteOKProvider(fetcher=lambda _request: json.dumps(payload).encode("utf-8"))

    assert provider.search_jobs(query="brand marketing", location=None, limit=5) == []


def test_remoteok_provider_reports_invalid_json() -> None:
    provider = RemoteOKProvider(fetcher=lambda _request: b"not-json")

    with pytest.raises(JobSearchProviderError, match="invalid JSON"):
        provider.search_jobs(query="python", location=None, limit=5)
