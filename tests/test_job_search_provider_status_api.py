"""回归验证职位搜索来源状态的正常链路、失败边界和兼容契约。"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.services.job_search_providers import (
    encode_selected_sources,
    get_job_search_provider_status,
    normalize_job_search_provider_name,
    selected_sources_from_provider_name,
)

client = TestClient(app)


def test_provider_resolver_defaults_to_cuhksz(monkeypatch) -> None:
    monkeypatch.setenv("JOBAGENT_JOB_SEARCH_PROVIDER", "cuhksz_career")

    assert normalize_job_search_provider_name(None) == "cuhksz_career"


def test_provider_resolver_supports_cuhksz_aliases() -> None:
    assert normalize_job_search_provider_name("cuhksz") == "cuhksz_career"
    assert normalize_job_search_provider_name("cuhk") == "cuhksz_career"
    assert normalize_job_search_provider_name("career_cuhk") == "cuhksz_career"


def test_provider_resolver_supports_web_search_aliases() -> None:
    assert normalize_job_search_provider_name("serper") == "serper_web"
    assert normalize_job_search_provider_name("web_search") == "serper_web"


def test_provider_resolver_supports_selected_source_aliases() -> None:
    assert normalize_job_search_provider_name("linkedin_jobs") == "linkedin"
    assert normalize_job_search_provider_name("remote_ok") == "remoteok"
    assert encode_selected_sources(["cuhksz", "linkedin", "remote_ok"]) == (
        "multi_source:cuhksz_career,linkedin,remoteok"
    )
    assert selected_sources_from_provider_name("multi_source:cuhksz_career,linkedin,remoteok") == [
        "cuhksz_career",
        "linkedin",
        "remoteok",
    ]
    assert selected_sources_from_provider_name("browser_helper:boss,cuhksz_career,remoteok") == [
        "cuhksz_career",
        "remoteok",
    ]


def test_provider_status_endpoint_reports_cuhksz() -> None:
    response = client.get("/api/v1/job-search-providers/status", params={"provider": "cuhksz_career"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "cuhksz_career"
    assert payload["configured"] is True
    assert payload["available_providers"] == [
        "mock",
        "cuhksz_career",
        "linkedin",
        "remoteok",
        "serper_web",
        "browser_helper",
        "multi_source",
    ]
    assert payload["base_url"] == "https://career.cuhk.edu.cn"
    assert payload["search_url"] == "https://career.cuhk.edu.cn/job/search"
    assert payload["allowlisted_domains"] == ["career.cuhk.edu.cn"]
    assert payload["source_kind"] == "native_job_board"
    assert payload["detail_strategy"] == "native_list_and_detail_crawl"


def test_provider_status_helper_reports_mock() -> None:
    status = get_job_search_provider_status("mock")

    assert status["provider"] == "mock"
    assert status["configured"] is True
    assert status["search_url"] is None


def test_provider_status_helper_reports_serper_configuration(monkeypatch) -> None:
    monkeypatch.setenv("JOBAGENT_SERPER_API_KEY", "test-key")
    monkeypatch.setenv("JOBAGENT_WEB_SEARCH_SITES", "career.example.com,jobs.example.org")

    status = get_job_search_provider_status("serper_web")

    assert status["provider"] == "serper_web"
    assert status["configured"] is True
    assert status["source_kind"] == "search_engine"
    assert status["detail_strategy"] == "search_result_snippet_only"
    assert status["allowlisted_domains"] == ["career.example.com", "jobs.example.org"]


def test_provider_status_helper_reports_linkedin_configuration(monkeypatch) -> None:
    monkeypatch.setenv("JOBAGENT_SERPER_API_KEY", "test-key")

    status = get_job_search_provider_status("linkedin")

    assert status["provider"] == "linkedin"
    assert status["configured"] is True
    assert status["source_kind"] == "search_engine"
    assert status["allowlisted_domains"] == ["linkedin.com/jobs"]


def test_provider_status_helper_reports_remoteok() -> None:
    status = get_job_search_provider_status("remoteok")

    assert status["provider"] == "remoteok"
    assert status["configured"] is True
    assert status["source_kind"] == "native_api"
    assert status["allowlisted_domains"] == ["remoteok.com"]


def test_provider_status_helper_reports_browser_helper() -> None:
    status = get_job_search_provider_status("browser_helper")

    assert status["provider"] == "browser_helper"
    assert status["configured"] is True
    assert status["source_kind"] == "browser_helper"
    assert status["detail_strategy"] == "browser_extension_payload"
    assert status["allowlisted_domains"] == ["zhipin.com"]


def test_provider_status_helper_reports_multi_source() -> None:
    status = get_job_search_provider_status("multi_source:cuhksz_career,linkedin,remoteok")

    assert status["provider"] == "multi_source"
    assert status["configured"] is True
    assert status["source_kind"] == "hybrid"
    assert "linkedin.com/jobs" in status["allowlisted_domains"]
