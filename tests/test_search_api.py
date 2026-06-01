from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


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
    assert response.json()["detail"] == "Search provider is not supported"
    assert response.json()["error_code"] == "search_provider_unsupported"
