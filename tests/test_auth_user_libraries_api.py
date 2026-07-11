from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _register(username: str) -> str:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "username": username,
            "password": "password-123",
            "display_name": username.title(),
        },
    )
    assert response.status_code == 201
    return response.json()["access_token"]


def _create_confirmed_profile(headers: dict[str, str]) -> dict:
    session = client.post("/api/v1/profile-sessions", headers=headers).json()
    client.post(
        f"/api/v1/profile-sessions/{session['session_id']}/resume-text",
        headers=headers,
        json={
            "text": (
                "Name: Jane Doe\n"
                "Role: Backend Engineer\n"
                "Skills: Python, FastAPI, SQL, Docker\n"
                "Project: Built a resume review and job search workflow.\n"
            )
        },
    )
    client.post(f"/api/v1/profile-sessions/{session['session_id']}/parse-resume", headers=headers)
    draft = client.post(
        f"/api/v1/profile-sessions/{session['session_id']}/profile-draft",
        headers=headers,
    ).json()
    return client.post(
        f"/api/v1/profile-drafts/{draft['profile_draft']['profile_draft_id']}/confirm",
        headers=headers,
    ).json()


def test_register_login_me_and_logout(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / "auth.sqlite3"))

    register_response = client.post(
        "/api/v1/auth/register",
        json={"username": "alice", "password": "password-123"},
    )

    assert register_response.status_code == 201
    token = register_response.json()["access_token"]
    assert register_response.json()["user"]["username"] == "alice"

    me_response = client.get("/api/v1/auth/me", headers=_auth_headers(token))
    assert me_response.status_code == 200
    assert me_response.json()["user"]["username"] == "alice"

    login_response = client.post(
        "/api/v1/auth/login",
        json={"username": "alice", "password": "password-123"},
    )
    assert login_response.status_code == 200
    assert login_response.json()["access_token"]

    logout_response = client.post("/api/v1/auth/logout", headers=_auth_headers(token))
    assert logout_response.status_code == 204

    revoked_response = client.get("/api/v1/auth/me", headers=_auth_headers(token))
    assert revoked_response.status_code == 401
    assert revoked_response.json()["error_code"] == "unauthorized"


def test_profile_session_is_user_scoped(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / "session-scope.sqlite3"))
    alice_token = _register("alice")
    bob_token = _register("bob")

    created = client.post(
        "/api/v1/profile-sessions",
        headers=_auth_headers(alice_token),
    ).json()

    own_response = client.get(
        f"/api/v1/profile-sessions/{created['session_id']}",
        headers=_auth_headers(alice_token),
    )
    assert own_response.status_code == 200

    other_response = client.get(
        f"/api/v1/profile-sessions/{created['session_id']}",
        headers=_auth_headers(bob_token),
    )
    assert other_response.status_code == 404
    assert other_response.json()["error_code"] == "profile_session_not_found"


def test_confirmed_profile_creates_resume_profile_library_item(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / "resume-profile-library.sqlite3"))
    token = _register("profile-user")
    headers = _auth_headers(token)

    confirmed = _create_confirmed_profile(headers)

    response = client.get("/api/v1/resume-profiles", headers=headers)

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["source_confirmed_profile_id"] == confirmed["confirmed_profile"]["confirmed_profile_id"]
    assert items[0]["is_default"] is True
    assert items[0]["raw_resume_text"].startswith("Name: Jane Doe")


def test_save_job_from_search_result_creates_saved_job_and_analysis(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / "saved-job.sqlite3"))
    token = _register("saved-job-user")
    headers = _auth_headers(token)
    confirmed = _create_confirmed_profile(headers)
    session_id = confirmed["profile_session"]["session_id"]

    run_response = client.post(
        "/api/v1/job-search-runs",
        headers=headers,
        json={"session_id": session_id, "search_mode": "local_mock"},
    )
    assert run_response.status_code == 200
    run = run_response.json()["job_search_run"]
    result = run["results"][0]

    save_response = client.post(
        "/api/v1/saved-jobs/from-search-result",
        headers=headers,
        json={
            "job_search_run_id": run["job_search_run_id"],
            "job_result_id": result["job_result_id"],
            "tags": ["priority"],
            "status": "interested",
        },
    )

    assert save_response.status_code == 200
    saved = save_response.json()
    assert saved["title"] == result["title"]
    assert saved["status"] == "interested"
    assert saved["latest_analysis"]["source_job_search_run_id"] == run["job_search_run_id"]
    assert saved["latest_analysis"]["source_job_result_id"] == result["job_result_id"]
    assert saved["latest_analysis"]["match_score"] == result["match_score"]

    duplicate_response = client.post(
        "/api/v1/saved-jobs/from-search-result",
        headers=headers,
        json={
            "job_search_run_id": run["job_search_run_id"],
            "job_result_id": result["job_result_id"],
        },
    )
    assert duplicate_response.status_code == 200
    assert duplicate_response.json()["saved_job_id"] == saved["saved_job_id"]

    list_response = client.get("/api/v1/saved-jobs", headers=headers)
    assert list_response.status_code == 200
    assert len(list_response.json()["items"]) == 1


