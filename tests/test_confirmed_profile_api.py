from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _create_session_with_draft(tmp_path, monkeypatch, name: str = "confirmed-profile.sqlite3") -> dict:
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
    return client.post(f"/api/v1/profile-sessions/{session['session_id']}/profile-draft").json()


def test_confirm_requires_existing_draft(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / "confirm-missing-draft.sqlite3"))

    response = client.post("/api/v1/profile-drafts/missing-draft/confirm")

    assert response.status_code == 404
    assert response.json()["error_code"] == "profile_draft_not_found"


def test_confirm_creates_confirmed_profile_and_updates_session(monkeypatch, tmp_path) -> None:
    created = _create_session_with_draft(tmp_path, monkeypatch, "confirm-create.sqlite3")
    draft = created["profile_draft"]

    response = client.post(f"/api/v1/profile-drafts/{draft['profile_draft_id']}/confirm")

    assert response.status_code == 200
    payload = response.json()
    assert payload["confirmed_profile"]["confirmed_profile_id"]
    assert payload["confirmed_profile"]["profile_draft_id"] == draft["profile_draft_id"]
    assert payload["confirmed_profile"]["summary"] == draft["summary"]
    assert payload["profile_session"]["current_step"] == "job_search_ready"
    assert (
        payload["profile_session"]["confirmed_profile_id"]
        == payload["confirmed_profile"]["confirmed_profile_id"]
    )


def test_confirm_is_idempotent_by_default_for_same_draft(monkeypatch, tmp_path) -> None:
    created = _create_session_with_draft(tmp_path, monkeypatch, "confirm-idempotent.sqlite3")
    draft_id = created["profile_draft"]["profile_draft_id"]

    first = client.post(f"/api/v1/profile-drafts/{draft_id}/confirm").json()
    second = client.post(f"/api/v1/profile-drafts/{draft_id}/confirm").json()

    assert (
        first["confirmed_profile"]["confirmed_profile_id"]
        == second["confirmed_profile"]["confirmed_profile_id"]
    )


def test_get_confirmed_profile_returns_profile(monkeypatch, tmp_path) -> None:
    created = _create_session_with_draft(tmp_path, monkeypatch, "confirm-get.sqlite3")
    confirmed = client.post(
        f"/api/v1/profile-drafts/{created['profile_draft']['profile_draft_id']}/confirm"
    ).json()

    response = client.get(
        f"/api/v1/confirmed-profiles/{confirmed['confirmed_profile']['confirmed_profile_id']}"
    )

    assert response.status_code == 200
    assert (
        response.json()["confirmed_profile"]["confirmed_profile_id"]
        == confirmed["confirmed_profile"]["confirmed_profile_id"]
    )


def test_get_missing_confirmed_profile_returns_not_found(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / "confirm-missing.sqlite3"))

    response = client.get("/api/v1/confirmed-profiles/missing-confirmed")

    assert response.status_code == 404
    assert response.json()["error_code"] == "confirmed_profile_not_found"


def test_patch_draft_after_confirmation_invalidates_confirmed_profile(monkeypatch, tmp_path) -> None:
    created = _create_session_with_draft(tmp_path, monkeypatch, "confirm-invalidate-draft.sqlite3")
    draft_id = created["profile_draft"]["profile_draft_id"]
    client.post(f"/api/v1/profile-drafts/{draft_id}/confirm")

    response = client.patch(
        f"/api/v1/profile-drafts/{draft_id}",
        json={"summary": "Updated summary after confirmation."},
    )

    assert response.status_code == 200
    assert response.json()["profile_session"]["confirmed_profile_id"] is None
    assert response.json()["profile_session"]["current_step"] == "profile_draft"


def test_resume_resubmission_invalidates_confirmed_profile(monkeypatch, tmp_path) -> None:
    created = _create_session_with_draft(tmp_path, monkeypatch, "confirm-invalidate-resume.sqlite3")
    draft_id = created["profile_draft"]["profile_draft_id"]
    client.post(f"/api/v1/profile-drafts/{draft_id}/confirm")

    response = client.post(
        f"/api/v1/profile-sessions/{created['profile_session']['session_id']}/resume-text",
        json={"text": "Skills: Python, FastAPI\nProject: Updated resume content."},
    )

    assert response.status_code == 200
    assert response.json()["profile_session"]["confirmed_profile_id"] is None
    assert response.json()["profile_session"]["current_step"] == "resume_ready"


def test_confirm_does_not_create_job_search_run(monkeypatch, tmp_path) -> None:
    created = _create_session_with_draft(tmp_path, monkeypatch, "confirm-no-job-search.sqlite3")
    response = client.post(
        f"/api/v1/profile-drafts/{created['profile_draft']['profile_draft_id']}/confirm"
    )

    payload = response.json()
    assert response.status_code == 200
    assert payload["profile_session"]["current_step"] == "job_search_ready"
    assert "job_search_run_id" not in payload["confirmed_profile"]
