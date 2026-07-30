"""回归验证认证账户与会话的正常链路、失败边界和兼容契约。"""

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
    profile = client.get("/api/v1/resume-profiles", headers=headers).json()["items"][0]

    run_response = client.post(
        "/api/v1/job-search-runs",
        headers=headers,
        json={"session_id": session_id, "search_mode": "local_mock"},
    )
    assert run_response.status_code == 200
    run = run_response.json()["job_search_run"]
    assert run["resume_profile_id"] == profile["resume_profile_id"]
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
    duplicate = duplicate_response.json()
    assert duplicate["saved_job_id"] == saved["saved_job_id"]
    assert (
        duplicate["latest_analysis"]["saved_job_analysis_id"]
        != saved["latest_analysis"]["saved_job_analysis_id"]
    )

    analyses_response = client.get(
        f"/api/v1/saved-jobs/{saved['saved_job_id']}/analyses", headers=headers
    )
    assert analyses_response.status_code == 200
    analyses = analyses_response.json()["items"]
    assert len(analyses) == 2
    assert analyses[0]["saved_job_analysis_id"] == duplicate["latest_analysis"][
        "saved_job_analysis_id"
    ]
    assert analyses[1]["saved_job_analysis_id"] == saved["latest_analysis"][
        "saved_job_analysis_id"
    ]

    contexts_response = client.get(
        f"/api/v1/saved-jobs/{saved['saved_job_id']}/contexts", headers=headers
    )
    assert contexts_response.status_code == 200
    contexts = contexts_response.json()["items"]
    assert len(contexts) == 1
    assert contexts[0]["resume_profile_id"] == profile["resume_profile_id"]
    assert contexts[0]["job_search_run_id"] == run["job_search_run_id"]
    assert contexts[0]["job_search_result_id"] == result["job_result_id"]
    assert contexts[0]["saved_job_analysis_id"] == duplicate["latest_analysis"][
        "saved_job_analysis_id"
    ]
    assert contexts[0]["profile_label"] == profile["name"]
    assert contexts[0]["search_query"] == run["query"]

    list_response = client.get("/api/v1/saved-jobs", headers=headers)
    assert list_response.status_code == 200
    assert len(list_response.json()["items"]) == 1


def test_duplicate_saved_job_keeps_the_richer_current_jd(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / "saved-job-refresh.sqlite3"))
    headers = _auth_headers(_register("saved-job-refresh"))
    payload = {
        "source_url": "https://jobs.example.com/backend",
        "title": "Backend Engineer",
        "company": "Example",
        "raw_jd_text": "Python required.",
        "structured_jd": {"requirements": ["Python"], "source": "search"},
    }
    first = client.post("/api/v1/saved-jobs", headers=headers, json=payload).json()

    richer = client.post(
        "/api/v1/saved-jobs",
        headers=headers,
        json={
            **payload,
            "raw_jd_text": "Python and SQL are required. Build and maintain backend APIs.",
            "structured_jd": {
                "requirements": ["Python", "SQL"],
                "evidence_quotes": ["Python and SQL are required."],
            },
        },
    ).json()
    shorter = client.post(
        "/api/v1/saved-jobs",
        headers=headers,
        json={**payload, "raw_jd_text": "Python.", "structured_jd": {"requirements": []}},
    ).json()

    assert richer["saved_job_id"] == first["saved_job_id"]
    assert richer["raw_jd_text"] == "Python and SQL are required. Build and maintain backend APIs."
    assert richer["structured_jd"]["requirements"] == ["Python", "SQL"]
    assert richer["structured_jd"]["source"] == "search"
    assert shorter["raw_jd_text"] == richer["raw_jd_text"]
    assert shorter["structured_jd"]["requirements"] == ["Python", "SQL"]


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

    answered = client.put(
        mission_url,
        headers=owner_headers,
        json={
            **revised.json()["input"],
            "clarification_answers": [{
                "question": "Should the search emphasize applied work?",
                "answer": "Yes, prioritize applied product engineering roles.",
            }],
        },
    )
    assert answered.status_code == 200
    assert answered.json()["revision"] == revised.json()["revision"]
    assert answered.json()["input"]["clarification_answers"][0]["answer"].startswith("Yes")


def test_library_deletes_do_not_cascade_across_product_libraries(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / "independent-delete.sqlite3"))
    headers = _auth_headers(_register("delete-owner"))
    other_headers = _auth_headers(_register("delete-other"))
    confirmed = _create_confirmed_profile(headers)
    session_id = confirmed["profile_session"]["session_id"]

    first_run = client.post(
        "/api/v1/job-search-runs",
        headers=headers,
        json={"session_id": session_id, "search_mode": "local_mock"},
    ).json()["job_search_run"]
    first_saved = client.post(
        "/api/v1/saved-jobs/from-search-result",
        headers=headers,
        json={
            "job_search_run_id": first_run["job_search_run_id"],
            "job_result_id": first_run["results"][0]["job_result_id"],
        },
    ).json()
    profile = client.get("/api/v1/resume-profiles", headers=headers).json()["items"][0]

    forbidden_delete = client.delete(
        f"/api/v1/job-search-runs/{first_run['job_search_run_id']}", headers=other_headers
    )
    run_delete = client.delete(
        f"/api/v1/job-search-runs/{first_run['job_search_run_id']}", headers=headers
    )
    saved_after_run_delete = client.get(
        f"/api/v1/saved-jobs/{first_saved['saved_job_id']}", headers=headers
    )

    second_run = client.post(
        "/api/v1/job-search-runs",
        headers=headers,
        json={"session_id": session_id, "search_mode": "local_mock"},
    ).json()["job_search_run"]
    second_saved = client.post(
        "/api/v1/saved-jobs/from-search-result",
        headers=headers,
        json={
            "job_search_run_id": second_run["job_search_run_id"],
            "job_result_id": second_run["results"][1]["job_result_id"],
        },
    ).json()
    saved_delete = client.delete(
        f"/api/v1/saved-jobs/{second_saved['saved_job_id']}", headers=headers
    )
    run_after_saved_delete = client.get(
        f"/api/v1/job-search-runs/{second_run['job_search_run_id']}", headers=headers
    )

    profile_delete = client.delete(
        f"/api/v1/resume-profiles/{profile['resume_profile_id']}", headers=headers
    )
    run_after_profile_delete = client.get(
        f"/api/v1/job-search-runs/{second_run['job_search_run_id']}", headers=headers
    )
    first_saved_after_profile_delete = client.get(
        f"/api/v1/saved-jobs/{first_saved['saved_job_id']}", headers=headers
    )
    first_contexts_after_profile_delete = client.get(
        f"/api/v1/saved-jobs/{first_saved['saved_job_id']}/contexts", headers=headers
    )

    assert forbidden_delete.status_code == 404
    assert run_delete.status_code == 204
    assert saved_after_run_delete.status_code == 200
    assert saved_after_run_delete.json()["latest_analysis"]["source_job_search_run_id"] is None
    assert saved_delete.status_code == 204
    assert run_after_saved_delete.status_code == 200
    assert profile_delete.status_code == 204
    assert run_after_profile_delete.status_code == 200
    assert first_saved_after_profile_delete.status_code == 200
    assert first_saved_after_profile_delete.json()["latest_analysis"]["resume_profile_id"] is None
    assert first_contexts_after_profile_delete.status_code == 200
    assert first_contexts_after_profile_delete.json()["items"][0]["resume_profile_id"] is None
    assert first_contexts_after_profile_delete.json()["items"][0]["profile_label"]
