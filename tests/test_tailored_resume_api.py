from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.main import app
from app.services.llm_provider import LLMProviderResolution
from app.services.tailored_resume_generator import RESUME_COMPLETION_MARKER


client = TestClient(app)


class _ResumeLLM:
    def chat_completion_json(self, **_: object) -> dict[str, str]:
        return {
            "content": (
                "# Jane Doe\n\n## Professional Summary\nBackend Engineer focused on Python APIs.\n\n"
                "## Skills\nPython, FastAPI, SQL\n\n## Projects\n"
                "Built JobAgent APIs and retrieval workflows.\n\n"
                f"{RESUME_COMPLETION_MARKER}"
            )
        }


class _FailingLLM:
    def chat_completion_json(self, **_: object) -> dict:
        raise RuntimeError("network unavailable")


class _CorrectingResumeLLM(_ResumeLLM):
    def __init__(self) -> None:
        self.calls = 0

    def chat_completion_json(self, **kwargs: object) -> dict[str, str]:
        self.calls += 1
        result = super().chat_completion_json(**kwargs)
        if self.calls == 1:
            result["content"] = result["content"].replace(RESUME_COMPLETION_MARKER, "")
        return result


class _UnsafeResumeLLM(_ResumeLLM):
    def chat_completion_json(self, **kwargs: object) -> dict[str, str]:
        result = super().chat_completion_json(**kwargs)
        result["content"] = result["content"].replace(
            RESUME_COMPLETION_MARKER,
            f"Improved revenue by 99%.\n\n{RESUME_COMPLETION_MARKER}",
        )
        return result


def _configure_llm(monkeypatch, service: object | None = None) -> None:
    monkeypatch.setattr(
        "app.application.tailored_resume_usecases.resolve_llm_provider",
        lambda _provider=None: LLMProviderResolution(
            provider="deepseek",
            service=service or _ResumeLLM(),
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
                "Skills: Python, FastAPI, SQL\n"
                "Project: Built JobAgent APIs and retrieval workflows.\n"
            )
        },
    )
    client.post(f"/api/v1/profile-sessions/{session['session_id']}/parse-resume", headers=headers)
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


def _save_job(headers: dict[str, str]) -> str:
    response = client.post(
        "/api/v1/saved-jobs",
        headers=headers,
        json={
            "title": "Backend Engineer",
            "company": "JobAgent",
            "raw_jd_text": "Build Python and FastAPI services with SQL.",
        },
    )
    assert response.status_code == 200
    return response.json()["saved_job_id"]


def test_tailored_resume_generation_edit_validation_and_approval(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / "tailored-resume.sqlite3"))
    _configure_llm(monkeypatch)
    headers = _register("tailored-resume-owner")
    profile_id = _create_profile(headers)
    job_id = _save_job(headers)

    generated = client.post(
        f"/api/v1/saved-jobs/{job_id}/tailored-resumes",
        headers=headers,
        json={"resume_profile_id": profile_id},
    )
    assert generated.status_code == 201
    version = generated.json()
    assert version["version"] == 1
    assert version["validation"]["is_valid"] is True
    assert "Python" in version["content"]

    workspace = client.get(f"/api/v1/saved-jobs/{job_id}/workspace", headers=headers).json()
    assert workspace["application"] is None
    assert workspace["tailored_resume"]["tailored_resume_id"] == version["tailored_resume_id"]
    assert workspace["events"] == []

    invalid = client.patch(
        f"/api/v1/tailored-resumes/{version['tailored_resume_id']}",
        headers=headers,
        json={"content": version["content"] + "\nImproved revenue by 99%."},
    )
    assert invalid.status_code == 200
    assert invalid.json()["status"] == "needs_review"
    rejected = client.post(
        f"/api/v1/tailored-resumes/{version['tailored_resume_id']}/approve",
        headers=headers,
    )
    assert rejected.status_code == 409

    repaired = client.patch(
        f"/api/v1/tailored-resumes/{version['tailored_resume_id']}",
        headers=headers,
        json={"content": version["content"]},
    )
    assert repaired.json()["validation"]["is_valid"] is True
    approved = client.post(
        f"/api/v1/tailored-resumes/{version['tailored_resume_id']}/approve",
        headers=headers,
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    pdf = client.get(
        f"/api/v1/tailored-resumes/{version['tailored_resume_id']}/pdf",
        headers=headers,
    )
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.content.startswith(b"%PDF")
    repeated = client.post(
        f"/api/v1/tailored-resumes/{version['tailored_resume_id']}/approve",
        headers=headers,
    )
    assert repeated.status_code == 200
    workspace = client.get(f"/api/v1/saved-jobs/{job_id}/workspace", headers=headers).json()
    assert workspace["application"] is None
    assert workspace["events"] == []


def test_tailored_resume_is_user_scoped(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / "tailored-resume-scope.sqlite3"))
    _configure_llm(monkeypatch)
    owner = _register("tailored-resume-scope-owner")
    other = _register("tailored-resume-scope-other")
    profile_id = _create_profile(owner)
    job_id = _save_job(owner)
    version = client.post(
        f"/api/v1/saved-jobs/{job_id}/tailored-resumes",
        headers=owner,
        json={"resume_profile_id": profile_id},
    ).json()

    response = client.patch(
        f"/api/v1/tailored-resumes/{version['tailored_resume_id']}",
        headers=other,
        json={"content": "not allowed"},
    )
    assert response.status_code == 404


