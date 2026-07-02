from __future__ import annotations

import json
import urllib.request

import pytest

from app.services.job_search_providers.base import JobSearchProviderError
from app.services.job_search_providers.serper_web_provider import (
    SerperWebSearchProvider,
    build_serper_query,
)


def test_build_serper_query_uses_optional_site_filters_without_hardcoding_platforms() -> None:
    query = build_serper_query(
        "Brand Marketing Intern",
        location="Shanghai",
        search_sites=["career.example.com", "jobs.example.org"],
    )

    assert "site:career.example.com" in query
    assert "site:jobs.example.org" in query
    assert "Brand Marketing Intern" in query
    assert "Shanghai" in query


def test_serper_provider_maps_search_results_without_network() -> None:
    captured: dict[str, object] = {}

    def fake_fetcher(request: urllib.request.Request) -> bytes:
        captured["url"] = request.full_url
        captured["headers"] = dict(request.header_items())
        captured["payload"] = json.loads((request.data or b"{}").decode("utf-8"))
        return json.dumps(
            {
                "organic": [
                    {
                        "title": "Brand Marketing Intern",
                        "link": "https://career.example.com/jobs/brand-marketing-intern",
                        "displayLink": "career.example.com",
                        "snippet": "Brand campaign planning, consumer research, and social media content.",
                    }
                ]
            }
        ).encode("utf-8")

    provider = SerperWebSearchProvider(
        api_key="test-key",
        search_sites=["career.example.com"],
        fetcher=fake_fetcher,
    )

    candidates = provider.search_jobs(query="Brand Marketing Intern", location="Shanghai", limit=5)

    assert captured["url"] == "https://google.serper.dev/search"
    assert captured["payload"]["q"] == "site:career.example.com Brand Marketing Intern Shanghai"
    assert candidates[0].title == "Brand Marketing Intern"
    assert candidates[0].company == "career.example.com"
    assert candidates[0].source_provider == "serper_web"
    assert candidates[0].source_url == "https://career.example.com/jobs/brand-marketing-intern"
    assert candidates[0].discovery_query == captured["payload"]["q"]
    assert candidates[0].detail_status == "search_result_snippet_only"
    assert candidates[0].provider_warnings


def test_serper_provider_requires_api_key(monkeypatch) -> None:
    monkeypatch.delenv("SERPER_API_KEY", raising=False)
    monkeypatch.delenv("JOBAGENT_SERPER_API_KEY", raising=False)
    provider = SerperWebSearchProvider(api_key="", fetcher=lambda _request: b"{}")

    with pytest.raises(JobSearchProviderError, match="API key"):
        provider.search_jobs(query="Marketing Intern", location=None, limit=5)
