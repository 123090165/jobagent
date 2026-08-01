from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.main import app
from app.services.llm_provider import LLMProviderResolution

client = TestClient(app)


class _GreetingLLM:
    def chat_completion_json(self, *, system_prompt: str, **_: object) -> dict:
        if "复核" in system_prompt:
            return {
                "approved": True,
                "naturalness": 9,
                "relevance": 9,
                "differentiation": 8,
                "issues": [],
            }
        return {
            "content": "您好，我有 Python、FastAPI 和 SQL 项目经验，与这个后端岗位较匹配，希望进一步沟通岗位情况。",
            "evidence_used": ["Python", "FastAPI", "SQL"],
            "avoid_claims": [],
        }


class _FailingGreetingLLM:
    def chat_completion_json(self, **_: object) -> dict:
        raise RuntimeError("network unavailable")


class _CorrectingGreetingLLM(_GreetingLLM):
    def __init__(self) -> None:
        self.review_calls = 0
        self.generation_calls = 0

    def chat_completion_json(self, *, system_prompt: str, **kwargs: object) -> dict:
        if "复核" in system_prompt:
            self.review_calls += 1
            if self.review_calls == 1:
                return {
                    "approved": False,
                    "naturalness": 5,
                    "relevance": 8,
                    "differentiation": 5,
                    "issues": ["表达略显模板化"],
                }
        else:
            self.generation_calls += 1
        return super().chat_completion_json(system_prompt=system_prompt, **kwargs)


def _configure_llm(monkeypatch, service: object | None = None) -> None:
    monkeypatch.setattr(
        "app.application.communication_usecases.resolve_llm_provider",
        lambda _provider=None: LLMProviderResolution(
            provider="deepseek",
            service=service or _GreetingLLM(),
            configured=True,
        ),
    )


def _register(username: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/register",
        json={"username": username, "password": "password-123"},
    )
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _create_profile(headers: dict[str, str]) -> str:
    session = client.post("/api/v1/profile-sessions", headers=headers).json()
    client.post(
        f"/api/v1/profile-sessions/{session['session_id']}/resume-text",
        headers=headers,
        json={
            "text": (
                "Name: Jane Doe\nRole: Backend Engineer\n"
                "Skills: Python, FastAPI, SQL, Docker\n"
                "Project: Built JobAgent APIs and retrieval workflows.\n"
            )
        },
    )
    client.post(
        f"/api/v1/profile-sessions/{session['session_id']}/parse-resume",
        headers=headers,
    )
    draft = client.post(
        f"/api/v1/profile-sessions/{session['session_id']}/profile-draft",
        headers=headers,
    ).json()
    client.post(
        f"/api/v1/profile-drafts/{draft['profile_draft']['profile_draft_id']}/confirm",
        headers=headers,
    )
    return client.get("/api/v1/resume-profiles", headers=headers).json()["items"][0][
        "resume_profile_id"
    ]


def _capture_job(headers: dict[str, str]) -> str:
    jd = (
        "Backend Engineer Intern responsible for Python FastAPI services, SQL APIs, "
        "Docker deployment workflows, automated tests, and collaboration with product teams."
    )
    response = client.post(
        "/api/v1/browser/job-captures",
        headers=headers,
        json={
            "source": "boss",
            "source_url": "https://www.zhipin.com/job_detail/backend-intern.html",
            "page_title": "Backend Engineer Intern",
            "title": "Backend Engineer Intern",
            "company": "JobAgent",
            "location": "Shenzhen",
            "jd_text": jd,
            "visible_text": jd,
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "extractor_version": "test-v1",
        },
    )
    assert response.status_code == 201
    return response.json()["capture_id"]