def test_search_history_is_user_scoped_and_ordered(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / "search-history.sqlite3"))
    alice_headers = _auth_headers(_register("history-alice"))
    bob_headers = _auth_headers(_register("history-bob"))
    alice_confirmed = _create_confirmed_profile(alice_headers)
    bob_confirmed = _create_confirmed_profile(bob_headers)

    alice_session_id = alice_confirmed["profile_session"]["session_id"]
    bob_session_id = bob_confirmed["profile_session"]["session_id"]
    first = client.post(
        "/api/v1/job-search-runs",
        headers=alice_headers,
        json={"session_id": alice_session_id, "search_mode": "local_mock", "query": "first"},
    ).json()["job_search_run"]
    second = client.post(
        "/api/v1/job-search-runs",
        headers=alice_headers,
        json={"session_id": alice_session_id, "search_mode": "local_mock", "query": "second"},
    ).json()["job_search_run"]
    client.post(
        "/api/v1/job-search-runs",
        headers=bob_headers,
        json={"session_id": bob_session_id, "search_mode": "local_mock", "query": "private"},
    )

    response = client.get("/api/v1/job-search-runs?limit=1", headers=alice_headers)

    assert response.status_code == 200
    assert [item["job_search_run_id"] for item in response.json()["items"]] == [
        second["job_search_run_id"]
    ]
    assert first["job_search_run_id"] != second["job_search_run_id"]
    assert all(item["query"] != "private" for item in response.json()["items"])


def test_saved_job_analysis_history_is_user_scoped(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / "analysis-history.sqlite3"))
    owner_headers = _auth_headers(_register("analysis-owner"))
    other_headers = _auth_headers(_register("analysis-other"))
    confirmed = _create_confirmed_profile(owner_headers)
    session_id = confirmed["profile_session"]["session_id"]
    run = client.post(
        "/api/v1/job-search-runs",
        headers=owner_headers,
        json={"session_id": session_id, "search_mode": "local_mock"},
    ).json()["job_search_run"]
    request = {
        "job_search_run_id": run["job_search_run_id"],
        "job_result_id": run["results"][0]["job_result_id"],
    }
    saved = client.post(
        "/api/v1/saved-jobs/from-search-result", headers=owner_headers, json=request
    ).json()
    client.post("/api/v1/saved-jobs/from-search-result", headers=owner_headers, json=request)

    response = client.get(
        f"/api/v1/saved-jobs/{saved['saved_job_id']}/analyses", headers=owner_headers
    )
    forbidden = client.get(
        f"/api/v1/saved-jobs/{saved['saved_job_id']}/analyses", headers=other_headers
    )

    assert response.status_code == 200
    assert len(response.json()["items"]) == 2
    assert all(item["saved_job_id"] == saved["saved_job_id"] for item in response.json()["items"])
    assert forbidden.status_code == 404


def test_job_search_result_feedback_upserts_and_is_user_scoped(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / "result-feedback.sqlite3"))
    owner_headers = _auth_headers(_register("feedback-owner"))
    other_headers = _auth_headers(_register("feedback-other"))
    confirmed = _create_confirmed_profile(owner_headers)
    run = client.post(
        "/api/v1/job-search-runs",
        headers=owner_headers,
        json={
            "session_id": confirmed["profile_session"]["session_id"],
            "search_mode": "local_mock",
        },
    ).json()["job_search_run"]
    result_id = run["results"][0]["job_result_id"]
    endpoint = f"/api/v1/job-search-runs/{run['job_search_run_id']}/results/{result_id}/feedback"

    created = client.post(
        endpoint,
        headers=owner_headers,
        json={"feedback_type": "relevant", "note": "Strong match"},
    )
    updated = client.post(
        endpoint,
        headers=owner_headers,
        json={"feedback_type": "irrelevant", "note": "Wrong seniority"},
    )
    listed = client.get(
        f"/api/v1/job-search-runs/{run['job_search_run_id']}/feedback",
        headers=owner_headers,
    )
    other = client.get(
        f"/api/v1/job-search-runs/{run['job_search_run_id']}/feedback",
        headers=other_headers,
    )

    assert created.status_code == 200
    assert updated.status_code == 200
    assert updated.json()["feedback_id"] == created.json()["feedback_id"]
    assert updated.json()["feedback_type"] == "irrelevant"
    assert updated.json()["source_provider"] == "local_mock"
    assert updated.json()["resume_profile_id"] is not None
    assert len(listed.json()["items"]) == 1
    assert other.status_code == 404


