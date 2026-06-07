from __future__ import annotations

import json
import sqlite3
from typing import Any

from pydantic import BaseModel

from app.schemas.application import ApplicationStatus
from app.schemas.report import FinalReport
from app.storage.database import init_database


def save_analysis_record(
    connection: sqlite3.Connection,
    report: FinalReport,
    *,
    application_id: int | None = None,
    workflow_steps: list[dict[str, Any]] | None = None,
) -> int:
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
        job_id = _get_or_create_job_posting(connection, report)
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
                application_id,
                match_report_id,
                project_challenge_id,
                optimization_json,
                markdown_report
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                resume_id,
                job_id,
                application_id,
                match_id,
                challenge_id,
                _model_to_json(report.optimization_result),
                report.markdown_report,
            ),
        )
        _insert_workflow_steps(connection, record_id=record_id, workflow_steps=workflow_steps or [])
    return record_id


def get_analysis_record(connection: sqlite3.Connection, record_id: int) -> dict[str, Any] | None:
    init_database(connection)
    row = connection.execute(
        """
        SELECT
            ar.id,
            ar.application_id,
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
    workflow_steps = list_workflow_steps(connection, record_id=record_id)
    return {
        "id": row["id"],
        "application_id": row["application_id"],
        "created_at": row["created_at"],
        "resume_profile": json.loads(row["profile_json"]),
        "job_analysis": json.loads(row["analysis_json"]),
        "match_report": json.loads(row["report_json"]),
        "optimization_result": json.loads(row["optimization_json"]),
        "project_challenge_report": json.loads(row["challenge_json"]),
        "markdown_report": row["markdown_report"],
        "workflow_steps": workflow_steps,
    }


def list_workflow_steps(connection: sqlite3.Connection, *, record_id: int) -> list[dict[str, Any]]:
    init_database(connection)
    rows = connection.execute(
        """
        SELECT
            workflow_run_id,
            agent_name,
            status,
            mode,
            summary,
            duration_ms,
            fallback_reason,
            guardrails_json
        FROM workflow_step_traces
        WHERE analysis_record_id = ?
        ORDER BY step_index ASC, id ASC
        """,
        (record_id,),
    ).fetchall()
    return [
        {
            "workflow_run_id": row["workflow_run_id"],
            "name": row["agent_name"],
            "status": row["status"],
            "mode": row["mode"],
            "summary": row["summary"],
            "duration_ms": float(row["duration_ms"] or 0.0),
            "fallback_reason": row["fallback_reason"],
            "guardrails": json.loads(row["guardrails_json"]),
        }
        for row in rows
    ]


def list_analysis_records(
    connection: sqlite3.Connection,
    *,
    limit: int = 20,
    keyword: str | None = None,
) -> list[dict[str, Any]]:
    init_database(connection)
    query = """
        SELECT
            ar.id,
            ar.created_at,
            jp.job_title,
            jp.company,
            mr.overall_score
        FROM analysis_records ar
        JOIN job_postings jp ON ar.job_posting_id = jp.id
        JOIN match_reports mr ON ar.match_report_id = mr.id
    """
    parameters: list[Any] = []
    if keyword:
        query += """
            WHERE jp.job_title LIKE ?
               OR jp.company LIKE ?
               OR jp.raw_jd LIKE ?
               OR jp.analysis_json LIKE ?
        """
        like_keyword = f"%{keyword}%"
        parameters.extend([like_keyword, like_keyword, like_keyword, like_keyword])
    query += " ORDER BY ar.created_at DESC, ar.id DESC LIMIT ?"
    parameters.append(_normalize_limit(limit))
    rows = connection.execute(query, tuple(parameters)).fetchall()
    return [
        {
            "id": row["id"],
            "created_at": row["created_at"],
            "job_title": row["job_title"],
            "company": row["company"],
            "overall_score": row["overall_score"],
        }
        for row in rows
    ]


def list_job_postings(
    connection: sqlite3.Connection,
    *,
    limit: int = 20,
    keyword: str | None = None,
) -> list[dict[str, Any]]:
    init_database(connection)
    query = """
        SELECT
            jp.id,
            jp.created_at,
            jp.job_title,
            jp.company,
            jp.analysis_json,
            COUNT(ar.id) AS analysis_count
        FROM job_postings jp
        LEFT JOIN analysis_records ar ON ar.job_posting_id = jp.id
    """
    parameters: list[Any] = []
    if keyword:
        query += """
            WHERE jp.job_title LIKE ?
               OR jp.company LIKE ?
               OR jp.raw_jd LIKE ?
               OR jp.analysis_json LIKE ?
        """
        like_keyword = f"%{keyword}%"
        parameters.extend([like_keyword, like_keyword, like_keyword, like_keyword])
    query += """
        GROUP BY jp.id
        ORDER BY jp.created_at DESC, jp.id DESC
        LIMIT ?
    """
    parameters.append(_normalize_limit(limit))
    rows = connection.execute(query, tuple(parameters)).fetchall()
    results: list[dict[str, Any]] = []
    for row in rows:
        analysis = json.loads(row["analysis_json"])
        keywords = analysis.get("keywords") or []
        results.append(
            {
                "id": row["id"],
                "created_at": row["created_at"],
                "job_title": row["job_title"],
                "company": row["company"],
                "keyword_text": ", ".join(keywords[:8]) if keywords else None,
                "analysis_count": row["analysis_count"],
            }
        )
    return results


def get_job_posting(connection: sqlite3.Connection, job_id: int) -> dict[str, Any] | None:
    init_database(connection)
    row = connection.execute(
        """
        SELECT
            jp.id,
            jp.created_at,
            jp.raw_jd,
            jp.analysis_json,
            COUNT(ar.id) AS analysis_count
        FROM job_postings jp
        LEFT JOIN analysis_records ar ON ar.job_posting_id = jp.id
        WHERE jp.id = ?
        GROUP BY jp.id
        """,
        (job_id,),
    ).fetchone()
    if row is None:
        return None
    return {
        "id": row["id"],
        "created_at": row["created_at"],
        "raw_jd": row["raw_jd"],
        "job_analysis": json.loads(row["analysis_json"]),
        "analysis_count": row["analysis_count"],
    }


def create_resume_version(
    connection: sqlite3.Connection,
    *,
    label: str,
    base_resume_text: str,
    tailored_resume_text: str | None = None,
    target_job_id: int | None = None,
    source_analysis_record_id: int | None = None,
    notes: str | None = None,
) -> dict[str, Any] | None:
    init_database(connection)
    if target_job_id is not None and not _job_exists(connection, target_job_id):
        return None
    if source_analysis_record_id is not None and not _analysis_record_exists(
        connection,
        source_analysis_record_id,
    ):
        return None

    with connection:
        resume_version_id = _insert_and_get_id(
            connection,
            """
            INSERT INTO resume_versions (
                label,
                base_resume_text,
                tailored_resume_text,
                target_job_posting_id,
                source_analysis_record_id,
                notes
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                label,
                base_resume_text,
                tailored_resume_text,
                target_job_id,
                source_analysis_record_id,
                notes,
            ),
        )
    return get_resume_version(connection, resume_version_id)


