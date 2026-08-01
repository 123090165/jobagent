from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _register(username: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/register",
        json={"username": username, "password": "password-123"},
    )
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _save_job(headers: dict[str, str], title: str = "Backend Engineer") -> dict:
    response = client.post(
        "/api/v1/saved-jobs",
        headers=headers,
        json={
            "title": title,
            "company": "JobAgent",
            "source_provider": "boss",
            "source_url": f"https://www.zhipin.com/job_detail/{title}.html",
            "raw_jd_text": "Build Python and FastAPI services for an AI product.",
        },
    )
    assert response.status_code == 200
    return response.json()


def test_user_can_manually_start_application_tracking(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / "application.sqlite3"))
    headers = _register("application-owner")
    job = _save_job(headers)
    endpoint = f"/api/v1/saved-jobs/{job['saved_job_id']}/application"

    created = client.post(endpoint, headers=headers, json={})
    repeated = client.post(endpoint, headers=headers, json={})
    workspace = client.get(
        f"/api/v1/saved-jobs/{job['saved_job_id']}/workspace",
        headers=headers,
    )

    assert created.status_code == 201
    assert repeated.status_code == 201
    assert repeated.json()["application_id"] == created.json()["application_id"]
    assert created.json()["stage"] == "not_started"
    assert created.json()["next_action"] == "generate_greeting"
    assert workspace.status_code == 200
    assert workspace.json()["application"]["application_id"] == created.json()["application_id"]
    assert [event["event_type"] for event in workspace.json()["events"]] == ["stage_changed"]


def test_application_transition_sets_default_action_and_is_user_scoped(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / "application-scope.sqlite3"))
    owner_headers = _register("application-transition-owner")
    other_headers = _register("application-transition-other")
    job = _save_job(owner_headers, "Agent Engineer")
    application = client.post(
        f"/api/v1/saved-jobs/{job['saved_job_id']}/application",
        headers=owner_headers,
        json={},
    ).json()

    updated = client.patch(
        f"/api/v1/job-applications/{application['application_id']}",
        headers=owner_headers,
        json={"stage": "contacted", "detail": "Greeting sent manually."},
    )
    forbidden = client.patch(
        f"/api/v1/job-applications/{application['application_id']}",
        headers=other_headers,
        json={"stage": "closed"},
    )
    invalid = client.patch(
        f"/api/v1/job-applications/{application['application_id']}",
        headers=owner_headers,
        json={"stage": "resume_ready"},
    )

    assert updated.status_code == 200
    assert updated.json()["stage"] == "contacted"
    assert updated.json()["next_action"] == "wait_for_reply"
    assert updated.json()["contacted_at"] is not None
    assert forbidden.status_code == 404
    assert invalid.status_code == 409
