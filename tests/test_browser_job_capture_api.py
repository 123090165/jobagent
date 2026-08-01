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


def _capture_only_payload() -> dict:
    payload = _capture_payload("unused")
    payload.pop("session_id")
    payload.pop("use_llm")
    return payload


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

    captured = client.post("/api/v1/browser/job-captures", json=_capture_only_payload()).json()
    response = client.post(
        f"/api/v1/browser/job-captures/{captured['capture_id']}/analyze",
        json={"session_id": session_id, "analysis_mode": "deterministic", "use_llm": False},
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
    assert payload["saved_job_id"] == captured["saved_job_id"]
    assert payload["saved_job_analysis_id"]
    assert any("generic extractor used" in warning for warning in payload["warnings"])

    conversation = client.post(
        "/api/v1/chat/conversations", json={"title": "Captured role"}
    ).json()
    ref = {
        "job_search_run_id": payload["job_search_run_id"],
        "job_result_id": payload["job_result_id"],
    }
    pin_url = (
        f"/api/v1/chat/conversations/{conversation['conversation_id']}"
        "/context/search-results"
    )
    first_pin = client.post(pin_url, json=ref)
    second_pin = client.post(pin_url, json=ref)
    assert first_pin.status_code == 200
    assert second_pin.status_code == 200
    assert second_pin.json()["data_scope"]["job_search_result_refs"] == [ref]

    turn = client.post(
        f"/api/v1/chat/conversations/{conversation['conversation_id']}/turns",
        json={
            "client_turn_id": "captured-job-question",
            "question": "What are the main risks in this attached job?",
            "llm_provider": "mock",
            "context_attachments": [{"type": "search_result", **ref}],
        },
    )
    assert turn.status_code == 200
    assert turn.json()["retrieval_plan"]["requests"][0]["strategy"] == "use_attachment"
    assert turn.json()["retrieved_refs"] == [
        f"search_result:{ref['job_search_run_id']}:{ref['job_result_id']}"
    ]


def test_browser_job_capture_can_be_saved_and_used_in_chat_without_analysis(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / "capture-only-chat.sqlite3"))
    captured = client.post(
        "/api/v1/browser/job-captures",
        json=_capture_only_payload(),
    )
    assert captured.status_code == 201
    saved_job_id = captured.json()["saved_job_id"]
    assert captured.json()["capture"]["title"] == "Backend Engineer Intern"
    assert "jd_text" not in captured.json()["capture"]

    conversation = client.post("/api/v1/chat/conversations", json={}).json()
    turn = client.post(
        f"/api/v1/chat/conversations/{conversation['conversation_id']}/turns",
        json={
            "client_turn_id": "capture-only-question",
            "question": "What are the main risks in this attached job?",
            "llm_provider": "mock",
            "context_attachments": [{
                "type": "saved_job",
                "saved_job_id": saved_job_id,
            }],
        },
    )
    assert turn.status_code == 200
    assert turn.json()["retrieval_plan"]["requests"][0] == {
        "source": "saved_jobs",
        "strategy": "use_attachment",
        "policy_reason": "explicit_attachment",
    }
    assert turn.json()["retrieved_refs"] == [
        f"saved_job:{captured.json()['saved_job_id']}"
    ]


def test_saved_browser_capture_can_be_analyzed_later(monkeypatch, tmp_path) -> None:
    confirmed = _create_session_with_confirmed_profile(
        tmp_path,
        monkeypatch,
        name="saved-capture-analysis.sqlite3",
    )
    capture_id = client.post(
        "/api/v1/browser/job-captures",
        json=_capture_only_payload(),
    ).json()["capture_id"]
    response = client.post(
        f"/api/v1/browser/job-captures/{capture_id}/analyze",
        json={
            "session_id": confirmed["profile_session"]["session_id"],
            "analysis_mode": "deterministic",
            "use_llm": False,
        },
    )
    assert response.status_code == 200
    assert response.json()["report"]["overall_score"] > 0
    saved_job_id = response.json()["saved_job_id"]
    job = client.get(f"/api/v1/saved-jobs/{saved_job_id}").json()
    assert job["latest_analysis"]["saved_job_analysis_id"] == response.json()[
        "saved_job_analysis_id"
    ]


def test_repeated_browser_capture_updates_one_job_workspace(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / "capture-job-identity.sqlite3"))
    first = client.post("/api/v1/browser/job-captures", json=_capture_only_payload())
    richer_payload = _capture_only_payload()
    richer_payload["jd_text"] += " Additional ownership of observability and production support."
    second = client.post("/api/v1/browser/job-captures", json=richer_payload)

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["capture_id"] != second.json()["capture_id"]
    assert first.json()["saved_job_id"] == second.json()["saved_job_id"]
    jobs = client.get("/api/v1/saved-jobs").json()["items"]
    assert len(jobs) == 1
    assert "Additional ownership" in jobs[0]["raw_jd_text"]


def test_browser_job_capture_requires_confirmed_profile(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / "browser-capture-no-confirmed.sqlite3"))
    session = client.post("/api/v1/profile-sessions").json()

    capture_id = client.post(
        "/api/v1/browser/job-captures", json=_capture_only_payload()
    ).json()["capture_id"]
    response = client.post(
        f"/api/v1/browser/job-captures/{capture_id}/analyze",
        json={"session_id": session["session_id"], "use_llm": False},
    )

    assert response.status_code == 409
    assert response.json()["error_code"] == "confirmed_profile_required"
