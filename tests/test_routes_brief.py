from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


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
