from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.schemas.application import ApplicationStatus
from app.schemas.job import JobAnalysis
from app.schemas.job_import_candidate import JobImportCandidate, JobImportCandidateStatus
from app.services.brief_run_storage_service import JD_TEXT_PREVIEW_MAX_CHARS, ensure_brief_run_tables
from app.services.errors import JobAgentError
from app.storage.database import get_connection, init_database
from app.storage.repositories import get_application_record, upsert_application_record

VALID_STATUSES: set[str] = {
    "draft",
    "reviewed",
    "ready_for_tracker",
    "ready_for_analysis",
    "imported",
    "rejected",
}


def ensure_job_import_candidates_table(*, database_path: str | Path | None = None) -> None:
    connection = get_connection(database_path)
    try:
        _ensure_job_import_candidates_table(connection)
    finally:
        connection.close()


def create_candidate_from_brief_run(
    run_id: str,
    item_id: int | None = None,
    rank: int | None = None,
    *,
    database_path: str | Path | None = None,
) -> JobImportCandidate:
    connection = get_connection(database_path)
    try:
        ensure_brief_run_tables(database_path=database_path)
        _ensure_job_import_candidates_table(connection)
        return _create_candidate_from_brief_run(connection, run_id=run_id, item_id=item_id, rank=rank)
    finally:
        connection.close()


def get_candidate(
    candidate_id: str,
    include_full_jd: bool = False,
    *,
    database_path: str | Path | None = None,
) -> JobImportCandidate | None:
    connection = get_connection(database_path)
    try:
        _ensure_job_import_candidates_table(connection)
        row = connection.execute(
            "SELECT * FROM job_import_candidates WHERE candidate_id = ?",
            (candidate_id,),
        ).fetchone()
        if row is None:
            return None
        return sanitize_candidate_for_response(_row_to_candidate(row), include_full_jd=include_full_jd)
    finally:
        connection.close()


def list_candidates(
    status: str | None = None,
    limit: int = 20,
    *,
    database_path: str | Path | None = None,
) -> list[JobImportCandidate]:
    connection = get_connection(database_path)
    try:
        _ensure_job_import_candidates_table(connection)
        normalized_limit = _normalize_limit(limit)
        normalized_status = _normalize_status(status) if status is not None else None
        query = """
            SELECT *
            FROM job_import_candidates
        """
        parameters: list[Any] = []
        if normalized_status is not None:
            query += " WHERE status = ?"
            parameters.append(normalized_status)
        query += " ORDER BY created_at DESC, id DESC LIMIT ?"
        parameters.append(normalized_limit)
        rows = connection.execute(query, tuple(parameters)).fetchall()
        return [sanitize_candidate_for_response(_row_to_candidate(row)) for row in rows]
    finally:
        connection.close()


def update_candidate(
    candidate_id: str,
    *,
    title: str | None = None,
    company: str | None = None,
    location: str | None = None,
    job_type: str | None = None,
    education: str | None = None,
    deadline: str | None = None,
    status: JobImportCandidateStatus | None = None,
    user_notes: str | None = None,
    database_path: str | Path | None = None,
) -> JobImportCandidate:
    connection = get_connection(database_path)
    try:
        _ensure_job_import_candidates_table(connection)
        existing = connection.execute(
            "SELECT * FROM job_import_candidates WHERE candidate_id = ?",
            (candidate_id,),
        ).fetchone()
        if existing is None:
            raise JobAgentError(
                "Job import candidate not found",
                "job_import_candidate_not_found",
                status_code=404,
            )

        normalized_status = _normalize_status(status) if status is not None else None
        payload = {
            "title": title if title is not None else existing["title"],
            "company": company if company is not None else existing["company"],
            "location": location if location is not None else existing["location"],
            "job_type": job_type if job_type is not None else existing["job_type"],
            "education": education if education is not None else existing["education"],
            "deadline": deadline if deadline is not None else existing["deadline"],
            "status": normalized_status if normalized_status is not None else existing["status"],
            "user_notes": user_notes if user_notes is not None else existing["user_notes"],
            "updated_at": _utc_now(),
            "candidate_id": candidate_id,
        }
        with connection:
            connection.execute(
                """
                UPDATE job_import_candidates
                SET title = ?, company = ?, location = ?, job_type = ?, education = ?,
                    deadline = ?, status = ?, user_notes = ?, updated_at = ?
                WHERE candidate_id = ?
                """,
                (
                    payload["title"],
                    payload["company"],
                    payload["location"],
                    payload["job_type"],
                    payload["education"],
                    payload["deadline"],
                    payload["status"],
                    payload["user_notes"],
                    payload["updated_at"],
                    payload["candidate_id"],
                ),
            )
        updated = connection.execute(
            "SELECT * FROM job_import_candidates WHERE candidate_id = ?",
            (candidate_id,),
        ).fetchone()
        return sanitize_candidate_for_response(_row_to_candidate(updated))
    finally:
        connection.close()


