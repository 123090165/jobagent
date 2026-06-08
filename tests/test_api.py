from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api import routes_analyze, routes_jobs
from app.main import app
from app.schemas.brief import JobBriefReport, JobRecommendationItem
from app.schemas.match import MatchReport
from app.schemas.search import SearchResultItem
from app.services.application_service import save_application
from app.services.brief_run_storage_service import save_brief_run
from app.services.jd_url_service import JDUrlImportError
from app.services.storage_service import load_analysis_record
from app.storage.database import get_connection, init_database
from app.workflows.job_analysis_workflow import WorkflowStepTrace, run_job_analysis_workflow
from tests.test_mock_pipeline import SAMPLE_JD, SAMPLE_RESUME

client = TestClient(app)


def _build_fake_langgraph_workflow_result():
    baseline = run_job_analysis_workflow(SAMPLE_RESUME, SAMPLE_JD)
    workflow_run_id = baseline.state.workflow_run_id
    router_step = WorkflowStepTrace(
        workflow_run_id=workflow_run_id,
        name="MatchScoreRouter",
        status="completed",
        mode="mock",
        summary="Route to resume optimization and project challenge path.",
        duration_ms=0.1,
        guardrails=[
            "Route by deterministic score threshold only.",
            "Do not claim LLM optimization ran when the workflow intentionally skipped it.",
        ],
    )
    steps = [
        *baseline.state.steps[:3],
        router_step,
        *baseline.state.steps[3:],
    ]
    return SimpleNamespace(
        final_report=baseline.final_report,
        state=SimpleNamespace(steps=steps),
    )


def _build_brief_report_for_candidate_flow() -> JobBriefReport:
    job = SearchResultItem(
        title="AI Platform Engineer",
        company="Example Tech",
        location="Shenzhen",
        url="https://example.com/jobs/ai-platform-engineer",
        snippet="Build AI platform APIs.",
        source="local_db",
        retrieved_at=datetime(2026, 6, 3, tzinfo=timezone.utc),
        responsibilities=["Build AI platform APIs."],
        requirements=["Python and FastAPI."],
        skills=["Python", "FastAPI", "PyTorch"],
        jd_text="Responsibilities: Build AI platform APIs.\nRequirements: Python and FastAPI.\n" + ("detail " * 120),
        is_full_jd=True,
        confidence=0.91,
        quality_label="full_jd",
        warnings=["needs_manual_review"],
        external_links=["https://example.com/jobs/ai-platform-engineer"],
    )
    match_report = MatchReport(
        overall_score=87.0,
        skill_score=88.0,
        project_score=84.0,
        experience_score=82.0,
        keyword_coverage=85.0,
        matched_points=["Strong backend alignment"],
        missing_points=["Need more production ML examples"],
        risks=["Domain depth is moderate"],
        evidence=["Built FastAPI workflow demos"],
        apply_recommendation="Apply after highlighting platform projects.",
        short_term_suggestions=["Move FastAPI evidence higher"],
        long_term_suggestions=["Add more production ML case studies"],
    )
    item = JobRecommendationItem(
        rank=1,
        job=job,
        match_report=match_report,
        fit_score=87.0,
        advice="Apply after highlighting platform projects.",
        scoring_quality="full_jd",
        fit_reasons=["Strong backend alignment"],
        risk_points=["Domain depth is moderate", "Need more production ML examples"],
    )
    return JobBriefReport(
        query="AI platform Shenzhen",
        provider="local_db",
        total_jobs=1,
        recommended_jobs=[item],
        top_skills=["Python", "FastAPI", "PyTorch"],
        market_summary="Found 1 local job.",
        application_strategy=["Prioritize the top role first."],
        scoring_quality_summary="Scoring quality mix: full_jd=1, partial_jd=0, external_link_only=0, snippet_only=0.",
    )


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
    assert payload["match_report"]["requirement_matches"]
    assert payload["optimization_result"]["rewrite_suggestions"]
    assert payload["project_challenge_report"]["grounded_questions"]
    assert "JD-Resume Evidence Chain" in payload["markdown_report"]
    assert "### Requirement:" in payload["markdown_report"]
    assert "- Rewrite suggestion:" in payload["markdown_report"]
    assert "- Interview challenge:" in payload["markdown_report"]
    assert "Match Overview" in payload["markdown_report"]
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


