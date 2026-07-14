from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _headers(username: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/register",
        json={"username": username, "password": "password-123"},
    )
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _job(headers: dict[str, str]) -> dict:
    response = client.post(
        "/api/v1/saved-jobs",
        headers=headers,
        json={
            "title": "Operations Analyst",
            "company": "Example",
            "raw_jd_text": (
                "Use Microsoft Office for weekly reporting and perform basic Linux operations. "
                "Analyze data with SQL and communicate findings to stakeholders."
            ),
        },
    )
    assert response.status_code == 200
    return response.json()


def test_preparation_generates_gaps_resources_questions_and_prompt(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / "preparation.sqlite3"))
    monkeypatch.delenv("JOBAGENT_LEARNING_MCP_URL", raising=False)
    alice = _headers("preparation-alice")
    bob = _headers("preparation-bob")
    job = _job(alice)

    response = client.post(
        f"/api/v1/saved-jobs/{job['saved_job_id']}/preparation",
        headers=alice,
        json={"llm_provider": "deepseek"},
    )

    assert response.status_code == 200
    workspace = response.json()
    assert workspace["status"] == "questions_ready"
    assert workspace["analysis_mode"] == "fallback"
    question_generation = workspace["question_generation"]
    assert question_generation["mode"] == "fallback"
    assert question_generation["provider"] == "deepseek"
    assert question_generation["prompt_version"] == "interview_preparation_questions_v6"
    assert question_generation["attempts"] == 1
    assert question_generation["fallback_reason"].startswith("LLMServiceError:")
    assert question_generation["attempt_errors"] == [
        question_generation["fallback_reason"]
    ]
    assert workspace["recommendation_generation"] is None
    assert {item["skill"] for item in workspace["skill_gaps"]} >= {"Microsoft Office", "Linux"}
    assert len(workspace["questions"]) <= 5
    assert all("Do you know" not in item["prompt"] for item in workspace["questions"])
    assert workspace["learning_resources"] == []
    assert workspace["resource_mode"] == "pending_answers"

    prompt = client.get(
        f"/api/v1/saved-jobs/{job['saved_job_id']}/preparation/prompt.txt",
        headers=alice,
    )
    assert prompt.status_code == 200
    assert "JOBAGENT EVIDENCE INTERVIEW" in prompt.text
    assert "user-reported" in prompt.text
    assert "attachment" in prompt.headers["content-disposition"]

    other_user = client.get(
        f"/api/v1/saved-jobs/{job['saved_job_id']}/preparation", headers=bob
    )
    assert other_user.status_code == 404


def test_preparation_accepts_answers_and_preserves_saved_job(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / "preparation-answer.sqlite3"))
    headers = _headers("preparation-answer")
    job = _job(headers)
    workspace = client.post(
        f"/api/v1/saved-jobs/{job['saved_job_id']}/preparation",
        headers=headers,
        json={},
    ).json()
    question = workspace["questions"][0]

    incomplete = client.put(
        f"/api/v1/saved-jobs/{job['saved_job_id']}/preparation/answers",
        headers=headers,
        json={
            "answers": [{
                "question_id": question["question_id"],
                "answer": "I diagnosed a Linux permission failure using ls -l and chmod, then reran the service check.",
            }]
        },
    )
    assert incomplete.status_code == 400
    assert incomplete.json()["error_code"] == "preparation_answers_incomplete"

    response = client.put(
        f"/api/v1/saved-jobs/{job['saved_job_id']}/preparation/answers",
        headers=headers,
        json={
            "answers": [
                {
                    "question_id": item["question_id"],
                    "answer": "I used this capability in a bounded exercise and need to clarify the exact scope.",
                }
                for item in workspace["questions"]
            ]
        },
    )

    assert response.status_code == 200
    paused = response.json()
    assert paused["status"] == "paused"
    assert any(answer["route"] == "clarify" for answer in paused["answers"])

    response = client.put(
        f"/api/v1/saved-jobs/{job['saved_job_id']}/preparation/answers",
        headers=headers,
        json={
            "answers": [
                {
                    "question_id": item["question_id"],
                    "answer": "I used this capability in a bounded exercise and need to clarify the exact scope.",
                }
                for item in workspace["questions"]
            ]
        },
    )
    assert response.status_code == 200
    completed = response.json()
    assert completed["status"] == "completed"
    assert completed["answers"][0]["question_id"] == question["question_id"]
    assert completed["recommendations"]
    assert completed["question_generation"] is not None
    assert completed["recommendation_generation"] is not None
    assert "questions:" in completed["fallback_reason"]
    assert "recommendations:" in completed["fallback_reason"]
    assert client.get(
        f"/api/v1/saved-jobs/{job['saved_job_id']}", headers=headers
    ).status_code == 200

    invalid = client.put(
        f"/api/v1/saved-jobs/{job['saved_job_id']}/preparation/answers",
        headers=headers,
        json={"answers": [{"question_id": "unknown", "answer": "value"}]},
    )
    assert invalid.status_code == 400