def create_application_from_candidate(
    candidate_id: str,
    *,
    status: ApplicationStatus = "interested",
    notes: str | None = None,
    next_action: str | None = None,
    resume_version_id: int | None = None,
    resume_version_label: str | None = None,
    database_path: str | Path | None = None,
) -> tuple[dict[str, Any], JobImportCandidate]:
    connection = get_connection(database_path)
    try:
        init_database(connection)
        _ensure_job_import_candidates_table(connection)
        existing = connection.execute(
            "SELECT * FROM job_import_candidates WHERE candidate_id = ?",
            (candidate_id,),
        ).fetchone()
        if existing is None:
            raise JobAgentError(
                "Job import candidate not found",
                "job_import_candidate_not_found",
                status_code=404,
            )

        tracker_application_id = existing["tracker_application_id"]
        if tracker_application_id is not None:
            existing_application = get_application_record(connection, int(tracker_application_id))
            if existing_application is not None:
                candidate = _mark_candidate_imported(connection, candidate_id=candidate_id)
                return existing_application, candidate

        candidate = _row_to_candidate(existing)
        job_id = _get_or_create_job_posting_for_candidate(connection, candidate)
        application = upsert_application_record(
            connection,
            job_id=job_id,
            status=status,
            notes=notes,
            next_action=next_action,
            resume_version_id=resume_version_id,
            resume_version_label=resume_version_label,
        )
        if application is None:
            if resume_version_id is not None:
                raise JobAgentError(
                    "resume version not found",
                    "resume_version_not_found",
                    status_code=404,
                )
            raise JobAgentError(
                "job not found",
                "job_not_found",
                status_code=404,
            )

        updated_candidate = _mark_candidate_imported(
            connection,
            candidate_id=candidate_id,
            tracker_application_id=int(application["id"]),
        )
        return application, updated_candidate
    finally:
        connection.close()


def sanitize_candidate_for_response(
    candidate: JobImportCandidate,
    *,
    include_full_jd: bool = False,
) -> JobImportCandidate:
    preview = (candidate.jd_text_preview or candidate.jd_text or candidate.snippet or "").strip()
    return candidate.model_copy(
        update={
            "jd_text_preview": preview[:JD_TEXT_PREVIEW_MAX_CHARS] or None,
            "jd_text": candidate.jd_text if include_full_jd else None,
        }
    )


