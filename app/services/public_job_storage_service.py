from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.schemas.cuhksz_career import CUHKSZJobDetail
from app.services.live_job.base import RawJobDetail
from app.storage.database import get_connection


def ensure_public_job_posts_table(*, database_path: str | Path | None = None) -> None:
    connection = get_connection(database_path)
    try:
        _ensure_public_job_posts_table(connection)
    finally:
        connection.close()


def save_public_job_post(
    detail: CUHKSZJobDetail | RawJobDetail,
    *,
    database_path: str | Path | None = None,
) -> int:
    connection = get_connection(database_path)
    try:
        _ensure_public_job_posts_table(connection)
        return _save_public_job_post(connection, detail)
    finally:
        connection.close()


def list_public_job_posts(
    keyword: str | None = None,
    limit: int = 20,
    *,
    database_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    connection = get_connection(database_path)
    try:
        _ensure_public_job_posts_table(connection)
        query = """
            SELECT *
            FROM public_job_posts
        """
        parameters: list[Any] = []
        if keyword:
            query += """
                WHERE title LIKE ?
                   OR company LIKE ?
                   OR location LIKE ?
                   OR job_type LIKE ?
                   OR education LIKE ?
                   OR snippet LIKE ?
                   OR jd_text LIKE ?
            """
            like_keyword = f"%{keyword}%"
            parameters.extend([like_keyword] * 7)
        query += " ORDER BY updated_at DESC, id DESC LIMIT ?"
        parameters.append(_normalize_limit(limit))
        rows = connection.execute(query, tuple(parameters)).fetchall()
        return [_row_to_dict(row) for row in rows]
    finally:
        connection.close()


def get_public_job_post(
    post_id: int,
    *,
    database_path: str | Path | None = None,
) -> dict[str, Any] | None:
    connection = get_connection(database_path)
    try:
        _ensure_public_job_posts_table(connection)
        row = connection.execute(
            "SELECT * FROM public_job_posts WHERE id = ?",
            (post_id,),
        ).fetchone()
        return _row_to_dict(row) if row is not None else None
    finally:
        connection.close()


def _ensure_public_job_posts_table(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS public_job_posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            external_id TEXT NOT NULL,
            source_url TEXT NOT NULL,
            title TEXT NOT NULL,
            company TEXT,
            location TEXT,
            job_type TEXT,
            education TEXT,
            published_at TEXT,
            deadline TEXT,
            snippet TEXT,
            jd_text TEXT NOT NULL,
            quality_label TEXT,
            quality_score REAL,
            quality_warnings TEXT,
            external_links TEXT,
            is_full_jd INTEGER NOT NULL DEFAULT 0,
            confidence REAL NOT NULL DEFAULT 0,
            extraction_method TEXT,
            content_hash TEXT NOT NULL,
            fetched_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(source, external_id)
        );
        """
    )
    _ensure_column(connection, "public_job_posts", "quality_label", "TEXT")
    _ensure_column(connection, "public_job_posts", "quality_score", "REAL")
    _ensure_column(connection, "public_job_posts", "quality_warnings", "TEXT")
    _ensure_column(connection, "public_job_posts", "external_links", "TEXT")
    connection.commit()


def _save_public_job_post(connection: sqlite3.Connection, detail: CUHKSZJobDetail | RawJobDetail) -> int:
    item = detail.list_item
    now = _utc_now()
    content_hash = _build_content_hash(detail)
    existing = connection.execute(
        """
        SELECT id, content_hash
        FROM public_job_posts
        WHERE source = ? AND external_id = ?
        """,
        (item.source, item.external_id),
    ).fetchone()

    with connection:
        if existing is None:
            cursor = connection.execute(
                """
                INSERT INTO public_job_posts (
                    source,
                    external_id,
                    source_url,
                    title,
                    company,
                    location,
                    job_type,
                    education,
                    published_at,
                    deadline,
                    snippet,
                    jd_text,
                    quality_label,
                    quality_score,
                    quality_warnings,
                    external_links,
                    is_full_jd,
                    confidence,
                    extraction_method,
                    content_hash,
                    fetched_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                _detail_to_parameters(detail, content_hash, fetched_at=now, updated_at=now),
            )
            return int(cursor.lastrowid)

        post_id = int(existing["id"])
        if existing["content_hash"] == content_hash:
            connection.execute(
                """
                UPDATE public_job_posts
                SET
                    quality_label = ?,
                    quality_score = ?,
                    quality_warnings = ?,
                    external_links = ?,
                    is_full_jd = ?,
                    confidence = ?,
                    extraction_method = ?,
                    fetched_at = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    detail.quality_label,
                    detail.confidence,
                    _json_dumps(detail.warnings),
                    _json_dumps(detail.external_links),
                    int(detail.is_full_jd),
                    detail.confidence,
                    detail.extraction_method,
                    now,
                    now,
                    post_id,
                ),
            )
            return post_id

        connection.execute(
            """
            UPDATE public_job_posts
            SET
                source_url = ?,
                title = ?,
                company = ?,
                location = ?,
                job_type = ?,
                education = ?,
                published_at = ?,
                deadline = ?,
                snippet = ?,
                jd_text = ?,
                quality_label = ?,
                quality_score = ?,
                quality_warnings = ?,
                external_links = ?,
                is_full_jd = ?,
                confidence = ?,
                extraction_method = ?,
                content_hash = ?,
                fetched_at = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                item.detail_url,
                item.title,
                item.company,
                item.location,
                item.job_type,
                item.education,
                item.published_at,
                item.deadline,
                detail.snippet,
                detail.jd_text,
                detail.quality_label,
                detail.confidence,
                _json_dumps(detail.warnings),
                _json_dumps(detail.external_links),
                int(detail.is_full_jd),
                detail.confidence,
                detail.extraction_method,
                content_hash,
                now,
                now,
                post_id,
            ),
        )
        return post_id


