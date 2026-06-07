from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.schemas.brief import JobBriefReport, JobRecommendationItem
from app.schemas.match import MatchReport
from app.schemas.search import SearchResultItem
from app.services.brief_run_storage_service import save_brief_run
from app.services.errors import JobAgentError
from app.services.job_import_candidate_service import (
    create_application_from_candidate,
    create_candidate_from_brief_run,
    get_candidate,
    list_candidates,
    update_candidate,
)
from app.storage.database import get_connection
from app.storage.repositories import count_application_records


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


def _prepare_run(tmp_path: Path, monkeypatch) -> tuple[Path, str]:
    database_path = tmp_path / "job-candidates.sqlite3"
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(database_path))
    run_id = save_brief_run(_build_report(), "resume text", database_path=database_path)
    return database_path, run_id


def test_create_candidate_from_brief_run_rank_1(tmp_path: Path, monkeypatch) -> None:
    _, run_id = _prepare_run(tmp_path, monkeypatch)

    candidate = create_candidate_from_brief_run(run_id, rank=1)

    assert candidate.source == "brief_run"
    assert candidate.source_run_id == run_id
    assert candidate.title == "AI Platform Engineer"
    assert candidate.status == "draft"
    assert candidate.jd_text is None
    assert candidate.jd_text_preview


def test_create_candidate_from_brief_run_item_id(tmp_path: Path, monkeypatch) -> None:
    database_path, run_id = _prepare_run(tmp_path, monkeypatch)
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    item_row = connection.execute(
        "SELECT id FROM brief_run_items WHERE run_id = ? ORDER BY id ASC LIMIT 1",
        (run_id,),
    ).fetchone()
    connection.close()

    candidate = create_candidate_from_brief_run(run_id, item_id=int(item_row["id"]))

    assert candidate.source_item_id == int(item_row["id"])
    assert candidate.title == "AI Platform Engineer"


def test_duplicate_source_run_id_and_source_url_returns_existing_candidate(tmp_path: Path, monkeypatch) -> None:
    _, run_id = _prepare_run(tmp_path, monkeypatch)

    first = create_candidate_from_brief_run(run_id, rank=1)
    second = create_candidate_from_brief_run(run_id, rank=1)

    assert first.candidate_id == second.candidate_id


def test_get_candidate_hides_full_jd_by_default_and_can_include_it(tmp_path: Path, monkeypatch) -> None:
    _, run_id = _prepare_run(tmp_path, monkeypatch)
    created = create_candidate_from_brief_run(run_id, rank=1)

    hidden = get_candidate(created.candidate_id)
    full = get_candidate(created.candidate_id, include_full_jd=True)

    assert hidden is not None
    assert full is not None
    assert hidden.jd_text is None
    assert full.jd_text


def test_list_candidates_filters_by_status_and_update_candidate_works(tmp_path: Path, monkeypatch) -> None:
    _, run_id = _prepare_run(tmp_path, monkeypatch)
    created = create_candidate_from_brief_run(run_id, rank=1)

    updated = update_candidate(
        created.candidate_id,
        status="ready_for_tracker",
        user_notes="Reviewed and ready",
    )
    filtered = list_candidates(status="ready_for_tracker", limit=20)

    assert updated.status == "ready_for_tracker"
    assert updated.user_notes == "Reviewed and ready"
    assert len(filtered) == 1
    assert filtered[0].candidate_id == created.candidate_id


def test_update_candidate_rejects_invalid_status(tmp_path: Path, monkeypatch) -> None:
    _, run_id = _prepare_run(tmp_path, monkeypatch)
    created = create_candidate_from_brief_run(run_id, rank=1)

    with pytest.raises(JobAgentError) as exc_info:
        update_candidate(created.candidate_id, status="not-valid")  # type: ignore[arg-type]

    assert exc_info.value.error_code == "job_import_candidate_status_invalid"


def test_create_candidate_rejects_missing_brief_run(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / "job-candidates.sqlite3"))

    with pytest.raises(JobAgentError) as exc_info:
        create_candidate_from_brief_run("missing-run", rank=1)

    assert exc_info.value.error_code == "brief_run_not_found"


def test_create_candidate_rejects_missing_brief_run_item(tmp_path: Path, monkeypatch) -> None:
    _, run_id = _prepare_run(tmp_path, monkeypatch)

    with pytest.raises(JobAgentError) as exc_info:
        create_candidate_from_brief_run(run_id, rank=99)

    assert exc_info.value.error_code == "brief_run_item_not_found"


def test_get_candidate_returns_none_for_missing_candidate(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / "job-candidates.sqlite3"))

    assert get_candidate("missing-candidate") is None


def test_create_application_from_candidate_creates_tracker_record(tmp_path: Path, monkeypatch) -> None:
    database_path, run_id = _prepare_run(tmp_path, monkeypatch)
    created = create_candidate_from_brief_run(run_id, rank=1)

    application, imported_candidate = create_application_from_candidate(
        created.candidate_id,
        status="interested",
        notes="Import into tracker",
        next_action="Tailor resume",
    )

    assert application["status"] == "interested"
    assert application["job_title"] == "AI Platform Engineer"
    assert application["company"] == "Example Tech"
    assert application["notes"] == "Import into tracker"
    assert imported_candidate.candidate_id == created.candidate_id
    assert imported_candidate.status == "imported"

    with get_connection(database_path) as connection:
        assert count_application_records(connection) == 1


def test_create_application_from_candidate_is_idempotent(tmp_path: Path, monkeypatch) -> None:
    database_path, run_id = _prepare_run(tmp_path, monkeypatch)
    created = create_candidate_from_brief_run(run_id, rank=1)

    first_application, first_candidate = create_application_from_candidate(
        created.candidate_id,
        status="interested",
        notes="First import",
    )
    second_application, second_candidate = create_application_from_candidate(
        created.candidate_id,
        status="applied",
        notes="Should not overwrite existing tracker record",
    )

    assert first_application["id"] == second_application["id"]
    assert second_application["status"] == "interested"
    assert second_application["notes"] == "First import"
    assert first_candidate.status == "imported"
    assert second_candidate.status == "imported"

    with get_connection(database_path) as connection:
        assert count_application_records(connection) == 1


def test_create_application_from_candidate_rejects_missing_candidate(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / "job-candidates.sqlite3"))

    with pytest.raises(JobAgentError) as exc_info:
        create_application_from_candidate("missing-candidate")

    assert exc_info.value.error_code == "job_import_candidate_not_found"