def _create_candidate_from_brief_run(
    connection: sqlite3.Connection,
    *,
    run_id: str,
    item_id: int | None,
    rank: int | None,
) -> JobImportCandidate:
    run_row = connection.execute(
        "SELECT run_id FROM brief_runs WHERE run_id = ?",
        (run_id,),
    ).fetchone()
    if run_row is None:
        raise JobAgentError("Brief run not found", "brief_run_not_found", status_code=404)

    item_row = _load_brief_run_item(connection, run_id=run_id, item_id=item_id, rank=rank)
    source_url = str(item_row["source_url"] or "").strip() or None
    if source_url:
        existing = connection.execute(
            """
            SELECT *
            FROM job_import_candidates
            WHERE source = 'brief_run' AND source_run_id = ? AND source_url = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (run_id, source_url),
        ).fetchone()
        if existing is not None:
            return sanitize_candidate_for_response(_row_to_candidate(existing))

    recommendation_payload = _json_loads_object(item_row["recommendation_json"])
    job_payload = _json_loads_object(item_row["job_json"])
    candidate = JobImportCandidate(
        candidate_id=uuid.uuid4().hex[:12],
        source="brief_run",
        source_run_id=run_id,
        source_item_id=int(item_row["id"]),
        title=str(item_row["title"] or ""),
        company=_coalesce_string(item_row["company"], recommendation_payload.get("job", {}).get("company")),
        location=_coalesce_string(item_row["location"], recommendation_payload.get("job", {}).get("location")),
        source_url=source_url,
        job_type=_coalesce_string(job_payload.get("job_type"), recommendation_payload.get("job", {}).get("job_type")),
        education=_coalesce_string(job_payload.get("education"), recommendation_payload.get("job", {}).get("education")),
        deadline=_coalesce_string(job_payload.get("deadline"), recommendation_payload.get("job", {}).get("deadline")),
        snippet=_coalesce_string(job_payload.get("snippet"), recommendation_payload.get("job", {}).get("snippet")),
        jd_text_preview=_build_jd_preview(item_row["jd_text"], job_payload.get("jd_text_preview")),
        jd_text=_coalesce_string(item_row["jd_text"]),
        quality_label=_coalesce_string(
            job_payload.get("quality_label"),
            recommendation_payload.get("job", {}).get("quality_label"),
            item_row["scoring_quality"],
        ),
        quality_score=_coalesce_float(
            job_payload.get("quality_score"),
            recommendation_payload.get("job", {}).get("quality_score"),
            item_row["confidence"],
        ),
        quality_warnings=_coalesce_list(
            job_payload.get("warnings"),
            recommendation_payload.get("job", {}).get("warnings"),
        ),
        external_links=_coalesce_list(
            job_payload.get("external_links"),
            recommendation_payload.get("job", {}).get("external_links"),
        ),
        fit_score=_coalesce_float(item_row["fit_score"], recommendation_payload.get("fit_score")),
        advice=_coalesce_string(item_row["advice"], recommendation_payload.get("advice")),
        fit_reasons=_coalesce_list(recommendation_payload.get("fit_reasons")),
        risk_points=_coalesce_list(recommendation_payload.get("risk_points")),
        status="draft",
        user_notes=None,
        created_at=_utc_now(),
        updated_at=_utc_now(),
    )

    with connection:
        connection.execute(
            """
            INSERT INTO job_import_candidates (
                candidate_id, source, source_run_id, source_item_id, title, company, location,
                source_url, job_type, education, deadline, snippet, jd_text, jd_text_preview,
                quality_label, quality_score, quality_warnings, external_links, fit_score,
                advice, fit_reasons, risk_points, status, user_notes, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                candidate.candidate_id,
                candidate.source,
                candidate.source_run_id,
                candidate.source_item_id,
                candidate.title,
                candidate.company,
                candidate.location,
                candidate.source_url,
                candidate.job_type,
                candidate.education,
                candidate.deadline,
                candidate.snippet,
                candidate.jd_text,
                candidate.jd_text_preview,
                candidate.quality_label,
                candidate.quality_score,
                _json_dumps(candidate.quality_warnings),
                _json_dumps(candidate.external_links),
                candidate.fit_score,
                candidate.advice,
                _json_dumps(candidate.fit_reasons),
                _json_dumps(candidate.risk_points),
                candidate.status,
                candidate.user_notes,
                candidate.created_at,
                candidate.updated_at,
            ),
        )
    return sanitize_candidate_for_response(candidate)