def test_browser_capture_can_create_resume_workbench(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / "capture-tailored-resume.sqlite3"))
    _configure_llm(monkeypatch)
    headers = _register("capture-tailored-resume-owner")
    profile_id = _create_profile(headers)
    jd_text = (
        "Build Python and FastAPI services with SQL, automated tests, API documentation, "
        "and collaboration across product and engineering teams."
    )
    capture_response = client.post(
        "/api/v1/browser/job-captures",
        headers=headers,
        json={
            "source": "boss",
            "source_url": "https://www.zhipin.com/job_detail/python-role.html",
            "page_title": "Python Engineer",
            "title": "Python Engineer",
            "company": "JobAgent",
            "jd_text": jd_text,
            "visible_text": jd_text,
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "extractor_version": "test-v1",
        },
    )
    assert capture_response.status_code == 201
    capture = capture_response.json()

    generated = client.post(
        f"/api/v1/browser/job-captures/{capture['capture_id']}/tailored-resumes",
        headers=headers,
        json={"resume_profile_id": profile_id},
    )

    assert generated.status_code == 201
    version = generated.json()
    workspace = client.get(
        f"/api/v1/saved-jobs/{version['saved_job_id']}/workspace",
        headers=headers,
    ).json()
    assert workspace["job"]["source_provider"] == "boss"
    assert workspace["tailored_resume"]["status"] == "needs_review"


def test_failed_generation_does_not_create_resume_or_application(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / "failed-tailored-resume.sqlite3"))
    _configure_llm(monkeypatch, _FailingLLM())
    headers = _register("failed-tailored-resume-owner")
    profile_id = _create_profile(headers)
    job_id = _save_job(headers)

    response = client.post(
        f"/api/v1/saved-jobs/{job_id}/tailored-resumes",
        headers=headers,
        json={"resume_profile_id": profile_id},
    )

    assert response.status_code == 502
    assert response.json()["error_code"] == "generation_failed"
    workspace = client.get(f"/api/v1/saved-jobs/{job_id}/workspace", headers=headers).json()
    assert workspace["application"] is None
    assert workspace["tailored_resume"] is None


def test_incomplete_resume_is_corrected_once(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / "corrected-tailored-resume.sqlite3"))
    service = _CorrectingResumeLLM()
    _configure_llm(monkeypatch, service)
    headers = _register("corrected-tailored-resume-owner")
    profile_id = _create_profile(headers)
    job_id = _save_job(headers)

    response = client.post(
        f"/api/v1/saved-jobs/{job_id}/tailored-resumes",
        headers=headers,
        json={"resume_profile_id": profile_id},
    )

    assert response.status_code == 201
    assert service.calls == 2
    assert RESUME_COMPLETION_MARKER not in response.json()["content"]


def test_repeated_unsafe_resume_is_rejected_without_persistence(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / "unsafe-tailored-resume.sqlite3"))
    _configure_llm(monkeypatch, _UnsafeResumeLLM())
    headers = _register("unsafe-tailored-resume-owner")
    profile_id = _create_profile(headers)
    job_id = _save_job(headers)

    response = client.post(
        f"/api/v1/saved-jobs/{job_id}/tailored-resumes",
        headers=headers,
        json={"resume_profile_id": profile_id},
    )

    assert response.status_code == 422
    assert response.json()["error_code"] == "generation_validation_failed"
    workspace = client.get(f"/api/v1/saved-jobs/{job_id}/workspace", headers=headers).json()
    assert workspace["application"] is None
    assert workspace["tailored_resume"] is None
