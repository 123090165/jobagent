from __future__ import annotations

from pathlib import Path

from app.services.mock_pipeline import run_mock_pipeline
from app.storage.database import get_connection, init_database
from app.storage.repositories import count_analysis_records, get_analysis_record, save_analysis_record
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
