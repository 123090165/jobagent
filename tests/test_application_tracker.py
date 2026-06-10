from __future__ import annotations

from pathlib import Path

from app.services.application_service import (
    analyze_application,
    list_applications,
    load_application,
    save_application,
    update_application,
)
from app.services.mock_pipeline import run_mock_pipeline
from app.services.storage_service import load_analysis_record
from app.storage.database import get_connection
from app.storage.repositories import count_application_records, list_job_postings, save_analysis_record
from tests.test_mock_pipeline import SAMPLE_JD, SAMPLE_RESUME


def _saved_job_id(database_path: Path, jd_text: str = SAMPLE_JD) -> int:
    report = run_mock_pipeline(SAMPLE_RESUME, jd_text)
    with get_connection(database_path) as connection:
        save_analysis_record(connection, report)
        jobs = list_job_postings(connection)
    return int(jobs[0]["id"])


def test_application_tracker_create_update_and_list(tmp_path: Path) -> None:
    database_path = tmp_path / "tracker.sqlite3"
    job_id = _saved_job_id(database_path)

    created = save_application(
        job_id=job_id,
        status="interested",
        notes="值得关注",
        next_action="定制简历",
        database_path=database_path,
    )
    assert created is not None
    assert created["status"] == "interested"
    assert created["job_id"] == job_id
    assert created["analysis_summary"]["analysis_count"] == 0
    assert created["analysis_summary"]["has_analysis"] is False
    assert created["analysis_summary"]["latest_analysis_record_id"] is None
    assert created["analysis_summary"]["last_match_score"] is None

    updated = update_application(
        application_id=created["id"],
        status="applied",
        next_action="等待反馈",
        database_path=database_path,
    )
    loaded = load_application(created["id"], database_path=database_path)
    applications = list_applications(status="applied", database_path=database_path)

    assert updated is not None
    assert loaded is not None
    assert loaded["status"] == "applied"
    assert loaded["analysis_summary"]["has_analysis"] is False
    assert loaded["next_action"] == "等待反馈"
    assert len(applications) == 1
    assert applications[0]["analysis_summary"]["analysis_count"] == 0

    with get_connection(database_path) as connection:
        assert count_application_records(connection) == 1


def test_application_tracker_upserts_by_job_id(tmp_path: Path) -> None:
    database_path = tmp_path / "tracker.sqlite3"
    job_id = _saved_job_id(database_path)

    first = save_application(job_id=job_id, status="interested", database_path=database_path)
    second = save_application(job_id=job_id, status="interviewing", database_path=database_path)

    assert first is not None
    assert second is not None
    assert first["id"] == second["id"]
    assert second["status"] == "interviewing"

    with get_connection(database_path) as connection:
        assert count_application_records(connection) == 1


def test_application_tracker_returns_none_for_missing_job(tmp_path: Path) -> None:
    database_path = tmp_path / "tracker.sqlite3"

    created = save_application(job_id=999, database_path=database_path)

    assert created is None


def test_application_tracker_can_run_analysis_and_link_record(tmp_path: Path) -> None:
    database_path = tmp_path / "tracker.sqlite3"
    job_id = _saved_job_id(database_path)
    application = save_application(job_id=job_id, status="interested", database_path=database_path)

    assert application is not None

    result = analyze_application(
        application["id"],
        resume_text=SAMPLE_RESUME,
        database_path=database_path,
    )
    record = load_analysis_record(result["record_id"], database_path=database_path)

    assert result["application_id"] == application["id"]
    assert result["record_id"] > 0
    assert result["application"]["analysis_summary"]["has_analysis"] is True
    assert result["application"]["analysis_summary"]["analysis_count"] == 1
    assert result["application"]["analysis_summary"]["latest_analysis_record_id"] == result["record_id"]
    assert record is not None
    assert record["application_id"] == application["id"]


def test_application_tracker_list_summaries_for_mixed_analysis_state(tmp_path: Path) -> None:
    database_path = tmp_path / "tracker.sqlite3"
    analyzed_job_id = _saved_job_id(database_path, SAMPLE_JD)
    pending_job_id = _saved_job_id(database_path, SAMPLE_JD + "\nExtra responsibility: API observability.")
    analyzed = save_application(
        job_id=analyzed_job_id,
        status="interested",
        database_path=database_path,
    )
    pending = save_application(
        job_id=pending_job_id,
        status="interested",
        database_path=database_path,
    )

    assert analyzed is not None
    assert pending is not None

    analyze_application(analyzed["id"], resume_text=SAMPLE_RESUME, database_path=database_path)
    applications = list_applications(database_path=database_path)
    summaries = {application["id"]: application["analysis_summary"] for application in applications}

    assert summaries[analyzed["id"]]["has_analysis"] is True
    assert summaries[analyzed["id"]]["analysis_count"] >= 1
    assert summaries[pending["id"]]["has_analysis"] is False
    assert summaries[pending["id"]]["analysis_count"] == 0


def test_application_tracker_summary_uses_latest_analysis_record(tmp_path: Path) -> None:
    database_path = tmp_path / "tracker.sqlite3"
    job_id = _saved_job_id(database_path)
    application = save_application(job_id=job_id, status="interested", database_path=database_path)

    assert application is not None

    first = analyze_application(application["id"], resume_text=SAMPLE_RESUME, database_path=database_path)
    second = analyze_application(application["id"], resume_text=SAMPLE_RESUME, database_path=database_path)
    loaded = load_application(application["id"], database_path=database_path)

    assert loaded is not None
    summary = loaded["analysis_summary"]
    assert summary["has_analysis"] is True
    assert summary["analysis_count"] == 2
    assert summary["latest_analysis_record_id"] == second["record_id"]
    assert summary["latest_analysis_record_id"] > first["record_id"]
    assert summary["last_match_score"] is None or isinstance(summary["last_match_score"], (int, float))
    assert summary["last_analysis_quality"] is None or summary["last_analysis_quality"] in {
        "strong",
        "medium",
        "limited",
        "weak",
    }
