from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _create_session_with_review(tmp_path, monkeypatch, name: str = "profile-draft.sqlite3") -> dict:
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
    return client.get(f"/api/v1/profile-sessions/{session['session_id']}").json()


def test_create_profile_draft_requires_parsed_review(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / "draft-missing-review.sqlite3"))
    session = client.post("/api/v1/profile-sessions").json()

    response = client.post(f"/api/v1/profile-sessions/{session['session_id']}/profile-draft")

    assert response.status_code == 409
    assert response.json()["error_code"] == "invalid_profile_session_state"


def test_create_profile_draft_updates_session(monkeypatch, tmp_path) -> None:
    session = _create_session_with_review(tmp_path, monkeypatch, "draft-create.sqlite3")

    response = client.post(f"/api/v1/profile-sessions/{session['session_id']}/profile-draft")

    assert response.status_code == 200
    payload = response.json()
    assert payload["profile_draft"]["profile_draft_id"]
    assert payload["profile_draft"]["parsed_review_id"] == session["parsed_review_id"]
    assert payload["profile_draft"]["summary"]
    assert isinstance(payload["profile_draft"]["core_skills"], list)
    assert payload["profile_session"]["current_step"] == "profile_draft"
    assert payload["profile_session"]["profile_draft_id"] == payload["profile_draft"]["profile_draft_id"]


def test_create_profile_draft_is_idempotent_by_default(monkeypatch, tmp_path) -> None:
    session = _create_session_with_review(tmp_path, monkeypatch, "draft-idempotent.sqlite3")

    first = client.post(f"/api/v1/profile-sessions/{session['session_id']}/profile-draft").json()
    second = client.post(f"/api/v1/profile-sessions/{session['session_id']}/profile-draft").json()

    assert first["profile_draft"]["profile_draft_id"] == second["profile_draft"]["profile_draft_id"]


def test_create_profile_draft_regenerate_creates_new_draft(monkeypatch, tmp_path) -> None:
    session = _create_session_with_review(tmp_path, monkeypatch, "draft-regenerate.sqlite3")

    first = client.post(f"/api/v1/profile-sessions/{session['session_id']}/profile-draft").json()
    second = client.post(
        f"/api/v1/profile-sessions/{session['session_id']}/profile-draft?regenerate=true"
    ).json()

    assert first["profile_draft"]["profile_draft_id"] != second["profile_draft"]["profile_draft_id"]


def test_get_profile_draft_returns_existing_draft(monkeypatch, tmp_path) -> None:
    session = _create_session_with_review(tmp_path, monkeypatch, "draft-get.sqlite3")
    created = client.post(f"/api/v1/profile-sessions/{session['session_id']}/profile-draft").json()

    response = client.get(f"/api/v1/profile-drafts/{created['profile_draft']['profile_draft_id']}")

    assert response.status_code == 200
    assert response.json()["profile_draft"]["profile_draft_id"] == created["profile_draft"]["profile_draft_id"]


def test_patch_profile_draft_updates_fields(monkeypatch, tmp_path) -> None:
    session = _create_session_with_review(tmp_path, monkeypatch, "draft-update.sqlite3")
    created = client.post(f"/api/v1/profile-sessions/{session['session_id']}/profile-draft").json()
    draft_id = created["profile_draft"]["profile_draft_id"]

    response = client.patch(
        f"/api/v1/profile-drafts/{draft_id}",
        json={
            "summary": "Targeting backend and applied AI platform roles.",
            "preferred_locations": ["Tokyo", "Remote"],
            "work_arrangements": ["Hybrid", "Remote"],
            "missing_info_questions": ["What scale of systems has the candidate owned?"],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["profile_draft"]["summary"] == "Targeting backend and applied AI platform roles."
    assert payload["profile_draft"]["preferred_locations"] == ["Tokyo", "Remote"]
    assert payload["profile_draft"]["work_arrangements"] == ["Hybrid", "Remote"]
    assert payload["profile_session"]["current_step"] == "profile_draft"


def test_submitting_new_resume_invalidates_previous_profile_draft(monkeypatch, tmp_path) -> None:
    session = _create_session_with_review(tmp_path, monkeypatch, "draft-invalidate.sqlite3")
    first_draft = client.post(
        f"/api/v1/profile-sessions/{session['session_id']}/profile-draft"
    ).json()

    updated_resume = client.post(
        f"/api/v1/profile-sessions/{session['session_id']}/resume-text",
        json={"text": "Skills: Python, FastAPI\nProject: Updated resume content."},
    ).json()

    assert first_draft["profile_draft"]["profile_draft_id"]
    assert updated_resume["profile_session"]["profile_draft_id"] is None
    assert updated_resume["profile_session"]["current_step"] == "resume_ready"
