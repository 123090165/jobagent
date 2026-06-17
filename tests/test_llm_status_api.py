from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_llm_status_endpoint_reports_configuration_without_network(monkeypatch) -> None:
    monkeypatch.setenv("JOBAGENT_LLM_PROVIDER", "mock")

    response = client.get("/api/v1/llm/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "mock"
    assert payload["configured"] is True
