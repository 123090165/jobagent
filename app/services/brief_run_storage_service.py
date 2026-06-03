from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.schemas.brief import JobBriefReport, JobRecommendationItem
from app.services.batch_brief_service import (
    build_application_strategy,
    build_market_summary,
    build_scoring_quality_summary,
    collect_top_skills,
)
from app.storage.database import get_connection

JD_TEXT_PREVIEW_MAX_CHARS = 500


def ensure_brief_run_tables(*, database_path: str | Path | None = None) -> None:
    connection = get_connection(database_path)
    try:
        _ensure_brief_run_tables(connection)
    finally:
        connection.close()


def save_brief_run(
    report: JobBriefReport,
    resume_text: str,
    *,
    database_path: str | Path | None = None,
) -> str:
    connection = get_connection(database_path)
    try:
        _ensure_brief_run_tables(connection)
        return _save_brief_run(connection, report, resume_text)
    finally:
        connection.close()


def get_brief_run(
    run_id: str,
    *,
    database_path: str | Path | None = None,
) -> dict[str, Any] | None:
    connection = get_connection(database_path)
    try:
        _ensure_brief_run_tables(connection)
        return _get_brief_run(connection, run_id)
    finally:
        connection.close()


def list_brief_runs(
    limit: int = 20,
    *,
    database_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    connection = get_connection(database_path)
    try:
        _ensure_brief_run_tables(connection)
        rows = connection.execute(
            """
            SELECT run_id, query, provider, total_jobs, full_jd_count, partial_jd_count,
                   external_link_only_count, snippet_only_count, created_at, updated_at
            FROM brief_runs
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            (_normalize_limit(limit),),
        ).fetchall()
        return [
            {
                "run_id": row["run_id"],
                "query": row["query"],
                "provider": row["provider"],
                "total_jobs": int(row["total_jobs"]),
                "full_jd_count": int(row["full_jd_count"]),
                "partial_jd_count": int(row["partial_jd_count"]),
                "external_link_only_count": int(row["external_link_only_count"]),
                "snippet_only_count": int(row["snippet_only_count"]),
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
            for row in rows
        ]
    finally:
        connection.close()


def sanitize_recommendation_for_storage(item: JobRecommendationItem) -> dict[str, Any]:
    payload = item.model_dump(mode="json")
    job_payload = dict(payload.get("job") or {})
    jd_text = str(job_payload.pop("jd_text", "") or "")
    if jd_text.strip():
        job_payload["jd_text_preview"] = jd_text[:JD_TEXT_PREVIEW_MAX_CHARS]
    payload["job"] = job_payload
    return payload


def _ensure_brief_run_tables(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS brief_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT UNIQUE NOT NULL,
            query TEXT NOT NULL,
            provider TEXT NOT NULL,
            resume_hash TEXT NOT NULL,
            total_jobs INTEGER NOT NULL DEFAULT 0,
            full_jd_count INTEGER NOT NULL DEFAULT 0,
            partial_jd_count INTEGER NOT NULL DEFAULT 0,
            external_link_only_count INTEGER NOT NULL DEFAULT 0,
            snippet_only_count INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS brief_run_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            rank INTEGER NOT NULL,
            source_url TEXT,
            title TEXT NOT NULL,
            company TEXT,
            location TEXT,
            source TEXT,
            fit_score REAL NOT NULL,
            advice TEXT,
            scoring_quality TEXT,
            is_full_jd INTEGER NOT NULL DEFAULT 0,
            confidence REAL NOT NULL DEFAULT 0,
            jd_text TEXT,
            job_json TEXT NOT NULL,
            match_report_json TEXT NOT NULL,
            recommendation_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (run_id) REFERENCES brief_runs(run_id)
        );
        """
    )
    _ensure_column(connection, "brief_run_items", "jd_text", "TEXT")
    connection.commit()


def _save_brief_run(
    connection: sqlite3.Connection,
    report: JobBriefReport,
    resume_text: str,
) -> str:
    run_id = uuid.uuid4().hex[:12]
    now = _utc_now()
    quality_counts = _count_scoring_qualities(report.recommended_jobs)
    resume_hash = hashlib.sha256(resume_text.encode("utf-8")).hexdigest()

    with connection:
        connection.execute(
            """
            INSERT INTO brief_runs (
                run_id, query, provider, resume_hash, total_jobs,
                full_jd_count, partial_jd_count, external_link_only_count, snippet_only_count,
                created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                report.query,
                report.provider,
                resume_hash,
                report.total_jobs,
                quality_counts.get("full_jd", 0),
                quality_counts.get("partial_jd", 0),
                quality_counts.get("external_link_only", 0),
                quality_counts.get("snippet_only", 0),
                now,
                now,
            ),
        )

        for item in report.recommended_jobs:
            sanitized_recommendation = sanitize_recommendation_for_storage(item)
            sanitized_job = sanitized_recommendation.get("job") or {}
            connection.execute(
                """
                INSERT INTO brief_run_items (
                    run_id, rank, source_url, title, company, location, source,
                    fit_score, advice, scoring_quality, is_full_jd, confidence,
                    jd_text, job_json, match_report_json, recommendation_json, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    item.rank,
                    item.job.url,
                    item.job.title,
                    item.job.company,
                    item.job.location,
                    item.job.source,
                    item.fit_score,
                    item.advice,
                    item.scoring_quality,
                    int(item.job.is_full_jd),
                    item.job.confidence,
                    item.job.jd_text,
                    _json_dumps(sanitized_job),
                    _json_dumps(item.match_report.model_dump(mode="json")),
                    _json_dumps(sanitized_recommendation),
                    now,
                ),
            )

    return run_id


def _get_brief_run(connection: sqlite3.Connection, run_id: str) -> dict[str, Any] | None:
    run_row = connection.execute(
        """
        SELECT run_id, query, provider, total_jobs, created_at, updated_at
        FROM brief_runs
        WHERE run_id = ?
        """,
        (run_id,),
    ).fetchone()
    if run_row is None:
        return None

    item_rows = connection.execute(
        """
        SELECT recommendation_json
        FROM brief_run_items
        WHERE run_id = ?
        ORDER BY rank ASC, id ASC
        """,
        (run_id,),
    ).fetchall()
    items = [_load_recommendation(row["recommendation_json"]) for row in item_rows]
    brief = _build_brief_report_from_items(
        query=run_row["query"],
        provider=run_row["provider"],
        total_jobs=int(run_row["total_jobs"]),
        items=items,
        reranked=False,
    )
    return {
        "run_id": run_row["run_id"],
        "brief": brief.model_dump(mode="json"),
        "created_at": run_row["created_at"],
        "updated_at": run_row["updated_at"],
    }


def _build_brief_report_from_items(
    *,
    query: str,
    provider: str,
    total_jobs: int,
    items: list[JobRecommendationItem],
    reranked: bool,
) -> JobBriefReport:
    reranked_items = [
        item.model_copy(update={"rank": index})
        for index, item in enumerate(items, start=1)
    ]
    jobs = [item.job for item in reranked_items]
    top_skills = collect_top_skills(jobs)
    market_summary = build_market_summary(query, provider, reranked_items, top_skills)
    if reranked:
        market_summary += " This report was reranked from an existing brief run without re-searching."
    return JobBriefReport(
        query=query,
        provider=provider,
        total_jobs=total_jobs,
        recommended_jobs=reranked_items,
        top_skills=top_skills,
        market_summary=market_summary,
        application_strategy=build_application_strategy(reranked_items, top_skills),
        scoring_quality_summary=build_scoring_quality_summary(reranked_items),
    )


def _load_recommendation(value: str) -> JobRecommendationItem:
    payload = json.loads(value)
    return JobRecommendationItem.model_validate(payload)


def _count_scoring_qualities(items: list[JobRecommendationItem]) -> dict[str, int]:
    counts = {
        "full_jd": 0,
        "partial_jd": 0,
        "external_link_only": 0,
        "snippet_only": 0,
    }
    for item in items:
        if item.scoring_quality in counts:
            counts[item.scoring_quality] += 1
    return counts


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _normalize_limit(limit: int) -> int:
    return max(1, min(int(limit), 100))


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


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
