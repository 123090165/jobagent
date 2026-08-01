from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from uuid import uuid4

from app.schemas.job_search import (
    BrowserJobCaptureCreateRequest,
    BrowserJobCaptureRecord,
)
from app.storage.database import get_connection, init_database


class BrowserJobCaptureRepository:
    def create(
        self,
        *,
        user_id: str,
        saved_job_id: str,
        payload: BrowserJobCaptureCreateRequest,
        connection: sqlite3.Connection | None = None,
    ) -> BrowserJobCaptureRecord:
        created_at = datetime.now(timezone.utc)
        record = BrowserJobCaptureRecord(
            **payload.model_dump(),
            capture_id=str(uuid4()),
            user_id=user_id,
            saved_job_id=saved_job_id,
            created_at=created_at,
        )
        if connection is not None:
            self._insert(connection, record)
            return record
        with get_connection() as owned:
            init_database(owned)
            self._insert(owned, record)
            owned.commit()
        return record

    @staticmethod
    def _insert(connection: sqlite3.Connection, record: BrowserJobCaptureRecord) -> None:
        connection.execute(
                """
                INSERT INTO browser_job_captures (
                    capture_id, user_id, saved_job_id, source, platform_job_id, source_url, page_title, title,
                    company, location, salary, jd_text, visible_text, captured_at,
                    extractor_version, warnings_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.capture_id, record.user_id, record.saved_job_id, record.source,
                    record.platform_job_id, record.source_url,
                    record.page_title, record.title, record.company, record.location,
                    record.salary, record.jd_text, record.visible_text,
                    record.captured_at.isoformat(), record.extractor_version,
                    json.dumps(record.warnings), record.created_at.isoformat(),
                ),
            )

    def get(self, *, user_id: str, capture_id: str) -> BrowserJobCaptureRecord | None:
        with get_connection() as connection:
            init_database(connection)
            row = connection.execute(
                "SELECT * FROM browser_job_captures WHERE user_id = ? AND capture_id = ?",
                (user_id, capture_id),
            ).fetchone()
        if row is None:
            return None
        return BrowserJobCaptureRecord(
            capture_id=row["capture_id"],
            user_id=row["user_id"],
            saved_job_id=row["saved_job_id"],
            source=row["source"],
            platform_job_id=row["platform_job_id"],
            source_url=row["source_url"],
            page_title=row["page_title"],
            title=row["title"],
            company=row["company"],
            location=row["location"],
            salary=row["salary"],
            jd_text=row["jd_text"],
            visible_text=row["visible_text"],
            captured_at=datetime.fromisoformat(row["captured_at"]),
            extractor_version=row["extractor_version"],
            warnings=json.loads(row["warnings_json"]),
            created_at=datetime.fromisoformat(row["created_at"]),
        )


browser_job_capture_repository = BrowserJobCaptureRepository()
