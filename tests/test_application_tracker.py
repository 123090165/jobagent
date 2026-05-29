from __future__ import annotations

from pathlib import Path

from app.services.application_service import (
    list_applications,
    load_application,
    save_application,
    update_application,
)
from app.services.mock_pipeline import run_mock_pipeline
from app.storage.database import get_connection
from app.storage.repositories import count_application_records, list_job_postings, save_analysis_record
from tests.test_mock_pipeline import SAMPLE_JD, SAMPLE_RESUME


def _saved_job_id(database_path: Path) -> int:
    report = run_mock_pipeline(SAMPLE_RESUME, SAMPLE_JD)
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
    assert loaded["next_action"] == "等待反馈"
    assert len(applications) == 1

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