def _detail_to_parameters(
    detail: CUHKSZJobDetail | RawJobDetail,
    content_hash: str,
    *,
    fetched_at: str,
    updated_at: str,
) -> tuple[Any, ...]:
    item = detail.list_item
    return (
        item.source,
        item.external_id,
        item.detail_url,
        item.title,
        item.company,
        item.location,
        item.job_type,
        item.education,
        item.published_at,
        item.deadline,
        detail.snippet,
        detail.jd_text,
        detail.quality_label,
        detail.confidence,
        _json_dumps(detail.warnings),
        _json_dumps(detail.external_links),
        int(detail.is_full_jd),
        detail.confidence,
        detail.extraction_method,
        content_hash,
        fetched_at,
        updated_at,
    )


def _build_content_hash(detail: CUHKSZJobDetail | RawJobDetail) -> str:
    item = detail.list_item
    source_text = "\0".join(
        [
            item.title or "",
            item.company or "",
            item.detail_url or "",
            detail.jd_text or "",
        ]
    )
    return hashlib.sha256(source_text.encode("utf-8")).hexdigest()


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "source": row["source"],
        "external_id": row["external_id"],
        "source_url": row["source_url"],
        "title": row["title"],
        "company": row["company"],
        "location": row["location"],
        "job_type": row["job_type"],
        "education": row["education"],
        "published_at": row["published_at"],
        "deadline": row["deadline"],
        "snippet": row["snippet"],
        "jd_text": row["jd_text"],
        "quality_label": row["quality_label"] or _fallback_quality_label(row),
        "quality_score": float(row["quality_score"]) if row["quality_score"] is not None else float(row["confidence"]),
        "quality_warnings": _json_loads_list(row["quality_warnings"]),
        "external_links": _json_loads_list(row["external_links"]),
        "is_full_jd": bool(row["is_full_jd"]),
        "confidence": float(row["confidence"]),
        "extraction_method": row["extraction_method"],
        "content_hash": row["content_hash"],
        "fetched_at": row["fetched_at"],
        "updated_at": row["updated_at"],
    }


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _normalize_limit(limit: int) -> int:
    return max(1, min(int(limit), 100))


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


def _json_dumps(values: list[str]) -> str:
    return json.dumps(values or [], ensure_ascii=False)


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


def _fallback_quality_label(row: sqlite3.Row) -> str:
    if bool(row["is_full_jd"]):
        return "full_jd"
    if str(row["jd_text"] or "").strip():
        return "partial_jd"
    return "snippet_only"