def list_resume_versions(
    connection: sqlite3.Connection,
    *,
    limit: int = 20,
    keyword: str | None = None,
    target_job_id: int | None = None,
) -> list[dict[str, Any]]:
    init_database(connection)
    query = """
        SELECT
            rv.id,
            rv.label,
            rv.target_job_posting_id,
            rv.source_analysis_record_id,
            rv.notes,
            rv.created_at,
            rv.updated_at,
            jp.job_title,
            jp.company
        FROM resume_versions rv
        LEFT JOIN job_postings jp ON rv.target_job_posting_id = jp.id
    """
    where_clauses: list[str] = []
    parameters: list[Any] = []
    if target_job_id is not None:
        where_clauses.append("rv.target_job_posting_id = ?")
        parameters.append(target_job_id)
    if keyword:
        where_clauses.append(
            """
            (
                rv.label LIKE ?
                OR rv.base_resume_text LIKE ?
                OR rv.tailored_resume_text LIKE ?
                OR rv.notes LIKE ?
                OR jp.job_title LIKE ?
                OR jp.company LIKE ?
            )
            """
        )
        like_keyword = f"%{keyword}%"
        parameters.extend(
            [
                like_keyword,
                like_keyword,
                like_keyword,
                like_keyword,
                like_keyword,
                like_keyword,
            ]
        )
    if where_clauses:
        query += " WHERE " + " AND ".join(where_clauses)
    query += " ORDER BY rv.updated_at DESC, rv.id DESC LIMIT ?"
    parameters.append(_normalize_limit(limit))
    rows = connection.execute(query, tuple(parameters)).fetchall()
    return [_resume_version_summary_row_to_dict(row) for row in rows]


