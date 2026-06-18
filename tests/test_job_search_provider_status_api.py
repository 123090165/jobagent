from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.services.job_search_providers import (
    get_job_search_provider_status,
    normalize_job_search_provider_name,
)

client = TestClient(app)


def test_provider_resolver_supports_curated_aliases(monkeypatch) -> None:
    monkeypatch.setenv("JOBAGENT_JOB_SEARCH_PROVIDER", "curated_crawler")

    assert normalize_job_search_provider_name("curated") == "curated_crawler"
    assert normalize_job_search_provider_name("crawler") == "curated_crawler"
    assert normalize_job_search_provider_name(None) == "curated_crawler"


def test_provider_status_endpoint_works(monkeypatch) -> None:
    monkeypatch.setenv("JOBAGENT_JOB_SEARCH_PROVIDER", "curated_crawler")
    monkeypatch.setenv("JOBAGENT_CURATED_JOB_DOMAINS", "boards.greenhouse.io,jobs.lever.co")

    response = client.get("/api/v1/job-search-providers/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "curated_crawler"
    assert payload["configured"] is True
    assert "curated_crawler" in payload["available_providers"]
    assert "boards.greenhouse.io" in payload["allowlisted_domains"]


def test_tavily_status_reports_missing_api_key(monkeypatch) -> None:
    monkeypatch.setenv("JOBAGENT_JOB_SEARCH_PROVIDER", "tavily")
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)

    status = get_job_search_provider_status()

    assert status["provider"] == "tavily"
    assert status["configured"] is False
    assert status["reason"] == "TAVILY_API_KEY is empty."