def test_approved_greeting_confirmation_creates_application_atomically(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / "communication.sqlite3"))
    _configure_llm(monkeypatch)
    headers = _register("communication-owner")
    profile_id = _create_profile(headers)
    capture_id = _capture_job(headers)

    generated = client.post(
        f"/api/v1/browser/job-captures/{capture_id}/greeting-drafts",
        headers=headers,
        json={"resume_profile_id": profile_id},
    )
    assert generated.status_code == 201
    draft = generated.json()
    assert draft["status"] == "generated"
    assert "Python" in draft["generated_content"]

    premature = client.post(
        f"/api/v1/communication-drafts/{draft['draft_id']}/confirm-sent",
        headers=headers,
        json={
            "platform_result": "success",
            "sent_content": draft["generated_content"],
            "sent_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    assert premature.status_code == 409
    jobs_before_send = client.get("/api/v1/saved-jobs", headers=headers).json()["items"]
    assert len(jobs_before_send) == 1
    assert jobs_before_send[0]["saved_job_id"] == draft["saved_job_id"]

    approved = client.patch(
        f"/api/v1/communication-drafts/{draft['draft_id']}",
        headers=headers,
        json={"approved_content": draft["generated_content"], "status": "approved"},
    )
    confirmed = client.post(
        f"/api/v1/communication-drafts/{draft['draft_id']}/confirm-sent",
        headers=headers,
        json={
            "platform_result": "success",
            "sent_content": approved.json()["approved_content"],
            "sent_at": datetime.now(timezone.utc).isoformat(),
        },
    )

    assert confirmed.status_code == 200
    assert confirmed.json()["draft"]["status"] == "sent"
    workspace = client.get(
        f"/api/v1/saved-jobs/{confirmed.json()['saved_job_id']}/workspace",
        headers=headers,
    ).json()
    assert workspace["application"]["stage"] == "contacted"
    assert workspace["application"]["next_action"] == "wait_for_reply"
    assert workspace["communication_draft"]["status"] == "sent"
    assert {event["event_type"] for event in workspace["events"]} >= {
        "greeting_sent",
        "stage_changed",
    }

    repeated = client.post(
        f"/api/v1/communication-drafts/{draft['draft_id']}/confirm-sent",
        headers=headers,
        json={
            "platform_result": "success",
            "sent_content": approved.json()["approved_content"],
            "sent_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    assert repeated.status_code == 200
    assert repeated.json()["application_id"] == confirmed.json()["application_id"]


def test_communication_draft_is_user_scoped(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / "communication-scope.sqlite3"))
    _configure_llm(monkeypatch)
    owner = _register("communication-scope-owner")
    other = _register("communication-scope-other")
    profile_id = _create_profile(owner)
    capture_id = _capture_job(owner)
    draft = client.post(
        f"/api/v1/browser/job-captures/{capture_id}/greeting-drafts",
        headers=owner,
        json={"resume_profile_id": profile_id},
    ).json()

    forbidden = client.patch(
        f"/api/v1/communication-drafts/{draft['draft_id']}",
        headers=other,
        json={"status": "dismissed"},
    )

    assert forbidden.status_code == 404


def test_failed_greeting_generation_does_not_create_draft(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / "failed-communication.sqlite3"))
    _configure_llm(monkeypatch, _FailingGreetingLLM())
    headers = _register("failed-communication-owner")
    profile_id = _create_profile(headers)
    capture_id = _capture_job(headers)

    response = client.post(
        f"/api/v1/browser/job-captures/{capture_id}/greeting-drafts",
        headers=headers,
        json={"resume_profile_id": profile_id},
    )

    assert response.status_code == 502
    assert response.json()["error_code"] == "generation_failed"


def test_greeting_quality_failure_is_corrected_once(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / "corrected-communication.sqlite3"))
    service = _CorrectingGreetingLLM()
    _configure_llm(monkeypatch, service)
    headers = _register("corrected-communication-owner")
    profile_id = _create_profile(headers)
    capture_id = _capture_job(headers)

    response = client.post(
        f"/api/v1/browser/job-captures/{capture_id}/greeting-drafts",
        headers=headers,
        json={"resume_profile_id": profile_id},
    )

    assert response.status_code == 201
    assert service.generation_calls == 2
    assert service.review_calls == 2
