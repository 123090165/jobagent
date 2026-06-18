from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.services.job_search_providers import (
    get_job_search_provider_status,
    normalize_job_search_provider_name,
)

client = TestClient(app)


def test_provider_resolver_defaults_to_cuhksz(monkeypatch) -> None:
    monkeypatch.setenv("JOBAGENT_JOB_SEARCH_PROVIDER", "cuhksz_career")

    assert normalize_job_search_provider_name(None) == "cuhksz_career"


def test_provider_resolver_supports_cuhksz_aliases() -> None:
    assert normalize_job_search_provider_name("cuhksz") == "cuhksz_career"
    assert normalize_job_search_provider_name("cuhk") == "cuhksz_career"
    assert normalize_job_search_provider_name("career_cuhk") == "cuhksz_career"


def test_provider_status_endpoint_reports_cuhksz() -> None:
    response = client.get("/api/v1/job-search-providers/status", params={"provider": "cuhksz_career"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "cuhksz_career"
    assert payload["configured"] is True
    assert payload["available_providers"] == ["mock", "cuhksz_career"]
    assert payload["base_url"] == "https://career.cuhk.edu.cn"
    assert payload["search_url"] == "https://career.cuhk.edu.cn/job/search"
    assert payload["allowlisted_domains"] == ["career.cuhk.edu.cn"]


def test_provider_status_helper_reports_mock() -> None:
    status = get_job_search_provider_status("mock")

    assert status["provider"] == "mock"
    assert status["configured"] is True
    assert status["search_url"] is None
