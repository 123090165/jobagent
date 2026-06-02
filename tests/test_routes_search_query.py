from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_search_queries_from_resume_endpoint_returns_queries() -> None:
    response = client.post(
        "/search/queries/from-resume",
        json={
            "resume_text": "Python FastAPI SQL backend experience with Streamlit demos.",
            "max_queries": 4,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["queries"]
    assert any("Python Backend Engineer" in query for query in payload["queries"])


def test_search_queries_from_resume_endpoint_returns_business_error_for_empty_resume() -> None:
    response = client.post(
        "/search/queries/from-resume",
        json={"resume_text": "   ", "max_queries": 5},
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["detail"] == "Resume text cannot be empty for search query generation"
    assert payload["error_code"] == "search_query_resume_empty"


def test_search_queries_from_resume_endpoint_returns_business_error_for_invalid_limit() -> None:
    response = client.post(
        "/search/queries/from-resume",
        json={"resume_text": "Python FastAPI", "max_queries": 11},
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["detail"] == "Search query count must be between 1 and 10"
    assert payload["error_code"] == "search_query_limit_invalid"