def test_saved_job_status_history_tracks_transitions_and_is_user_scoped(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / "status-history.sqlite3"))
    owner_headers = _auth_headers(_register("status-owner"))
    other_headers = _auth_headers(_register("status-other"))
    confirmed = _create_confirmed_profile(owner_headers)
    run = client.post(
        "/api/v1/job-search-runs",
        headers=owner_headers,
        json={
            "session_id": confirmed["profile_session"]["session_id"],
            "search_mode": "local_mock",
        },
    ).json()["job_search_run"]
    saved = client.post(
        "/api/v1/saved-jobs/from-search-result",
        headers=owner_headers,
        json={
            "job_search_run_id": run["job_search_run_id"],
            "job_result_id": run["results"][0]["job_result_id"],
        },
    ).json()
    client.patch(
        f"/api/v1/saved-jobs/{saved['saved_job_id']}",
        headers=owner_headers,
        json={"status": "applied"},
    )
    updated = client.patch(
        f"/api/v1/saved-jobs/{saved['saved_job_id']}",
        headers=owner_headers,
        json={"status": "interviewing"},
    )
    client.post(
        "/api/v1/saved-jobs/from-search-result",
        headers=owner_headers,
        json={
            "job_search_run_id": run["job_search_run_id"],
            "job_result_id": run["results"][0]["job_result_id"],
        },
    )

    history_url = f"/api/v1/saved-jobs/{saved['saved_job_id']}/status-history"
    history = client.get(history_url, headers=owner_headers)
    other = client.get(history_url, headers=other_headers)

    assert updated.status_code == 200
    assert updated.json()["status"] == "interviewing"
    current = client.get(
        f"/api/v1/saved-jobs/{saved['saved_job_id']}", headers=owner_headers
    )
    assert current.json()["status"] == "interviewing"
    assert history.status_code == 200
    assert [item["to_status"] for item in history.json()["items"]] == [
        "interviewing",
        "applied",
        "saved",
    ]
    assert other.status_code == 404


def test_search_mission_is_user_scoped_and_drives_search_preview(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / "search-mission.sqlite3"))
    owner_headers = _auth_headers(_register("mission-owner"))
    other_headers = _auth_headers(_register("mission-other"))
    confirmed = _create_confirmed_profile(owner_headers)
    session_id = confirmed["profile_session"]["session_id"]
    mission_url = f"/api/v1/profile-sessions/{session_id}/search-mission"

    saved = client.put(
        mission_url,
        headers=owner_headers,
        json={
            "target_roles": ["AI Application Engineer"],
            "excluded_roles": ["Sales Engineer"],
            "preferred_industries": ["Healthcare"],
            "locations": ["Tokyo"],
            "work_arrangements": ["Hybrid"],
            "employment_types": ["Full-time"],
            "must_have": ["LLM applications"],
            "nice_to_have": ["FastAPI"],
            "ranking_priorities": ["Role fit"],
            "exploration_level": "balanced",
            "free_text": "Prefer applied AI over pure research.",
        },
    )
    interpreted = client.post(
        f"{mission_url}/interpret",
        headers=owner_headers,
        json={"use_llm": False, "llm_provider": "deepseek"},
    )
    confirmed_mission = client.post(f"{mission_url}/confirm", headers=owner_headers)
    preview = client.post(
        "/api/v1/job-search-runs/preview",
        headers=owner_headers,
        json={"session_id": session_id, "search_mode": "local_mock"},
    )
    forbidden = client.get(mission_url, headers=other_headers)

    assert saved.status_code == 200
    assert saved.json()["status"] == "draft"
    assert interpreted.status_code == 200
    assert interpreted.json()["analysis_mode"] == "deterministic"
    assert interpreted.json()["mission"]["target_roles"] == ["AI Application Engineer"]
    assert len(interpreted.json()["mission"]["clarification_questions"]) <= 3
    assert confirmed_mission.status_code == 200
    assert confirmed_mission.json()["status"] == "confirmed"
    assert preview.status_code == 200
    assert preview.json()["target_roles"][0] == "AI Application Engineer"
    assert preview.json()["locations"][0] == "Tokyo"
    assert preview.json()["search_mission_id"] == saved.json()["search_mission_id"]
    assert preview.json()["mission_excluded_roles"] == ["Sales Engineer"]
    assert forbidden.status_code == 404

    revised = client.put(
        mission_url,
        headers=owner_headers,
        json={**saved.json()["input"], "target_roles": ["Backend Engineer"]},
    )
    assert revised.json()["revision"] == confirmed_mission.json()["revision"] + 1
    assert revised.json()["status"] == "draft"
