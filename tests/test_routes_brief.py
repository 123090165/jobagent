from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.schemas.cuhksz_career import CUHKSZJobDetail, CUHKSZJobListItem
from app.services import batch_brief_service
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


def test_brief_search_plan_endpoint_returns_structured_plan() -> None:
    response = client.post(
        "/brief/search-plan",
        json={
            "query": "backend internship",
            "profile_context": {
                "confirmed_profile": {
                    "raw_text": "profile context test resume",
                    "skills": ["Python", "FastAPI"],
                },
                "user_confirmed_data": {
                    "target_roles": ["AI Agent Engineer"],
                    "preferred_locations": ["Shenzhen"],
                    "additional_skills": ["LangGraph"],
                    "constraints": ["Prefer backend roles"],
                },
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["original_query"] == "backend internship"
    assert payload["effective_query"].startswith("backend internship")
    assert payload["profile_context_used"] is True
    assert payload["role_terms"] == ["AI Agent Engineer"]
    assert payload["location_terms"] == ["Shenzhen"]
    assert "LangGraph" in payload["skill_terms"]
    assert "Python" in payload["skill_terms"]


def test_brief_search_plan_endpoint_supports_empty_query_with_profile_context() -> None:
    response = client.post(
        "/brief/search-plan",
        json={
            "query": "",
            "profile_context": {
                "confirmed_profile": {
                    "raw_text": "profile context test resume",
                    "skills": ["Python"],
                },
                "user_confirmed_data": {
                    "target_roles": ["AI Agent Engineer"],
                },
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["original_query"] == ""
    assert payload["effective_query"]
    assert "effective query was generated only from profile context" in payload["warnings"]


def test_brief_search_plan_endpoint_without_profile_context_keeps_query() -> None:
    response = client.post(
        "/brief/search-plan",
        json={"query": "backend internship"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["effective_query"] == "backend internship"
    assert payload["profile_context_used"] is False


def test_brief_search_plan_endpoint_allows_empty_query_without_context() -> None:
    response = client.post(
        "/brief/search-plan",
        json={"query": ""},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["effective_query"] == ""
    assert payload["profile_context_used"] is False


def test_brief_search_plan_endpoint_does_not_call_provider(monkeypatch) -> None:
    def fail_search_jobs(*args, **kwargs):
        raise AssertionError("search_jobs should not be called by /brief/search-plan")

    monkeypatch.setattr(batch_brief_service, "search_jobs", fail_search_jobs)

    response = client.post(
        "/brief/search-plan",
        json={"query": "backend internship"},
    )

    assert response.status_code == 200
    assert response.json()["effective_query"] == "backend internship"


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