def _load_brief_run_item(
    connection: sqlite3.Connection,
    *,
    run_id: str,
    item_id: int | None,
    rank: int | None,
) -> sqlite3.Row:
    if item_id is not None:
        row = connection.execute(
            """
            SELECT *
            FROM brief_run_items
            WHERE run_id = ? AND id = ?
            """,
            (run_id, item_id),
        ).fetchone()
    else:
        lookup_rank = rank if rank is not None else 1
        row = connection.execute(
            """
            SELECT *
            FROM brief_run_items
            WHERE run_id = ? AND rank = ?
            ORDER BY id ASC
            LIMIT 1
            """,
            (run_id, lookup_rank),
        ).fetchone()

    if row is None:
        raise JobAgentError("Brief run item not found", "brief_run_item_not_found", status_code=404)
    return row


def _ensure_job_import_candidates_table(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS job_import_candidates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            candidate_id TEXT UNIQUE NOT NULL,
            source TEXT NOT NULL,
            source_run_id TEXT,
            source_item_id INTEGER,
            title TEXT NOT NULL,
            company TEXT,
            location TEXT,
            source_url TEXT,
            job_type TEXT,
            education TEXT,
            deadline TEXT,
            snippet TEXT,
            jd_text TEXT,
            jd_text_preview TEXT,
            quality_label TEXT,
            quality_score REAL,
            quality_warnings TEXT,
            external_links TEXT,
            fit_score REAL,
            advice TEXT,
            fit_reasons TEXT,
            risk_points TEXT,
            status TEXT NOT NULL,
            user_notes TEXT,
            tracker_application_id INTEGER,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        """
    )
    _ensure_column(connection, "job_import_candidates", "tracker_application_id", "INTEGER")
    connection.commit()


def _row_to_candidate(row: sqlite3.Row) -> JobImportCandidate:
    return JobImportCandidate(
        candidate_id=row["candidate_id"],
        source=row["source"],
        source_run_id=row["source_run_id"],
        source_item_id=int(row["source_item_id"]) if row["source_item_id"] is not None else None,
        title=row["title"],
        company=row["company"],
        location=row["location"],
        source_url=row["source_url"],
        job_type=row["job_type"],
        education=row["education"],
        deadline=row["deadline"],
        snippet=row["snippet"],
        jd_text_preview=row["jd_text_preview"],
        jd_text=row["jd_text"],
        quality_label=row["quality_label"],
        quality_score=float(row["quality_score"]) if row["quality_score"] is not None else None,
        quality_warnings=_json_loads_list(row["quality_warnings"]),
        external_links=_json_loads_list(row["external_links"]),
        fit_score=float(row["fit_score"]) if row["fit_score"] is not None else None,
        advice=row["advice"],
        fit_reasons=_json_loads_list(row["fit_reasons"]),
        risk_points=_json_loads_list(row["risk_points"]),
        status=row["status"],
        user_notes=row["user_notes"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _normalize_status(status: str | None) -> str:
    normalized = (status or "").strip()
    if normalized not in VALID_STATUSES:
        raise JobAgentError(
            "Job import candidate status is invalid",
            "job_import_candidate_status_invalid",
        )
    return normalized


def _normalize_limit(limit: int) -> int:
    try:
        normalized = int(limit)
    except (TypeError, ValueError) as exc:
        raise JobAgentError(
            "Job import candidate limit must be between 1 and 100",
            "job_import_candidate_limit_invalid",
        ) from exc
    if normalized < 1 or normalized > 100:
        raise JobAgentError(
            "Job import candidate limit must be between 1 and 100",
            "job_import_candidate_limit_invalid",
        )
    return normalized


def _build_jd_preview(*values: Any) -> str | None:
    for value in values:
        normalized = _coalesce_string(value)
        if normalized:
            return normalized[:JD_TEXT_PREVIEW_MAX_CHARS]
    return None


def _coalesce_string(*values: Any) -> str | None:
    for value in values:
        if value is None:
            continue
        normalized = str(value).strip()
        if normalized:
            return normalized
    return None


def _coalesce_float(*values: Any) -> float | None:
    for value in values:
        if value is None or value == "":
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _coalesce_list(*values: Any) -> list[str]:
    for value in values:
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if value is None:
            continue
    return []


def _json_loads_object(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    text = str(value).strip()
    if not text:
        return {}
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _json_loads_list(value: Any) -> list[str]:
    if value is None:
        return []
    text = str(value).strip()
    if not text:
        return []
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, list):
        return []
    return [str(item).strip() for item in payload if str(item).strip()]


def _json_dumps(value: Any) -> str:
    return json.dumps(value or [], ensure_ascii=False)


def _mark_candidate_imported(
    connection: sqlite3.Connection,
    *,
    candidate_id: str,
    tracker_application_id: int | None = None,
) -> JobImportCandidate:
    current = connection.execute(
        "SELECT tracker_application_id FROM job_import_candidates WHERE candidate_id = ?",
        (candidate_id,),
    ).fetchone()
    if current is None:
        raise JobAgentError(
            "Job import candidate not found",
            "job_import_candidate_not_found",
            status_code=404,
        )
    stored_application_id = (
        tracker_application_id
        if tracker_application_id is not None
        else current["tracker_application_id"]
    )
    updated_at = _utc_now()
    with connection:
        connection.execute(
            """
            UPDATE job_import_candidates
            SET status = ?, tracker_application_id = ?, updated_at = ?
            WHERE candidate_id = ?
            """,
            ("imported", stored_application_id, updated_at, candidate_id),
        )
    row = connection.execute(
        "SELECT * FROM job_import_candidates WHERE candidate_id = ?",
        (candidate_id,),
    ).fetchone()
    return sanitize_candidate_for_response(_row_to_candidate(row))


def _get_or_create_job_posting_for_candidate(
    connection: sqlite3.Connection,
    candidate: JobImportCandidate,
) -> int:
    raw_jd = _build_candidate_raw_jd(candidate)
    existing = connection.execute(
        "SELECT id FROM job_postings WHERE raw_jd = ? ORDER BY id ASC LIMIT 1",
        (raw_jd,),
    ).fetchone()
    if existing is not None:
        return int(existing["id"])

    job_analysis = JobAnalysis(
        raw_jd=raw_jd,
        job_title=candidate.title,
        company=candidate.company,
        location=candidate.location,
        education_requirements=[candidate.education] if candidate.education else [],
        keywords=_build_candidate_keywords(candidate),
        job_category=candidate.job_type,
    )
    cursor = connection.execute(
        """
        INSERT INTO job_postings (raw_jd, analysis_json, job_title, company)
        VALUES (?, ?, ?, ?)
        """,
        (
            raw_jd,
            json.dumps(job_analysis.model_dump(mode="json"), ensure_ascii=False),
            candidate.title,
            candidate.company,
        ),
    )
    return int(cursor.lastrowid)


def _build_candidate_raw_jd(candidate: JobImportCandidate) -> str:
    raw_jd = _coalesce_string(candidate.jd_text, candidate.jd_text_preview, candidate.snippet)
    if raw_jd:
        return raw_jd

    parts = [
        f"Title: {candidate.title}",
        f"Company: {candidate.company}" if candidate.company else None,
        f"Location: {candidate.location}" if candidate.location else None,
        f"Job Type: {candidate.job_type}" if candidate.job_type else None,
        f"Education: {candidate.education}" if candidate.education else None,
        f"Source URL: {candidate.source_url}" if candidate.source_url else None,
    ]
    return "\n".join(part for part in parts if part)


def _build_candidate_keywords(candidate: JobImportCandidate) -> list[str]:
    values = [
        candidate.title,
        candidate.company,
        candidate.location,
        candidate.job_type,
        candidate.education,
    ]
    keywords: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = _coalesce_string(value)
        if normalized and normalized not in seen:
            keywords.append(normalized)
            seen.add(normalized)
    return keywords


def _ensure_column(
    connection: sqlite3.Connection,
    table_name: str,
    column_name: str,
    column_definition: str,
) -> None:
    columns = {
        row["name"]
        for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    }
    if column_name not in columns:
        connection.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