def test_full_analysis_endpoint_defaults_to_python_workflow(monkeypatch) -> None:
    calls = {"default": 0, "langgraph": 0}
    baseline = run_job_analysis_workflow(SAMPLE_RESUME, SAMPLE_JD)

    def fake_default_workflow(**kwargs):
        calls["default"] += 1
        return baseline

    def fake_langgraph_workflow(**kwargs):
        calls["langgraph"] += 1
        raise AssertionError("langgraph workflow should not be called by default")

    monkeypatch.setattr(routes_analyze, "run_job_analysis_workflow", fake_default_workflow)
    monkeypatch.setattr(
        routes_analyze,
        "run_langgraph_job_analysis_workflow",
        fake_langgraph_workflow,
    )

    response = client.post(
        "/analyze/full",
        json={"resume_text": SAMPLE_RESUME, "jd_text": SAMPLE_JD},
    )

    assert response.status_code == 200
    assert calls == {"default": 1, "langgraph": 0}


def test_full_analysis_endpoint_can_use_langgraph_workflow(monkeypatch) -> None:
    fake_result = _build_fake_langgraph_workflow_result()

    def fake_langgraph_workflow(**kwargs):
        return fake_result

    monkeypatch.setattr(
        routes_analyze,
        "run_langgraph_job_analysis_workflow",
        fake_langgraph_workflow,
    )

    response = client.post(
        "/analyze/full",
        json={
            "resume_text": SAMPLE_RESUME,
            "jd_text": SAMPLE_JD,
            "use_langgraph_workflow": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["workflow_steps"]
    assert any(step["name"] == "MatchScoreRouter" for step in payload["workflow_steps"])


def test_full_analysis_can_save_langgraph_record(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / "langgraph-api-test.sqlite3"))
    fake_result = _build_fake_langgraph_workflow_result()

    def fake_langgraph_workflow(**kwargs):
        return fake_result

    monkeypatch.setattr(
        routes_analyze,
        "run_langgraph_job_analysis_workflow",
        fake_langgraph_workflow,
    )

    response = client.post(
        "/analyze/full",
        json={
            "resume_text": SAMPLE_RESUME,
            "jd_text": SAMPLE_JD,
            "use_langgraph_workflow": True,
            "save_result": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["record_id"] is not None
    assert any(step["name"] == "MatchScoreRouter" for step in payload["workflow_steps"])

    record_response = client.get(f"/records/{payload['record_id']}")
    assert record_response.status_code == 200
    record = record_response.json()
    assert any(step["name"] == "MatchScoreRouter" for step in record["workflow_steps"])


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
    assert "JD-Resume Evidence Chain" in report_response.json()["markdown_report"]
    assert "- Rewrite suggestion:" in report_response.json()["markdown_report"]
    assert "Project Challenge Questions" in report_response.json()["markdown_report"]


def test_import_jd_url_endpoint_returns_extracted_text(monkeypatch) -> None:
    monkeypatch.setattr(
        routes_jobs,
        "import_jd_from_url",
        lambda url: "Python backend role. " * 8,
    )

    response = client.post(
        "/jobs/import-url",
        json={"url": "https://example.com/job"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["url"] == "https://example.com/job"
    assert "Python backend role." in payload["extracted_text"]
    assert payload["warning"] is None


def test_import_jd_url_endpoint_returns_error_code(monkeypatch) -> None:
    def fake_import(url: str) -> str:
        raise JDUrlImportError(
            "Failed to fetch JD URL. Please paste the JD manually.",
            "jd_url_fetch_failed",
        )

    monkeypatch.setattr(routes_jobs, "import_jd_from_url", fake_import)

    response = client.post(
        "/jobs/import-url",
        json={"url": "https://example.com/job"},
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["detail"] == "Failed to fetch JD URL. Please paste the JD manually."
    assert payload["error_code"] == "jd_url_fetch_failed"


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


def test_candidate_can_create_application_via_api(tmp_path, monkeypatch) -> None:
    database_path = tmp_path / "candidate-to-tracker-api.sqlite3"
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(database_path))
    run_id = save_brief_run(_build_brief_report_for_candidate_flow(), "resume text", database_path=database_path)

    candidate_response = client.post(
        "/job-candidates/from-brief-run",
        json={"run_id": run_id, "rank": 1},
    )
    assert candidate_response.status_code == 200
    candidate_id = candidate_response.json()["candidate"]["candidate_id"]

    create_application_response = client.post(
        f"/job-candidates/{candidate_id}/create-application",
        json={
            "status": "interested",
            "notes": "Import candidate into tracker",
            "next_action": "Tailor resume",
        },
    )
    assert create_application_response.status_code == 200
    payload = create_application_response.json()
    assert payload["candidate"]["status"] == "imported"
    assert payload["application"]["status"] == "interested"
    assert payload["application"]["job_title"] == "AI Platform Engineer"

    application_id = payload["application"]["id"]
    detail_response = client.get(f"/applications/{application_id}")
    assert detail_response.status_code == 200
    assert detail_response.json()["job_title"] == "AI Platform Engineer"


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


def test_application_analyze_api_flow(tmp_path, monkeypatch) -> None:
    database_path = tmp_path / "application-analyze.sqlite3"
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(database_path))

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

    application_response = client.post(
        "/applications",
        json={
            "job_id": job_id,
            "status": "interested",
            "notes": "Focus on backend API depth.",
        },
    )
    assert application_response.status_code == 200
    application = application_response.json()

    analyze_response = client.post(
        f"/applications/{application['id']}/analyze",
        json={"resume_text": SAMPLE_RESUME, "mode": "mock"},
    )
    assert analyze_response.status_code == 200
    payload = analyze_response.json()

    assert payload["application_id"] == application["id"]
    assert payload["application"]["id"] == application["id"]
    assert payload["record_id"] > 0
    assert payload["match_report"]["overall_score"] > 0

    record = load_analysis_record(payload["record_id"], database_path=database_path)
    assert record is not None
    assert record["application_id"] == application["id"]


def test_application_analyze_returns_404_for_missing_application(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / "missing-application-analyze.sqlite3"))

    response = client.post(
        "/applications/999/analyze",
        json={"resume_text": SAMPLE_RESUME, "mode": "mock"},
    )

    assert response.status_code == 404
    payload = response.json()
    assert payload["detail"] == "application not found"
    assert payload["error_code"] == "application_not_found"


def test_application_analyze_returns_error_when_job_description_missing(tmp_path, monkeypatch) -> None:
    database_path = tmp_path / "missing-jd.sqlite3"
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(database_path))

    baseline = run_job_analysis_workflow(SAMPLE_RESUME, SAMPLE_JD)
    with get_connection(database_path) as connection:
        init_database(connection)
        connection.execute(
            """
            INSERT INTO job_postings (raw_jd, analysis_json, job_title, company)
            VALUES (?, ?, ?, ?)
            """,
            (
                "   ",
                baseline.final_report.job_analysis.model_dump_json(),
                "Backend Engineer",
                "Example Co",
            ),
        )
        job_id = int(connection.execute("SELECT last_insert_rowid() AS id").fetchone()["id"])

    application = save_application(job_id=job_id, status="interested", database_path=database_path)
    assert application is not None

    response = client.post(
        f"/applications/{application['id']}/analyze",
        json={"resume_text": SAMPLE_RESUME, "mode": "mock"},
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["detail"] == "application job description is missing"
    assert payload["error_code"] == "application_job_description_missing"