def test_preparation_structured_answers_control_state_and_recommendation(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / "preparation-structured.sqlite3"))
    headers = _headers("preparation-structured")
    job = _job(headers)
    workspace = client.post(
        f"/api/v1/saved-jobs/{job['saved_job_id']}/preparation",
        headers=headers,
        json={},
    ).json()
    questions = workspace["questions"]
    assert questions[0]["options"]

    answers = [
        {"question_id": question["question_id"], "experience_level": "no_experience"}
        for question in questions
    ]
    paused = client.put(
        f"/api/v1/saved-jobs/{job['saved_job_id']}/preparation/answers",
        headers=headers,
        json={"answers": answers[:1], "action": "save"},
    )
    assert paused.status_code == 200
    assert paused.json()["status"] == "paused"
    assert paused.json()["recommendations"] == []

    completed = client.put(
        f"/api/v1/saved-jobs/{job['saved_job_id']}/preparation/answers",
        headers=headers,
        json={"answers": answers, "action": "complete"},
    )
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"
    assert all(gap["evidence_origin"] == "user_reported" for gap in completed.json()["skill_gaps"])
    assert {item["action_type"] for item in completed.json()["recommendations"]} == {"capability_gap"}
    assert {item["source"] for item in completed.json()["learning_resources"]} >= {
        "Ubuntu Documentation", "Microsoft Support"
    }


def test_preparation_pauses_for_focused_detail_then_resumes(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / "preparation-detail.sqlite3"))
    headers = _headers("preparation-detail")
    job = _job(headers)
    workspace = client.post(
        f"/api/v1/saved-jobs/{job['saved_job_id']}/preparation",
        headers=headers,
        json={},
    ).json()
    first = workspace["questions"][0]
    required = next(
        item for item in first["options"] if item["detail_policy"] == "required"
    )
    answers = [
        {
            "question_id": question["question_id"],
            "experience_level": "no_experience",
        }
        for question in workspace["questions"]
    ]
    answers[0] = {
        "question_id": first["question_id"],
        "selected_option_id": required["option_id"],
    }

    response = client.put(
        f"/api/v1/saved-jobs/{job['saved_job_id']}/preparation/answers",
        headers=headers,
        json={"answers": answers, "action": "complete"},
    )

    assert response.status_code == 200
    paused = response.json()
    assert paused["status"] == "paused"
    first_answer = next(
        item for item in paused["answers"] if item["question_id"] == first["question_id"]
    )
    assert first_answer["route"] == "ask_evidence"
    assert first_answer["evidence_transition"] == "partial"
    assert first_answer["pending_prompt"]

    completed = client.put(
        f"/api/v1/saved-jobs/{job['saved_job_id']}/preparation/answers",
        headers=headers,
        json={
            "answers": [{
                "question_id": first["question_id"],
                "selected_option_id": required["option_id"],
                "detail": (
                    "I implemented the workflow personally, used a bounded dataset, "
                    "and evaluated the result on 200 samples."
                ),
            }],
            "action": "complete",
        },
    )
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"
    resolved = next(
        item for item in completed.json()["answers"]
        if item["question_id"] == first["question_id"]
    )
    assert resolved["evidence_transition"] == "supported"


def test_preparation_can_stop_without_answers_or_summary(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / "preparation-stop.sqlite3"))
    headers = _headers("preparation-stop")
    job = _job(headers)
    client.post(
        f"/api/v1/saved-jobs/{job['saved_job_id']}/preparation",
        headers=headers,
        json={},
    )

    stopped = client.put(
        f"/api/v1/saved-jobs/{job['saved_job_id']}/preparation/answers",
        headers=headers,
        json={"answers": [], "action": "stop"},
    )

    assert stopped.status_code == 200
    assert stopped.json()["status"] == "stopped"
    assert stopped.json()["recommendations"] == []
