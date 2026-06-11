from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_resume_profile_enrichment_endpoint_use_llm_false_returns_200() -> None:
    response = client.post(
        "/resume/profile-enrichment",
        json={
            "resume_text": "Skills: Python, FastAPI\nProjects: JobAgent built FastAPI APIs.",
            "use_llm": False,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["baseline_review"]
    assert isinstance(payload["enrichment_suggestions"], list)
    assert payload["llm_success_count"] == 0


def test_resume_profile_enrichment_response_contains_baseline_review() -> None:
    response = client.post(
        "/resume/profile-enrichment",
        json={"resume_text": "Skills: Python, FastAPI"},
    )

    assert response.status_code == 200
    assert response.json()["baseline_review"]["parsed_profile"]


def test_resume_profile_enrichment_response_contains_suggestions_list() -> None:
    response = client.post(
        "/resume/profile-enrichment",
        json={"resume_text": "Projects: JobAgent built FastAPI APIs."},
    )

    assert response.status_code == 200
    assert isinstance(response.json()["enrichment_suggestions"], list)


def test_resume_profile_enrichment_rejects_empty_resume_text() -> None:
    response = client.post(
        "/resume/profile-enrichment",
        json={"resume_text": "   "},
    )

    assert response.status_code == 400
    assert response.json()["error_code"] == "resume_text_required"
