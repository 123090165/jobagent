from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.application.job_search_usecases import browser_job_capture_to_candidate
from app.main import app
from app.schemas.job_search import BrowserJobCaptureRequest

client = TestClient(app)


def _create_session_with_confirmed_profile(
    tmp_path,
    monkeypatch,
    name: str = "browser-job-capture.sqlite3",
) -> dict:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / name))
    session = client.post("/api/v1/profile-sessions").json()
    client.post(
        f"/api/v1/profile-sessions/{session['session_id']}/resume-text",
        json={
            "text": (
                "Name: Jane Doe\n"
                "Role: Backend Engineer\n"
                "Skills: Python, FastAPI, SQL, APIs, Docker\n"
                "Project: Built API services and tested backend workflows.\n"
            )
        },
    )
    client.post(f"/api/v1/profile-sessions/{session['session_id']}/parse-resume")
    draft = client.post(
        f"/api/v1/profile-sessions/{session['session_id']}/profile-draft"
    ).json()
    return client.post(
        f"/api/v1/profile-drafts/{draft['profile_draft']['profile_draft_id']}/confirm"
    ).json()


def _capture_payload(session_id: str) -> dict:
    jd_text = (
        "Backend Engineer Intern. Responsibilities include building Python FastAPI "
        "services, SQL-backed APIs, integration tests, and deployment workflows. "
        "Requirements include Python, REST API design, SQL, Docker, and clear communication."
    )
    return {
        "session_id": session_id,
        "source": "company_site",
        "source_url": "https://jobs.example.com/backend-intern",
        "page_title": "Backend Engineer Intern - Example Jobs",
        "title": "Backend Engineer Intern",
        "company": "Example Jobs",
        "location": "Remote",
        "salary": None,
        "jd_text": jd_text,
        "visible_text": f"\n\n{jd_text}\n\n",
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "extractor_version": "browser-capture-test",
        "warnings": ["generic extractor used"],
        "use_llm": False,
    }


def test_browser_job_capture_request_validates_jd_text() -> None:
    payload = _capture_payload("session-1")
    payload["jd_text"] = "too short"

    with pytest.raises(ValidationError):
        BrowserJobCaptureRequest.model_validate(payload)


def test_browser_job_capture_request_rejects_non_http_url() -> None:
    payload = _capture_payload("session-1")
    payload["source_url"] = "chrome://extensions"

    with pytest.raises(ValidationError):
        BrowserJobCaptureRequest.model_validate(payload)


def test_browser_job_capture_to_candidate_preserves_debug_metadata() -> None:
    payload = BrowserJobCaptureRequest.model_validate(_capture_payload("session-1"))

    candidate = browser_job_capture_to_candidate(payload)

    assert candidate.title == "Backend Engineer Intern"
    assert candidate.company == "Example Jobs"
    assert candidate.source_url == "https://jobs.example.com/backend-intern"
    assert candidate.source_provider == "browser_capture_company_site"
    assert candidate.raw_description == payload.jd_text
    assert "generic extractor used" in candidate.provider_warnings
    assert any("extractor version" in warning for warning in candidate.provider_warnings)


def test_browser_job_capture_analyze_endpoint_reuses_job_search_pipeline(monkeypatch, tmp_path) -> None:
    confirmed = _create_session_with_confirmed_profile(tmp_path, monkeypatch)
    session_id = confirmed["profile_session"]["session_id"]

    response = client.post(
        "/api/v1/browser/job-captures/analyze",
        json=_capture_payload(session_id),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["capture"]["source"] == "company_site"
    assert payload["capture"]["source_url"] == "https://jobs.example.com/backend-intern"
    assert payload["report"]["overall_score"] > 0
    assert payload["report"]["recommendation"]
    assert payload["report"]["matched_strengths"]
    assert payload["job_search_run_id"]
    assert payload["job_result_id"]
    assert any("generic extractor used" in warning for warning in payload["warnings"])


def test_browser_job_capture_requires_confirmed_profile(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / "browser-capture-no-confirmed.sqlite3"))
    session = client.post("/api/v1/profile-sessions").json()

    response = client.post(
        "/api/v1/browser/job-captures/analyze",
        json=_capture_payload(session["session_id"]),
    )

    assert response.status_code == 409
    assert response.json()["error_code"] == "confirmed_profile_required"
