from __future__ import annotations

from pathlib import Path

from app.services.application_service import save_application
from app.services.mock_pipeline import run_mock_pipeline
from app.services.resume_version_service import (
    list_saved_resume_versions,
    load_resume_version,
    save_resume_version,
)
from app.storage.database import get_connection
from app.storage.repositories import (
    count_resume_versions,
    list_job_postings,
    save_analysis_record,
)
from tests.test_mock_pipeline import SAMPLE_JD, SAMPLE_RESUME


def _saved_analysis_and_job(database_path: Path) -> tuple[int, int]:
    report = run_mock_pipeline(SAMPLE_RESUME, SAMPLE_JD)
    with get_connection(database_path) as connection:
        analysis_id = save_analysis_record(connection, report)
        job_id = int(list_job_postings(connection)[0]["id"])
    return analysis_id, job_id


def test_resume_version_create_list_and_load(tmp_path: Path) -> None:
    database_path = tmp_path / "resume-versions.sqlite3"
    analysis_id, job_id = _saved_analysis_and_job(database_path)

    created = save_resume_version(
        label="v1-fastapi-targeted",
        base_resume_text=SAMPLE_RESUME,
        tailored_resume_text=SAMPLE_RESUME + "\n补充：突出 FastAPI API 设计经验。",
        target_job_id=job_id,
        source_analysis_record_id=analysis_id,
        notes="针对 FastAPI 岗位定制",
        database_path=database_path,
    )
    versions = list_saved_resume_versions(keyword="FastAPI", database_path=database_path)
    loaded = load_resume_version(created["id"], database_path=database_path) if created else None

    assert created is not None
    assert created["target_job_id"] == job_id
    assert created["source_analysis_record_id"] == analysis_id
    assert len(versions) == 1
    assert loaded is not None
    assert loaded["base_resume_text"] == SAMPLE_RESUME
    assert "FastAPI" in (loaded["tailored_resume_text"] or "")

    with get_connection(database_path) as connection:
        assert count_resume_versions(connection) == 1


def test_resume_version_rejects_missing_linked_job(tmp_path: Path) -> None:
    database_path = tmp_path / "missing-linked-job.sqlite3"

    created = save_resume_version(
        label="v1-missing-job",
        base_resume_text=SAMPLE_RESUME,
        target_job_id=999,
        database_path=database_path,
    )

    assert created is None


def test_application_can_link_resume_version(tmp_path: Path) -> None:
    database_path = tmp_path / "application-version.sqlite3"
    _, job_id = _saved_analysis_and_job(database_path)
    version = save_resume_version(
        label="v1-application",
        base_resume_text=SAMPLE_RESUME,
        target_job_id=job_id,
        database_path=database_path,
    )
    assert version is not None

    application = save_application(
        job_id=job_id,
        status="interested",
        resume_version_id=version["id"],
        database_path=database_path,
    )

    assert application is not None
    assert application["resume_version_id"] == version["id"]
    assert application["resume_version_label"] == "v1-application"
