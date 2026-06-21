from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_llm_status_endpoint_reports_configuration_without_network(monkeypatch) -> None:
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")

    response = client.get("/api/v1/llm/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "ollama"
    assert payload["configured"] is True


def test_llm_status_endpoint_reports_deepseek_switch_without_network(monkeypatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")

    response = client.get("/api/v1/llm/status?use_deepseek=true")

    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "deepseek"
    assert payload["configured"] is True
