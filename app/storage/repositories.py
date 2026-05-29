from __future__ import annotations

import json
import sqlite3
from typing import Any

from pydantic import BaseModel

from app.schemas.report import FinalReport
from app.storage.database import init_database


def save_analysis_record(connection: sqlite3.Connection, report: FinalReport) -> int:
    init_database(connection)
    with connection:
        resume_id = _insert_and_get_id(
            connection,
            """
            INSERT INTO resume_records (raw_text, profile_json)
            VALUES (?, ?)
            """,
            (
                report.resume_profile.raw_text,
                _model_to_json(report.resume_profile),
            ),
        )
        job_id = _insert_and_get_id(
            connection,
            """
            INSERT INTO job_postings (raw_jd, analysis_json, job_title, company)
            VALUES (?, ?, ?, ?)
            """,
            (
                report.job_analysis.raw_jd,
                _model_to_json(report.job_analysis),
                report.job_analysis.job_title,
                report.job_analysis.company,
            ),
        )
        match_id = _insert_and_get_id(
            connection,
            """
            INSERT INTO match_reports (
                resume_record_id,
                job_posting_id,
                report_json,
                overall_score
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                resume_id,
                job_id,
                _model_to_json(report.match_report),
                report.match_report.overall_score,
            ),
        )
        challenge_id = _insert_and_get_id(
            connection,
            """
            INSERT INTO project_challenges (match_report_id, challenge_json)
            VALUES (?, ?)
            """,
            (
                match_id,
                _model_to_json(report.project_challenge_report),
            ),
        )
        record_id = _insert_and_get_id(
            connection,
            """
            INSERT INTO analysis_records (
                resume_record_id,
                job_posting_id,
                match_report_id,
                project_challenge_id,
                optimization_json,
                markdown_report
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                resume_id,
                job_id,
                match_id,
                challenge_id,
                _model_to_json(report.optimization_result),
                report.markdown_report,
            ),
        )
    return record_id


def get_analysis_record(connection: sqlite3.Connection, record_id: int) -> dict[str, Any] | None:
    init_database(connection)
    row = connection.execute(
        """
        SELECT
            ar.id,
            ar.created_at,
            ar.markdown_report,
            rr.profile_json,
            jp.analysis_json,
            mr.report_json,
            ar.optimization_json,
            pc.challenge_json
        FROM analysis_records ar
        JOIN resume_records rr ON ar.resume_record_id = rr.id
        JOIN job_postings jp ON ar.job_posting_id = jp.id
        JOIN match_reports mr ON ar.match_report_id = mr.id
        JOIN project_challenges pc ON ar.project_challenge_id = pc.id
        WHERE ar.id = ?
        """,
        (record_id,),
    ).fetchone()
    if row is None:
        return None
    return {
        "id": row["id"],
        "created_at": row["created_at"],
        "resume_profile": json.loads(row["profile_json"]),
        "job_analysis": json.loads(row["analysis_json"]),
        "match_report": json.loads(row["report_json"]),
        "optimization_result": json.loads(row["optimization_json"]),
        "project_challenge_report": json.loads(row["challenge_json"]),
        "markdown_report": row["markdown_report"],
    }


def count_analysis_records(connection: sqlite3.Connection) -> int:
    init_database(connection)
    row = connection.execute("SELECT COUNT(*) AS count FROM analysis_records").fetchone()
    return int(row["count"])


def _insert_and_get_id(
    connection: sqlite3.Connection,
    sql: str,
    parameters: tuple[Any, ...],
) -> int:
    cursor = connection.execute(sql, parameters)
    return int(cursor.lastrowid)


def _model_to_json(model: BaseModel) -> str:
    return model.model_dump_json(ensure_ascii=False)
