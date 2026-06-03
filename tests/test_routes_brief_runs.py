from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_brief_run_from_search_endpoint_saves_and_returns_run(tmp_path: Path, monkeypatch) -> None:
    database_path = tmp_path / "brief-runs.sqlite3"
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(database_path))

    response = client.post(
        "/brief/runs/from-search",
        json={
            "resume_text": "Python FastAPI SQL LLM project experience",
            "query": "python backend jobs",
            "provider": "mock",
            "limit": 2,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["run_id"]
    assert payload["brief"]["provider"] == "mock"
    assert payload["brief"]["total_jobs"] == 2


def test_get_saved_brief_run_endpoint_returns_saved_brief(tmp_path: Path, monkeypatch) -> None:
    database_path = tmp_path / "brief-runs.sqlite3"
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(database_path))
    create_response = client.post(
        "/brief/runs/from-search",
        json={
            "resume_text": "Python FastAPI SQL LLM project experience",
            "query": "python backend jobs",
            "provider": "mock",
            "limit": 2,
        },
    )
    run_id = create_response.json()["run_id"]

    response = client.get(f"/brief/runs/{run_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["run_id"] == run_id
    assert payload["brief"]["recommended_jobs"]


def test_rerank_saved_brief_run_endpoint_returns_reranked_report(tmp_path: Path, monkeypatch) -> None:
    database_path = tmp_path / "brief-runs.sqlite3"
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(database_path))
    create_response = client.post(
        "/brief/runs/from-search",
        json={
            "resume_text": "Python FastAPI SQL LLM project experience",
            "query": "python backend jobs",
            "provider": "mock",
            "limit": 3,
        },
    )
    run_id = create_response.json()["run_id"]

    response = client.post(
        f"/brief/runs/{run_id}/rerank",
        json={
            "require_full_jd": False,
            "exclude_external_link_only": False,
            "location_keywords": ["remote"],
            "include_keywords": ["python"],
            "exclude_keywords": [],
            "min_fit_score": 50,
            "limit": 2,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_jobs"] == 2
    assert len(payload["recommended_jobs"]) == 2


def test_get_saved_brief_run_endpoint_returns_404_for_missing_run() -> None:
    response = client.get("/brief/runs/missing-run")

    assert response.status_code == 404
    payload = response.json()
    assert payload["error_code"] == "brief_run_not_found"
