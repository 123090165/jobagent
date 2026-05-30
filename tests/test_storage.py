from __future__ import annotations

from pathlib import Path

from app.services.mock_pipeline import run_mock_pipeline
from app.services.storage_service import (
    list_saved_analysis_records,
    list_saved_job_postings,
    save_final_report,
)
from app.storage.database import get_connection, init_database
from app.storage.repositories import (
    count_analysis_records,
    count_job_postings,
    get_analysis_record,
    get_job_posting,
    list_analysis_records,
    list_job_postings,
    list_workflow_steps,
    save_analysis_record,
)
from app.workflows.job_analysis_workflow import run_job_analysis_workflow
from tests.test_mock_pipeline import SAMPLE_JD, SAMPLE_RESUME


def test_save_and_load_analysis_record(tmp_path: Path) -> None:
    database_path = tmp_path / "jobagent-test.sqlite3"
    report = run_mock_pipeline(SAMPLE_RESUME, SAMPLE_JD)

    with get_connection(database_path) as connection:
        init_database(connection)
        record_id = save_analysis_record(connection, report)
        stored = get_analysis_record(connection, record_id)

        assert count_analysis_records(connection) == 1

    assert stored is not None
    assert stored["id"] == record_id
    assert stored["resume_profile"]["raw_text"] == report.resume_profile.raw_text
    assert stored["job_analysis"]["raw_jd"] == report.job_analysis.raw_jd
    assert stored["match_report"]["overall_score"] == report.match_report.overall_score
    assert "markdown_report" in stored


def test_save_analysis_record_deduplicates_same_jd(tmp_path: Path) -> None:
    database_path = tmp_path / "jobagent-test.sqlite3"
    first_report = run_mock_pipeline(SAMPLE_RESUME, SAMPLE_JD)
    second_report = run_mock_pipeline(SAMPLE_RESUME + "\n补充：Docker", SAMPLE_JD)

    with get_connection(database_path) as connection:
        first_record_id = save_analysis_record(connection, first_report)
        second_record_id = save_analysis_record(connection, second_report)
        records = list_analysis_records(connection)
        jobs = list_job_postings(connection)

        assert first_record_id != second_record_id
        assert count_analysis_records(connection) == 2
        assert count_job_postings(connection) == 1

    assert len(records) == 2
    assert len(jobs) == 1
    assert jobs[0]["analysis_count"] == 2


def test_list_and_get_job_posting(tmp_path: Path) -> None:
    database_path = tmp_path / "jobagent-test.sqlite3"
    report = run_mock_pipeline(SAMPLE_RESUME, SAMPLE_JD)

    with get_connection(database_path) as connection:
        save_analysis_record(connection, report)
        jobs = list_job_postings(connection, keyword="FastAPI")
        job = get_job_posting(connection, jobs[0]["id"])

    assert len(jobs) == 1
    assert jobs[0]["keyword_text"]
    assert job is not None
    assert job["raw_jd"] == report.job_analysis.raw_jd
    assert job["analysis_count"] == 1


def test_storage_service_closes_database_connections(tmp_path: Path) -> None:
    database_path = tmp_path / "service-close.sqlite3"
    report = run_mock_pipeline(SAMPLE_RESUME, SAMPLE_JD)

    record_id = save_final_report(report, database_path=database_path)
    records = list_saved_analysis_records(database_path=database_path)
    jobs = list_saved_job_postings(database_path=database_path)

    assert record_id == 1
    assert len(records) == 1
    assert len(jobs) == 1
    database_path.unlink()


def test_save_analysis_record_with_workflow_steps(tmp_path: Path) -> None:
    database_path = tmp_path / "workflow-trace.sqlite3"
    workflow_result = run_job_analysis_workflow(SAMPLE_RESUME, SAMPLE_JD)
    workflow_steps = [step.model_dump() for step in workflow_result.state.steps]

    with get_connection(database_path) as connection:
        record_id = save_analysis_record(
            connection,
            workflow_result.final_report,
            workflow_steps=workflow_steps,
        )
        stored = get_analysis_record(connection, record_id)
        steps = list_workflow_steps(connection, record_id=record_id)

    assert stored is not None
    assert len(stored["workflow_steps"]) == 6
    assert len(steps) == 6
    assert steps[0]["name"] == "ResumeParseAgent"
    assert steps[0]["mode"] == "mock"
    assert steps[0]["guardrails"]
