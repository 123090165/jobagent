"""回归验证Job Brief的正常链路、失败边界和兼容契约。"""

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


def _create_job(headers: dict[str, str]) -> dict:
    response = client.post(
        "/api/v1/saved-jobs",
        headers=headers,
        json={
            "title": "Backend Engineer",
            "company": "Example",
            "raw_jd_text": "Build Python APIs with FastAPI and SQL.",
            "structured_jd": {"requirements": ["Python", "FastAPI", "SQL"]},
        },
    )
    assert response.status_code == 200
    return response.json()


def test_job_brief_generation_is_versioned_and_user_scoped(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / "job-brief.sqlite3"))
    alice = _register("brief-alice")
    bob = _register("brief-bob")
    job = _create_job(alice)

    first = client.post(
        f"/api/v1/saved-jobs/{job['saved_job_id']}/briefs",
        headers=alice,
        json={"llm_provider": "deepseek"},
    )
    second = client.post(
        f"/api/v1/saved-jobs/{job['saved_job_id']}/briefs",
        headers=alice,
        json={"llm_provider": "deepseek"},
    )

    assert first.status_code == 200
    assert first.json()["version"] == 1
    assert first.json()["analysis_mode"] == "fallback"
    assert first.json()["content"]["next_actions"]
    assert second.status_code == 200
    assert second.json()["version"] == 2

    history = client.get(
        f"/api/v1/saved-jobs/{job['saved_job_id']}/briefs", headers=alice
    )
    assert history.status_code == 200
    assert [item["version"] for item in history.json()["items"]] == [2, 1]

    other_user = client.get(
        f"/api/v1/saved-jobs/{job['saved_job_id']}/briefs", headers=bob
    )
    assert other_user.status_code == 404


def test_deleting_saved_job_removes_only_its_briefs(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / "job-brief-delete.sqlite3"))
    headers = _register("brief-delete")
    first_job = _create_job(headers)
    second_job = client.post(
        "/api/v1/saved-jobs",
        headers=headers,
        json={"title": "Data Engineer", "raw_jd_text": "Build data pipelines."},
    ).json()
    for job in (first_job, second_job):
        response = client.post(
            f"/api/v1/saved-jobs/{job['saved_job_id']}/briefs",
            headers=headers,
            json={},
        )
        assert response.status_code == 200

    assert client.delete(
        f"/api/v1/saved-jobs/{first_job['saved_job_id']}", headers=headers
    ).status_code == 204
    remaining = client.get(
        f"/api/v1/saved-jobs/{second_job['saved_job_id']}/briefs", headers=headers
    )
    assert remaining.status_code == 200
    assert len(remaining.json()["items"]) == 1
