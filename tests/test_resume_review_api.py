from __future__ import annotations

from fastapi.testclient import TestClient
from types import SimpleNamespace

from app.main import app

client = TestClient(app)


def _create_session_with_resume(tmp_path, monkeypatch, name: str = "resume-review.sqlite3") -> dict:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / name))
    session = client.post("/api/v1/profile-sessions").json()
    client.post(
        f"/api/v1/profile-sessions/{session['session_id']}/resume-text",
        json={
            "text": (
                "Name: Jane Doe\n"
                "Skills: Python, FastAPI, SQL, LangGraph\n"
                "Project: Built JobAgent resume review flow with pytest coverage.\n"
            )
        },
    )
    return client.get(f"/api/v1/profile-sessions/{session['session_id']}").json()


def test_parse_resume_requires_existing_session(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / "missing-session.sqlite3"))

    response = client.post("/api/v1/profile-sessions/missing-session/parse-resume")

    assert response.status_code == 404
    assert response.json()["error_code"] == "profile_session_not_found"


def test_parse_resume_requires_resume_document(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / "missing-resume.sqlite3"))
    session = client.post("/api/v1/profile-sessions").json()

    response = client.post(f"/api/v1/profile-sessions/{session['session_id']}/parse-resume")

    assert response.status_code == 409
    assert response.json()["error_code"] == "invalid_profile_session_state"


def test_parse_resume_creates_review_and_updates_session(monkeypatch, tmp_path) -> None:
    session = _create_session_with_resume(tmp_path, monkeypatch, "create-review.sqlite3")

    response = client.post(f"/api/v1/profile-sessions/{session['session_id']}/parse-resume")

    assert response.status_code == 200
    payload = response.json()
    assert payload["parsed_review"]["parsed_review_id"]
    assert payload["parsed_review"]["resume_document_id"] == session["resume_document_id"]
    assert isinstance(payload["parsed_review"]["quality_warnings"], list)
    assert isinstance(payload["parsed_review"]["missing_info_questions"], list)
    assert payload["profile_session"]["current_step"] == "resume_review"
    assert payload["profile_session"]["parsed_review_id"] == payload["parsed_review"]["parsed_review_id"]


def test_parse_resume_is_idempotent_by_default(monkeypatch, tmp_path) -> None:
    session = _create_session_with_resume(tmp_path, monkeypatch, "idempotent.sqlite3")

    class FakeResumeReviewLLM:
        def chat_completion_json(self, *, system_prompt: str, user_prompt: str) -> dict:
            return {
                "resume_profile": {
                    "raw_text": "Name: Jane Doe\nSkills: Python",
                    "name": "Jane Doe",
                    "target_roles": [],
                    "education": [],
                    "skills": ["Python"],
                    "projects": [],
                    "work_experiences": [],
                    "certificates": [],
                    "highlights": [],
                    "missing_info": [],
                },
                "quality_warnings": [],
            }

    monkeypatch.setattr(
        "app.application.resume_review_usecases.resolve_llm_provider_for_switch",
        lambda *, use_deepseek: SimpleNamespace(
            provider="deepseek" if use_deepseek else "ollama",
            service=FakeResumeReviewLLM(),
        ),
    )

    first = client.post(f"/api/v1/profile-sessions/{session['session_id']}/parse-resume").json()
    second = client.post(f"/api/v1/profile-sessions/{session['session_id']}/parse-resume").json()

    assert first["parsed_review"]["parsed_review_id"] == second["parsed_review"]["parsed_review_id"]


def test_parse_resume_regenerate_creates_new_review(monkeypatch, tmp_path) -> None:
    session = _create_session_with_resume(tmp_path, monkeypatch, "regenerate.sqlite3")

    first = client.post(f"/api/v1/profile-sessions/{session['session_id']}/parse-resume").json()
    second = client.post(
        f"/api/v1/profile-sessions/{session['session_id']}/parse-resume?regenerate=true"
    ).json()

    assert first["parsed_review"]["parsed_review_id"] != second["parsed_review"]["parsed_review_id"]
    assert second["profile_session"]["parsed_review_id"] == second["parsed_review"]["parsed_review_id"]


def test_parse_resume_accepts_use_llm_true(monkeypatch, tmp_path) -> None:
    session = _create_session_with_resume(tmp_path, monkeypatch, "use-llm-review.sqlite3")

    class FakeResumeReviewLLM:
        def chat_completion_json(self, *, system_prompt: str, user_prompt: str) -> dict:
            return {
                "resume_profile": {
                    "raw_text": "Name: Jane Doe\nSkills: Python",
                    "name": "Jane Doe",
                    "target_roles": ["AI Health Signal Processing Engineer"],
                    "education": [],
                    "skills": ["Python", "PPG", "ECG"],
                    "projects": [
                        {
                            "name": "AI Health Signals",
                            "description": "Analyzed physiological signals.",
                            "technologies": ["Python"],
                            "highlights": [],
                            "raw_text": "AI Health Signals",
                        }
                    ],
                    "work_experiences": [],
                    "certificates": [],
                    "highlights": [],
                    "missing_info": [],
                },
                "quality_warnings": [],
            }

    monkeypatch.setattr(
        "app.application.resume_review_usecases.resolve_llm_provider_for_switch",
        lambda *, use_deepseek: SimpleNamespace(
            provider="deepseek" if use_deepseek else "ollama",
            service=FakeResumeReviewLLM(),
        ),
    )

    response = client.post(
        f"/api/v1/profile-sessions/{session['session_id']}/parse-resume?regenerate=true&use_llm=true"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["parsed_review"]["analysis_mode"] == "llm_guided"
    assert payload["parsed_review"]["analysis_provider"] == "deepseek"
    assert payload["parsed_review"]["raw_parser_output"]["name"] == "Jane Doe"


def test_get_parsed_review_returns_current_review(monkeypatch, tmp_path) -> None:
    session = _create_session_with_resume(tmp_path, monkeypatch, "get-review.sqlite3")
    created = client.post(f"/api/v1/profile-sessions/{session['session_id']}/parse-resume").json()

    response = client.get(f"/api/v1/profile-sessions/{session['session_id']}/parsed-review")

    assert response.status_code == 200
    assert response.json()["parsed_review"]["parsed_review_id"] == created["parsed_review"]["parsed_review_id"]


def test_get_parsed_review_before_parse_returns_not_found(monkeypatch, tmp_path) -> None:
    session = _create_session_with_resume(tmp_path, monkeypatch, "parsed-review-missing.sqlite3")

    response = client.get(f"/api/v1/profile-sessions/{session['session_id']}/parsed-review")

    assert response.status_code == 404
    assert response.json()["error_code"] == "parsed_review_not_found"


def test_submitting_new_resume_invalidates_previous_parsed_review(monkeypatch, tmp_path) -> None:
    session = _create_session_with_resume(tmp_path, monkeypatch, "invalidate-review.sqlite3")
    first_review = client.post(
        f"/api/v1/profile-sessions/{session['session_id']}/parse-resume"
    ).json()

    updated_resume = client.post(
        f"/api/v1/profile-sessions/{session['session_id']}/resume-text",
        json={"text": "Skills: Python\nProject: Built a new review iteration."},
    ).json()

    assert updated_resume["profile_session"]["parsed_review_id"] is None
    assert updated_resume["profile_session"]["current_step"] == "resume_ready"

    second_review = client.post(
        f"/api/v1/profile-sessions/{session['session_id']}/parse-resume"
    ).json()
    assert first_review["parsed_review"]["parsed_review_id"] != second_review["parsed_review"]["parsed_review_id"]