def get_resume_version(
    connection: sqlite3.Connection,
    resume_version_id: int,
) -> dict[str, Any] | None:
    init_database(connection)
    row = connection.execute(
        """
        SELECT
            rv.id,
            rv.label,
            rv.base_resume_text,
            rv.tailored_resume_text,
            rv.target_job_posting_id,
            rv.source_analysis_record_id,
            rv.notes,
            rv.created_at,
            rv.updated_at,
            jp.job_title,
            jp.company
        FROM resume_versions rv
        LEFT JOIN job_postings jp ON rv.target_job_posting_id = jp.id
        WHERE rv.id = ?
        """,
        (resume_version_id,),
    ).fetchone()
    if row is None:
        return None
    return _resume_version_row_to_dict(row)


def upsert_application_record(
    connection: sqlite3.Connection,
    *,
    job_id: int,
    status: ApplicationStatus = "interested",
    notes: str | None = None,
    next_action: str | None = None,
    resume_version_id: int | None = None,
    resume_version_label: str | None = None,
) -> dict[str, Any] | None:
    init_database(connection)
    if not _job_exists(connection, job_id):
        return None
    if resume_version_id is not None and not _resume_version_exists(connection, resume_version_id):
        return None

    with connection:
        connection.execute(
            """
            INSERT INTO application_records (
                job_posting_id,
                status,
                notes,
                next_action,
                resume_version_id,
                resume_version_label
            )
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(job_posting_id) DO UPDATE SET
                status = excluded.status,
                notes = excluded.notes,
                next_action = excluded.next_action,
                resume_version_id = excluded.resume_version_id,
                resume_version_label = excluded.resume_version_label,
                updated_at = CURRENT_TIMESTAMP
            """,
            (job_id, status, notes, next_action, resume_version_id, resume_version_label),
        )
    return get_application_by_job_id(connection, job_id)


