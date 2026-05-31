from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from tests.test_mock_pipeline import SAMPLE_JD, SAMPLE_RESUME

client = TestClient(app)


def test_health_endpoint() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_full_analysis_endpoint_returns_report() -> None:
    response = client.post(
        "/analyze/full",
        json={"resume_text": SAMPLE_RESUME, "jd_text": SAMPLE_JD},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["resume_profile"]["skills"]
    assert payload["job_analysis"]["required_skills"]
    assert payload["match_report"]["overall_score"] > 0
    assert "匹配度总览" in payload["markdown_report"]
    assert len(payload["workflow_steps"]) == 6
    assert payload["workflow_steps"][0]["mode"] == "mock"
    assert payload["workflow_steps"][0]["workflow_run_id"]
    assert payload["workflow_steps"][0]["duration_ms"] >= 0
    optimize_step = next(
        step for step in payload["workflow_steps"] if step["name"] == "ResumeOptimizeAgent"
    )
    assert optimize_step["mode"] == "mock"
    challenge_step = next(
        step for step in payload["workflow_steps"] if step["name"] == "ProjectInterviewAgent"
    )
    assert challenge_step["mode"] == "mock"


def test_full_analysis_endpoint_rejects_empty_resume() -> None:
    response = client.post(
        "/analyze/full",
        json={"resume_text": "", "jd_text": SAMPLE_JD},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "resume_text cannot be empty"
    assert response.json()["error_code"] == "analysis_input_invalid"


def test_full_analysis_endpoint_accepts_resume_optimize_llm_flag(monkeypatch) -> None:
    monkeypatch.delenv("JOBAGENT_LLM_API_KEY", raising=False)

    response = client.post(
        "/analyze/full",
        json={
            "resume_text": SAMPLE_RESUME,
            "jd_text": SAMPLE_JD,
            "use_llm_resume_optimize": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    optimize_step = next(
        step for step in payload["workflow_steps"] if step["name"] == "ResumeOptimizeAgent"
    )
    assert optimize_step["mode"] == "fallback"
    assert optimize_step["fallback_reason"] == "LLMServiceError"
    assert payload["optimization_result"]["jd_targeted_bullets"]


def test_full_analysis_endpoint_accepts_project_challenge_llm_flag(monkeypatch) -> None:
    monkeypatch.delenv("JOBAGENT_LLM_API_KEY", raising=False)

    response = client.post(
        "/analyze/full",
        json={
            "resume_text": SAMPLE_RESUME,
            "jd_text": SAMPLE_JD,
            "use_llm_project_challenge": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    challenge_step = next(
        step for step in payload["workflow_steps"] if step["name"] == "ProjectInterviewAgent"
    )
    assert challenge_step["mode"] == "fallback"
    assert challenge_step["fallback_reason"] == "LLMServiceError"
    assert payload["project_challenge_report"]["basic_questions"]


def test_stepwise_api_flow() -> None:
    resume_response = client.post("/resume/parse", json={"resume_text": SAMPLE_RESUME})
    assert resume_response.status_code == 200

    jd_response = client.post("/jobs/analyze", json={"jd_text": SAMPLE_JD})
    assert jd_response.status_code == 200

    match_response = client.post(
        "/match/analyze",
        json={
            "resume_profile": resume_response.json(),
            "job_analysis": jd_response.json(),
        },
    )
    assert match_response.status_code == 200

    full_response = client.post(
        "/analyze/full",
        json={"resume_text": SAMPLE_RESUME, "jd_text": SAMPLE_JD},
    )
    full_payload = full_response.json()

    report_response = client.post(
        "/reports/generate",
        json={
            "resume_profile": full_payload["resume_profile"],
            "job_analysis": full_payload["job_analysis"],
            "match_report": full_payload["match_report"],
            "optimization_result": full_payload["optimization_result"],
            "project_challenge_report": full_payload["project_challenge_report"],
        },
    )

    assert report_response.status_code == 200
    assert "markdown_report" in report_response.json()
    assert "项目拷打问题" in report_response.json()["markdown_report"]


def test_resume_parse_endpoint_returns_error_code_for_empty_text() -> None:
    response = client.post("/resume/parse", json={"resume_text": ""})

    assert response.status_code == 400
    payload = response.json()
    assert payload["detail"] == "resume_text cannot be empty"
    assert payload["error_code"] == "resume_text_empty"


def test_resume_parse_file_endpoint_accepts_txt() -> None:
    response = client.post(
        "/resume/parse-file",
        files={"file": ("resume.txt", SAMPLE_RESUME.encode("utf-8"), "text/plain")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["filename"] == "resume.txt"
    assert payload["file_type"] == "txt"
    assert payload["extracted_text"] == SAMPLE_RESUME.strip()
    assert payload["resume_profile"]["raw_text"] == SAMPLE_RESUME.strip()
    assert payload["resume_profile"]["skills"]


def test_resume_parse_file_endpoint_accepts_md() -> None:
    markdown_resume = f"# Resume\n\n{SAMPLE_RESUME}"

    response = client.post(
        "/resume/parse-file",
        files={"file": ("resume.md", markdown_resume.encode("utf-8"), "text/markdown")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["filename"] == "resume.md"
    assert payload["file_type"] == "md"
    assert payload["extracted_text"].startswith("# Resume")
    assert payload["resume_profile"]["raw_text"].startswith("# Resume")


def test_resume_parse_file_endpoint_rejects_empty_file() -> None:
    response = client.post(
        "/resume/parse-file",
        files={"file": ("resume.txt", b"", "text/plain")},
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["detail"] == "resume file cannot be empty"
    assert payload["error_code"] == "resume_file_empty"


def test_resume_parse_file_endpoint_rejects_unsupported_extension() -> None:
    response = client.post(
        "/resume/parse-file",
        files={"file": ("resume.pdf", b"fake pdf", "application/pdf")},
    )

    assert response.status_code == 400
    payload = response.json()
    assert "unsupported resume file type" in payload["detail"]
    assert payload["error_code"] == "resume_file_type_unsupported"


def test_resume_parse_file_endpoint_rejects_decode_failure() -> None:
    response = client.post(
        "/resume/parse-file",
        files={"file": ("resume.txt", b"\xff\xfe\x00\x00", "text/plain")},
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["detail"] == "resume file must be UTF-8 text"
    assert payload["error_code"] == "resume_file_decode_failed"


def test_resume_parse_file_endpoint_rejects_oversized_file(monkeypatch) -> None:
    monkeypatch.setenv("JOBAGENT_MAX_RESUME_FILE_BYTES", "16")

    response = client.post(
        "/resume/parse-file",
        files={"file": ("resume.txt", b"this resume is too long", "text/plain")},
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["detail"] == "resume file is too large"
    assert payload["error_code"] == "resume_file_too_large"


def test_full_analysis_can_save_and_load_record(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / "api-test.sqlite3"))

    response = client.post(
        "/analyze/full",
        json={
            "resume_text": SAMPLE_RESUME,
            "jd_text": SAMPLE_JD,
            "save_result": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["record_id"] is not None

    record_response = client.get(f"/records/{payload['record_id']}")
    assert record_response.status_code == 200
    record = record_response.json()
    assert record["id"] == payload["record_id"]
    assert record["markdown_report"] == payload["markdown_report"]
    assert len(record["workflow_steps"]) == 6
    assert record["workflow_steps"][0]["name"] == "ResumeParseAgent"
    assert record["workflow_steps"][0]["workflow_run_id"] == payload["workflow_steps"][0]["workflow_run_id"]
    assert record["workflow_steps"][0]["duration_ms"] >= 0


def test_record_endpoint_returns_404_for_missing_record(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / "missing.sqlite3"))

    response = client.get("/records/999")

    assert response.status_code == 404
    assert response.json()["detail"] == "record not found"


def test_can_list_records_and_jobs_after_saving(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / "job-list.sqlite3"))

    save_response = client.post(
        "/analyze/full",
        json={
            "resume_text": SAMPLE_RESUME,
            "jd_text": SAMPLE_JD,
            "save_result": True,
        },
    )
    assert save_response.status_code == 200

    records_response = client.get("/records", params={"keyword": "Python"})
    assert records_response.status_code == 200
    records = records_response.json()
    assert len(records) == 1
    assert records[0]["overall_score"] > 0

    jobs_response = client.get("/jobs", params={"keyword": "Python"})
    assert jobs_response.status_code == 200
    jobs = jobs_response.json()
    assert len(jobs) == 1
    assert jobs[0]["analysis_count"] == 1

    job_response = client.get(f"/jobs/{jobs[0]['id']}")
    assert job_response.status_code == 200
    assert job_response.json()["analysis_count"] == 1


def test_job_endpoint_returns_404_for_missing_job(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / "missing-job.sqlite3"))

    response = client.get("/jobs/999")

    assert response.status_code == 404
    assert response.json()["detail"] == "job not found"


def test_application_tracker_api_flow(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / "applications.sqlite3"))

    save_response = client.post(
        "/analyze/full",
        json={
            "resume_text": SAMPLE_RESUME,
            "jd_text": SAMPLE_JD,
            "save_result": True,
        },
    )
    assert save_response.status_code == 200

    jobs_response = client.get("/jobs")
    job_id = jobs_response.json()[0]["id"]

    create_response = client.post(
        "/applications",
        json={
            "job_id": job_id,
            "status": "interested",
            "notes": "岗位匹配度不错",
            "next_action": "定制简历",
        },
    )
    assert create_response.status_code == 200
    application = create_response.json()
    assert application["status"] == "interested"
    assert application["job_id"] == job_id

    patch_response = client.patch(
        f"/applications/{application['id']}",
        json={"status": "applied", "next_action": "等待反馈"},
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["status"] == "applied"

    list_response = client.get("/applications", params={"status": "applied"})
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    detail_response = client.get(f"/applications/{application['id']}")
    assert detail_response.status_code == 200
    assert detail_response.json()["next_action"] == "等待反馈"


def test_resume_version_api_flow(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / "resume-version-api.sqlite3"))

    save_response = client.post(
        "/analyze/full",
        json={
            "resume_text": SAMPLE_RESUME,
            "jd_text": SAMPLE_JD,
            "save_result": True,
        },
    )
    assert save_response.status_code == 200
    analysis_id = save_response.json()["record_id"]

    jobs_response = client.get("/jobs")
    job_id = jobs_response.json()[0]["id"]

    create_response = client.post(
        "/resume-versions",
        json={
            "label": "v1-api-targeted",
            "base_resume_text": SAMPLE_RESUME,
            "tailored_resume_text": SAMPLE_RESUME + "\n补充：突出 API 设计经验。",
            "target_job_id": job_id,
            "source_analysis_record_id": analysis_id,
            "notes": "针对目标岗位定制",
        },
    )
    assert create_response.status_code == 200
    version = create_response.json()
    assert version["target_job_id"] == job_id
    assert version["source_analysis_record_id"] == analysis_id

    list_response = client.get("/resume-versions", params={"keyword": "api"})
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    detail_response = client.get(f"/resume-versions/{version['id']}")
    assert detail_response.status_code == 200
    assert detail_response.json()["base_resume_text"] == SAMPLE_RESUME

    application_response = client.post(
        "/applications",
        json={
            "job_id": job_id,
            "status": "interested",
            "resume_version_id": version["id"],
        },
    )
    assert application_response.status_code == 200
    application = application_response.json()
    assert application["resume_version_id"] == version["id"]
    assert application["resume_version_label"] == "v1-api-targeted"


def test_application_tracker_rejects_missing_job(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / "missing-application-job.sqlite3"))

    response = client.post("/applications", json={"job_id": 999})

    assert response.status_code == 404
    assert response.json()["detail"] == "job not found"
