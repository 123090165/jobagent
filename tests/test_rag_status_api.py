from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import app
from app.repositories.rag_sync_repository import RAGSyncRepository


client = TestClient(app)


def _register(username: str) -> tuple[dict[str, str], str]:
    response = client.post(
        "/api/v1/auth/register",
        json={"username": username, "password": "password-123"},
    )
    assert response.status_code == 201
    body = response.json()
    return (
        {"Authorization": f"Bearer {body['access_token']}"},
        body["user"]["user_id"],
    )


def test_rag_status_requires_authentication() -> None:
    response = client.get("/api/v1/rag/status")

    assert response.status_code == 401


def test_rag_status_reports_unconfigured_service_for_current_user(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / "rag-status.sqlite3"))
    monkeypatch.delenv("JOBAGENT_RAG_SYNC_ENABLED", raising=False)
    monkeypatch.setattr(
        "app.api.v1.rag.resolve_modular_rag_service",
        lambda: None,
    )
    headers, _ = _register("rag-status-off")

    response = client.get("/api/v1/rag/status", headers=headers)

    assert response.status_code == 200
    assert response.json() == {
        "sync_enabled": False,
        "mcp_configured": False,
        "reachable": False,
        "server_name": None,
        "server_version": None,
        "reason": "not_configured",
        "overview": {
            "resource_count": 0,
            "ready_count": 0,
            "pending_resource_count": 0,
            "failed_resource_count": 0,
            "deleted_count": 0,
            "pending_event_count": 0,
            "processing_event_count": 0,
            "failed_event_count": 0,
            "oldest_pending_at": None,
            "last_synced_at": None,
            "recent_failures": [],
        },
    }


def test_rag_status_is_scoped_to_authenticated_user(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / "rag-status-user.sqlite3"))
    monkeypatch.setenv("JOBAGENT_RAG_SYNC_ENABLED", "true")

    class ReachableService:
        async def inspect(self):
            return SimpleNamespace(
                server_name="modular-rag-mcp-server",
                server_version="0.1.0",
            )

    monkeypatch.setattr(
        "app.api.v1.rag.resolve_modular_rag_service",
        lambda: ReachableService(),
    )
    headers, user_id = _register("rag-status-user")
    _, other_user_id = _register("rag-status-other")
    RAGSyncRepository().enqueue(
        user_id=user_id,
        resource_type="saved_job",
        resource_id="job-1",
        operation="upsert",
    )
    RAGSyncRepository().enqueue(
        user_id=other_user_id,
        resource_type="saved_job",
        resource_id="job-2",
        operation="upsert",
    )

    response = client.get("/api/v1/rag/status", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["sync_enabled"] is True
    assert body["reachable"] is True
    assert body["server_name"] == "modular-rag-mcp-server"
    assert body["overview"]["resource_count"] == 1
    assert body["overview"]["pending_event_count"] == 1