def update_application_record(
    connection: sqlite3.Connection,
    *,
    application_id: int,
    status: ApplicationStatus | None = None,
    notes: str | None = None,
    next_action: str | None = None,
    resume_version_id: int | None = None,
    resume_version_label: str | None = None,
) -> dict[str, Any] | None:
    init_database(connection)
    existing = get_application_record(connection, application_id)
    if existing is None:
        return None

    new_status = status if status is not None else existing["status"]
    new_notes = notes if notes is not None else existing["notes"]
    new_next_action = next_action if next_action is not None else existing["next_action"]
    new_resume_version_id = resume_version_id if resume_version_id is not None else existing["resume_version_id"]
    if new_resume_version_id is not None and not _resume_version_exists(connection, new_resume_version_id):
        return None
    new_resume_version_label = (
        resume_version_label if resume_version_label is not None else existing["resume_version_label"]
    )
    with connection:
        connection.execute(
            """
            UPDATE application_records
            SET
                status = ?,
                notes = ?,
                next_action = ?,
                resume_version_id = ?,
                resume_version_label = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                new_status,
                new_notes,
                new_next_action,
                new_resume_version_id,
                new_resume_version_label,
                application_id,
            ),
        )
    return get_application_record(connection, application_id)


def list_application_records(
    connection: sqlite3.Connection,
    *,
    limit: int = 20,
    status: str | None = None,
    keyword: str | None = None,
) -> list[dict[str, Any]]:
    init_database(connection)
    query = """
        SELECT
            app.id,
            app.job_posting_id,
            app.status,
            app.notes,
            app.next_action,
            app.resume_version_id,
            COALESCE(app.resume_version_label, rv.label) AS resume_version_label,
            app.created_at,
            app.updated_at,
            jp.job_title,
            jp.company,
            jp.raw_jd
        FROM application_records app
        JOIN job_postings jp ON app.job_posting_id = jp.id
        LEFT JOIN resume_versions rv ON app.resume_version_id = rv.id
    """
    where_clauses: list[str] = []
    parameters: list[Any] = []
    if status:
        where_clauses.append("app.status = ?")
        parameters.append(status)
    if keyword:
        where_clauses.append(
            """
            (
                jp.job_title LIKE ?
                OR jp.company LIKE ?
                OR jp.raw_jd LIKE ?
                OR app.notes LIKE ?
                OR app.next_action LIKE ?
                OR app.resume_version_label LIKE ?
                OR rv.label LIKE ?
            )
            """
        )
        like_keyword = f"%{keyword}%"
        parameters.extend(
            [
                like_keyword,
                like_keyword,
                like_keyword,
                like_keyword,
                like_keyword,
                like_keyword,
                like_keyword,
            ]
        )
    if where_clauses:
        query += " WHERE " + " AND ".join(where_clauses)
    query += " ORDER BY app.updated_at DESC, app.id DESC LIMIT ?"
    parameters.append(_normalize_limit(limit))
    rows = connection.execute(query, tuple(parameters)).fetchall()
    return [_application_row_to_dict(row) for row in rows]


def get_application_record(connection: sqlite3.Connection, application_id: int) -> dict[str, Any] | None:
    init_database(connection)
    row = connection.execute(
        """
        SELECT
            app.id,
            app.job_posting_id,
            app.status,
            app.notes,
            app.next_action,
            app.resume_version_id,
            COALESCE(app.resume_version_label, rv.label) AS resume_version_label,
            app.created_at,
            app.updated_at,
            jp.job_title,
            jp.company,
            jp.raw_jd
        FROM application_records app
        JOIN job_postings jp ON app.job_posting_id = jp.id
        LEFT JOIN resume_versions rv ON app.resume_version_id = rv.id
        WHERE app.id = ?
        """,
        (application_id,),
    ).fetchone()
    if row is None:
        return None
    return _application_row_to_dict(row)


def get_application_by_job_id(connection: sqlite3.Connection, job_id: int) -> dict[str, Any] | None:
    init_database(connection)
    row = connection.execute(
        """
        SELECT
            app.id,
            app.job_posting_id,
            app.status,
            app.notes,
            app.next_action,
            app.resume_version_id,
            COALESCE(app.resume_version_label, rv.label) AS resume_version_label,
            app.created_at,
            app.updated_at,
            jp.job_title,
            jp.company
        FROM application_records app
        JOIN job_postings jp ON app.job_posting_id = jp.id
        LEFT JOIN resume_versions rv ON app.resume_version_id = rv.id
        WHERE app.job_posting_id = ?
        """,
        (job_id,),
    ).fetchone()
    if row is None:
        return None
    return _application_row_to_dict(row)


def count_analysis_records(connection: sqlite3.Connection) -> int:
    init_database(connection)
    row = connection.execute("SELECT COUNT(*) AS count FROM analysis_records").fetchone()
    return int(row["count"])


def count_job_postings(connection: sqlite3.Connection) -> int:
    init_database(connection)
    row = connection.execute("SELECT COUNT(*) AS count FROM job_postings").fetchone()
    return int(row["count"])


def count_application_records(connection: sqlite3.Connection) -> int:
    init_database(connection)
    row = connection.execute("SELECT COUNT(*) AS count FROM application_records").fetchone()
    return int(row["count"])


def count_resume_versions(connection: sqlite3.Connection) -> int:
    init_database(connection)
    row = connection.execute("SELECT COUNT(*) AS count FROM resume_versions").fetchone()
    return int(row["count"])


def _get_or_create_job_posting(connection: sqlite3.Connection, report: FinalReport) -> int:
    existing = connection.execute(
        "SELECT id FROM job_postings WHERE raw_jd = ? ORDER BY id LIMIT 1",
        (report.job_analysis.raw_jd,),
    ).fetchone()
    if existing is not None:
        return int(existing["id"])
    return _insert_and_get_id(
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


def _insert_workflow_steps(
    connection: sqlite3.Connection,
    *,
    record_id: int,
    workflow_steps: list[dict[str, Any]],
) -> None:
    for index, step in enumerate(workflow_steps):
        connection.execute(
            """
            INSERT INTO workflow_step_traces (
                analysis_record_id,
                workflow_run_id,
                step_index,
                agent_name,
                status,
                mode,
                summary,
                duration_ms,
                fallback_reason,
                guardrails_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record_id,
                step.get("workflow_run_id"),
                index,
                step["name"],
                step["status"],
                step["mode"],
                step["summary"],
                float(step.get("duration_ms") or 0.0),
                step.get("fallback_reason"),
                json.dumps(step.get("guardrails") or [], ensure_ascii=False),
            ),
        )


