from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.main import app
from app.schemas.brief import JobBriefReport, JobRecommendationItem
from app.schemas.match import MatchReport
from app.schemas.search import SearchResultItem
from app.services.brief_run_storage_service import save_brief_run

client = TestClient(app)


def _build_report() -> JobBriefReport:
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


def _prepare_run(tmp_path: Path, monkeypatch) -> str:
    database_path = tmp_path / "job-candidate-routes.sqlite3"
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(database_path))
    return save_brief_run(_build_report(), "resume text", database_path=database_path)


def test_post_job_candidates_from_brief_run_works(tmp_path: Path, monkeypatch) -> None:
    run_id = _prepare_run(tmp_path, monkeypatch)

    response = client.post(
        "/job-candidates/from-brief-run",
        json={"run_id": run_id, "rank": 1},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["candidate"]["source"] == "brief_run"
    assert payload["candidate"]["source_run_id"] == run_id
    assert payload["candidate"]["jd_text"] is None


def test_get_job_candidate_supports_include_full_jd(tmp_path: Path, monkeypatch) -> None:
    run_id = _prepare_run(tmp_path, monkeypatch)
    create_response = client.post(
        "/job-candidates/from-brief-run",
        json={"run_id": run_id, "rank": 1},
    )
    candidate_id = create_response.json()["candidate"]["candidate_id"]

    hidden = client.get(f"/job-candidates/{candidate_id}")
    full = client.get(f"/job-candidates/{candidate_id}?include_full_jd=true")

    assert hidden.status_code == 200
    assert full.status_code == 200
    assert hidden.json()["candidate"]["jd_text"] is None
    assert full.json()["candidate"]["jd_text"]


def test_list_job_candidates_and_patch_work(tmp_path: Path, monkeypatch) -> None:
    run_id = _prepare_run(tmp_path, monkeypatch)
    create_response = client.post(
        "/job-candidates/from-brief-run",
        json={"run_id": run_id, "rank": 1},
    )
    candidate_id = create_response.json()["candidate"]["candidate_id"]

    patch_response = client.patch(
        f"/job-candidates/{candidate_id}",
        json={"status": "reviewed", "user_notes": "Looks promising"},
    )
    list_response = client.get("/job-candidates?status=reviewed&limit=20")

    assert patch_response.status_code == 200
    assert patch_response.json()["candidate"]["status"] == "reviewed"
    assert patch_response.json()["candidate"]["user_notes"] == "Looks promising"
    assert list_response.status_code == 200
    assert list_response.json()["candidates"][0]["candidate_id"] == candidate_id


def test_patch_job_candidate_rejects_invalid_status_with_error_code(tmp_path: Path, monkeypatch) -> None:
    run_id = _prepare_run(tmp_path, monkeypatch)
    create_response = client.post(
        "/job-candidates/from-brief-run",
        json={"run_id": run_id, "rank": 1},
    )
    candidate_id = create_response.json()["candidate"]["candidate_id"]

    response = client.patch(
        f"/job-candidates/{candidate_id}",
        json={"status": "not-valid"},
    )

    assert response.status_code == 400
    assert response.json()["error_code"] == "job_import_candidate_status_invalid"


def test_job_candidate_routes_return_not_found_errors(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / "job-candidate-routes.sqlite3"))

    create_response = client.post(
        "/job-candidates/from-brief-run",
        json={"run_id": "missing-run", "rank": 1},
    )
    get_response = client.get("/job-candidates/missing-candidate")

    assert create_response.status_code == 404
    assert create_response.json()["error_code"] == "brief_run_not_found"
    assert get_response.status_code == 404
    assert get_response.json()["error_code"] == "job_import_candidate_not_found"
