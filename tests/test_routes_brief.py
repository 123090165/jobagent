from __future__ import annotations

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


def test_brief_from_search_endpoint_returns_job_brief_report() -> None:
    response = client.post(
        "/brief/from-search",
        json={
            "resume_text": "Python FastAPI SQL LLM project experience",
            "query": "python backend jobs",
            "provider": "mock",
            "limit": 3,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "mock"
    assert payload["total_jobs"] == 3
    assert len(payload["recommended_jobs"]) == 3


def test_brief_from_search_endpoint_returns_recommended_jobs() -> None:
    response = client.post(
        "/brief/from-search",
        json={
            "resume_text": "Python FastAPI SQL LLM project experience",
            "query": "python backend jobs",
            "provider": "mock",
            "limit": 2,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["recommended_jobs"]
    first_item = payload["recommended_jobs"][0]
    assert "job" in first_item
    assert "match_report" in first_item
    assert "fit_score" in first_item
    assert "advice" in first_item
    assert "fit_reasons" in first_item
    assert "risk_points" in first_item
    assert "scoring_quality" in first_item


def test_brief_from_search_endpoint_rejects_invalid_limit() -> None:
    response = client.post(
        "/brief/from-search",
        json={
            "resume_text": "resume text",
            "query": "python backend jobs",
            "provider": "mock",
            "limit": 0,
        },
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["error_code"] == "brief_limit_invalid"


def test_brief_from_search_endpoint_rejects_empty_resume() -> None:
    response = client.post(
        "/brief/from-search",
        json={
            "resume_text": "   ",
            "query": "python backend jobs",
            "provider": "mock",
            "limit": 3,
        },
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["error_code"] == "brief_resume_empty"


def test_brief_from_search_endpoint_rejects_empty_query() -> None:
    response = client.post(
        "/brief/from-search",
        json={
            "resume_text": "resume text",
            "query": "   ",
            "provider": "mock",
            "limit": 3,
        },
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["error_code"] == "brief_query_empty"


def test_brief_from_search_endpoint_uses_search_provider_unsupported() -> None:
    response = client.post(
        "/brief/from-search",
        json={
            "resume_text": "resume text",
            "query": "python backend jobs",
            "provider": "not-supported",
            "limit": 3,
        },
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["error_code"] == "search_provider_unsupported"


def test_brief_from_search_endpoint_supports_local_db_provider(tmp_path, monkeypatch) -> None:
    database_path = tmp_path / "brief-local.sqlite3"
    save_public_job_post(_build_local_detail(), database_path=database_path)
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(database_path))

    response = client.post(
        "/brief/from-search",
        json={
            "resume_text": "Python FastAPI SQL LLM project experience",
            "query": "AI Platform",
            "provider": "local_db",
            "limit": 1,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "local_db"
    assert payload["total_jobs"] == 1
    assert payload["recommended_jobs"][0]["job"]["source"] == "cuhksz_career"