def _job_exists(connection: sqlite3.Connection, job_id: int) -> bool:
    row = connection.execute("SELECT id FROM job_postings WHERE id = ?", (job_id,)).fetchone()
    return row is not None


def _analysis_record_exists(connection: sqlite3.Connection, record_id: int) -> bool:
    row = connection.execute("SELECT id FROM analysis_records WHERE id = ?", (record_id,)).fetchone()
    return row is not None


def _resume_version_exists(connection: sqlite3.Connection, resume_version_id: int) -> bool:
    row = connection.execute("SELECT id FROM resume_versions WHERE id = ?", (resume_version_id,)).fetchone()
    return row is not None


def _resume_version_summary_row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "label": row["label"],
        "target_job_id": row["target_job_posting_id"],
        "target_job_title": row["job_title"],
        "target_company": row["company"],
        "source_analysis_record_id": row["source_analysis_record_id"],
        "notes": row["notes"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _resume_version_row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    data = _resume_version_summary_row_to_dict(row)
    data.update(
        {
            "base_resume_text": row["base_resume_text"],
            "tailored_resume_text": row["tailored_resume_text"],
        }
    )
    return data


def _application_row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "job_id": row["job_posting_id"],
        "status": row["status"],
        "notes": row["notes"],
        "next_action": row["next_action"],
        "resume_version_id": row["resume_version_id"],
        "resume_version_label": row["resume_version_label"],
        "job_title": row["job_title"],
        "company": row["company"],
        "raw_jd": row["raw_jd"] if "raw_jd" in row.keys() else None,
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _insert_and_get_id(
    connection: sqlite3.Connection,
    sql: str,
    parameters: tuple[Any, ...],
) -> int:
    cursor = connection.execute(sql, parameters)
    return int(cursor.lastrowid)


def _model_to_json(model: BaseModel) -> str:
    return model.model_dump_json(ensure_ascii=False)


def _normalize_limit(limit: int) -> int:
    return max(1, min(limit, 100))
