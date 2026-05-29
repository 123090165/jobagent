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


def test_full_analysis_endpoint_rejects_empty_resume() -> None:
    response = client.post(
        "/analyze/full",
        json={"resume_text": "", "jd_text": SAMPLE_JD},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "resume_text cannot be empty"


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
