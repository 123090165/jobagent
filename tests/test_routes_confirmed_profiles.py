from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from tests.test_confirmed_profile_storage_service import _request

client = TestClient(app)


def _payload() -> dict:
    return _request().model_dump(mode="json")


def test_post_confirmed_profile_returns_id(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / "confirmed-api.sqlite3"))

    response = client.post("/profile/confirmed", json=_payload())

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] > 0
    assert payload["summary"]["skill_count"] == 2


def test_get_confirmed_profiles_returns_list(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / "confirmed-api.sqlite3"))
    client.post("/profile/confirmed", json=_payload())

    response = client.get("/profile/confirmed")

    assert response.status_code == 200
    assert response.json()[0]["target_roles"] == ["Backend Engineer"]


def test_get_confirmed_profile_detail_returns_record(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / "confirmed-api.sqlite3"))
    created = client.post("/profile/confirmed", json=_payload()).json()

    response = client.get(f"/profile/confirmed/{created['id']}")

    assert response.status_code == 200
    assert response.json()["confirmed_result"]["confirmed_profile"]["skills"]


def test_invalid_decision_status_returns_validation_error(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / "confirmed-api.sqlite3"))
    payload = _payload()
    payload["suggestion_decisions"][0]["decision_status"] = "maybe"

    response = client.post("/profile/confirmed", json=payload)

    assert response.status_code == 422


def test_unknown_id_returns_expected_error(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / "confirmed-api.sqlite3"))

    response = client.get("/profile/confirmed/999")

    assert response.status_code == 404
    assert response.json()["error_code"] == "confirmed_profile_not_found"
