"""回归验证简历到搜索的流程会话的正常链路、失败边界和兼容契约。"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_create_profile_session_returns_v4_resource(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / "profile-session-create.sqlite3"))
    response = client.post("/api/v1/profile-sessions")

    assert response.status_code == 201
    payload = response.json()
    assert payload["session_id"]
    assert payload["status"] == "active"
    assert payload["current_step"] == "created"
    assert payload["resume_document_id"] is None
    assert payload["parsed_review_id"] is None
    assert payload["profile_draft_id"] is None
    assert payload["confirmed_profile_id"] is None
    assert payload["created_at"]
    assert payload["updated_at"]


def test_get_profile_session_returns_existing_session(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / "profile-session-get.sqlite3"))
    created = client.post("/api/v1/profile-sessions").json()

    response = client.get(f"/api/v1/profile-sessions/{created['session_id']}")

    assert response.status_code == 200
    assert response.json() == created


def test_get_unknown_profile_session_returns_404(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / "profile-session-missing.sqlite3"))
    response = client.get("/api/v1/profile-sessions/unknown-session")

    assert response.status_code == 404
    assert response.json()["error_code"] == "profile_session_not_found"
