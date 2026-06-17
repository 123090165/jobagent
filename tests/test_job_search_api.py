from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _create_session_with_confirmed_profile(
    tmp_path,
    monkeypatch,
    name: str = "job-search.sqlite3",
) -> dict:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / name))
    session = client.post("/api/v1/profile-sessions").json()
    client.post(
        f"/api/v1/profile-sessions/{session['session_id']}/resume-text",
        json={
            "text": (
                "Name: Jane Doe\n"
                "Role: Backend Engineer\n"
                "Skills: Python, FastAPI, SQL, LangGraph, Docker\n"
                "Project: Built JobAgent resume review flow with pytest coverage.\n"
            )
        },
    )
    client.post(f"/api/v1/profile-sessions/{session['session_id']}/parse-resume")
    draft = client.post(
        f"/api/v1/profile-sessions/{session['session_id']}/profile-draft"
    ).json()
    confirmed = client.post(
        f"/api/v1/profile-drafts/{draft['profile_draft']['profile_draft_id']}/confirm"
    ).json()
    return confirmed


def test_job_search_requires_existing_session(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / "job-search-missing-session.sqlite3"))

    response = client.post("/api/v1/job-search-runs", json={"session_id": "missing"})

    assert response.status_code == 404
    assert response.json()["error_code"] == "profile_session_not_found"


def test_job_search_requires_confirmed_profile(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / "job-search-no-confirmed.sqlite3"))
    session = client.post("/api/v1/profile-sessions").json()

    response = client.post("/api/v1/job-search-runs", json={"session_id": session["session_id"]})

    assert response.status_code == 409
    assert response.json()["error_code"] == "confirmed_profile_required"


def test_job_search_creates_run_and_updates_session(monkeypatch, tmp_path) -> None:
    confirmed = _create_session_with_confirmed_profile(tmp_path, monkeypatch, "job-search-create.sqlite3")

    response = client.post(
        "/api/v1/job-search-runs",
        json={"session_id": confirmed["profile_session"]["session_id"]},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["job_search_run"]["job_search_run_id"]
    assert payload["profile_session"]["current_step"] == "job_search_completed"
    assert len(payload["job_search_run"]["results"]) >= 5


def test_job_search_uses_local_mock_source(monkeypatch, tmp_path) -> None:
    confirmed = _create_session_with_confirmed_profile(tmp_path, monkeypatch, "job-search-source.sqlite3")

    response = client.post(
        "/api/v1/job-search-runs",
        json={"session_id": confirmed["profile_session"]["session_id"]},
    )

    results = response.json()["job_search_run"]["results"]
    assert all(item["source"] == "local_mock" for item in results)


def test_job_search_results_have_expected_fields(monkeypatch, tmp_path) -> None:
    confirmed = _create_session_with_confirmed_profile(tmp_path, monkeypatch, "job-search-fields.sqlite3")

    response = client.post(
        "/api/v1/job-search-runs",
        json={"session_id": confirmed["profile_session"]["session_id"]},
    )

    first = response.json()["job_search_run"]["results"][0]
    assert first["title"]
    assert first["company"]
    assert first["location"]
    assert isinstance(first["match_score"], int)
    assert isinstance(first["match_reasons"], list)


def test_get_job_search_run_returns_run(monkeypatch, tmp_path) -> None:
    confirmed = _create_session_with_confirmed_profile(tmp_path, monkeypatch, "job-search-get.sqlite3")
    created = client.post(
        "/api/v1/job-search-runs",
        json={"session_id": confirmed["profile_session"]["session_id"]},
    ).json()

    response = client.get(f"/api/v1/job-search-runs/{created['job_search_run']['job_search_run_id']}")

    assert response.status_code == 200
    assert (
        response.json()["job_search_run"]["job_search_run_id"]
        == created["job_search_run"]["job_search_run_id"]
    )


def test_get_missing_job_search_run_returns_not_found(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / "job-search-missing-run.sqlite3"))

    response = client.get("/api/v1/job-search-runs/missing-run")

    assert response.status_code == 404
    assert response.json()["error_code"] == "job_search_run_not_found"


def test_list_job_search_runs_by_session_returns_runs(monkeypatch, tmp_path) -> None:
    confirmed = _create_session_with_confirmed_profile(tmp_path, monkeypatch, "job-search-list.sqlite3")
    session_id = confirmed["profile_session"]["session_id"]
    client.post("/api/v1/job-search-runs", json={"session_id": session_id})

    response = client.get(f"/api/v1/profile-sessions/{session_id}/job-search-runs")

    assert response.status_code == 200
    assert len(response.json()["items"]) == 1


def test_job_search_does_not_require_network_or_llm(monkeypatch, tmp_path) -> None:
    confirmed = _create_session_with_confirmed_profile(tmp_path, monkeypatch, "job-search-local-only.sqlite3")

    response = client.post(
        "/api/v1/job-search-runs",
        json={"session_id": confirmed["profile_session"]["session_id"]},
    )

    assert response.status_code == 200
    assert response.json()["job_search_run"]["status"] == "completed"
