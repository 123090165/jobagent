from __future__ import annotations

import json
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import app
from app.schemas.cuhksz_career import CUHKSZJobDetail, CUHKSZJobListItem
from app.services.public_job_storage_service import save_public_job_post

client = TestClient(app)


def _build_local_detail() -> CUHKSZJobDetail:
    jd_text = (
        "Responsibilities:\n"
        "- Build Python and FastAPI services.\n"
        "Requirements:\n"
        "- Strong SQL and testing fundamentals.\n"
        "Skills: Python, FastAPI, SQL"
    )
    return CUHKSZJobDetail(
        list_item=CUHKSZJobListItem(
            external_id="468293",
            title="AI Platform Intern",
            company="Example Tech",
            location="Shenzhen",
            job_type="Intern",
            education="Bachelor",
            published_at="2026-05-30",
            deadline="2026-07-01",
            detail_url="https://career.cuhk.edu.cn/job/view/id/468293",
        ),
        jd_text=jd_text,
        snippet=jd_text[:120],
        is_full_jd=True,
        confidence=0.88,
        warnings=[],
    )


def test_search_jobs_endpoint_returns_mock_results() -> None:
    response = client.post(
        "/search/jobs",
        json={"query": "python backend", "provider": "mock", "limit": 2},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "mock"
    assert payload["query"] == "python backend"
    assert len(payload["items"]) == 2
    assert payload["items"][0]["source"] == "mock"


def test_search_jobs_endpoint_rejects_invalid_query() -> None:
    response = client.post(
        "/search/jobs",
        json={"query": "   ", "provider": "mock", "limit": 5},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Search query cannot be empty"
    assert response.json()["error_code"] == "search_query_invalid"


def test_search_jobs_endpoint_rejects_limit_below_range() -> None:
    response = client.post(
        "/search/jobs",
        json={"query": "python backend", "provider": "mock", "limit": 0},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Search limit must be between 1 and 20"
    assert response.json()["error_code"] == "search_limit_invalid"


def test_search_jobs_endpoint_rejects_limit_above_range() -> None:
    response = client.post(
        "/search/jobs",
        json={"query": "python backend", "provider": "mock", "limit": 21},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Search limit must be between 1 and 20"
    assert response.json()["error_code"] == "search_limit_invalid"


def test_search_jobs_endpoint_rejects_unsupported_provider() -> None:
    response = client.post(
        "/search/jobs",
        json={"query": "python backend", "provider": "gemini_cli", "limit": 5},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Gemini CLI search provider is disabled"
    assert response.json()["error_code"] == "search_provider_disabled"


def test_search_jobs_endpoint_supports_local_db_provider(tmp_path, monkeypatch) -> None:
    database_path = tmp_path / "search-api.sqlite3"
    save_public_job_post(_build_local_detail(), database_path=database_path)
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(database_path))

    response = client.post(
        "/search/jobs",
        json={"query": "AI Platform", "provider": "local_db", "limit": 5},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "local_db"
    assert len(payload["items"]) == 1
    assert payload["items"][0]["source"] == "cuhksz_career"
    assert payload["items"][0]["skills"] == ["Python", "FastAPI", "SQL"]


def test_search_jobs_endpoint_supports_gemini_cli_provider_when_enabled(monkeypatch) -> None:
    monkeypatch.setenv("JOBAGENT_ENABLE_GEMINI_CLI", "1")

    def fake_run(command, **kwargs):
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps(
                {
                    "items": [
                        {
                            "title": "Python Backend Engineer",
                            "company": "Example Co",
                            "location": "Remote",
                            "url": "https://example.com/jobs/python-backend",
                            "snippet": "Build FastAPI services and workflow APIs.",
                        }
                    ]
                }
            ),
            stderr="",
        )

    monkeypatch.setattr("app.services.search_providers.gemini_cli_provider.subprocess.run", fake_run)

    response = client.post(
        "/search/jobs",
        json={"query": "python backend", "provider": "gemini_cli", "limit": 5},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "gemini_cli"
    assert len(payload["items"]) == 1
    assert payload["items"][0]["source"] == "gemini_cli"
