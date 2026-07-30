"""读写 SQLite 中的浏览器职位采集，并在查询和更新时强制 user_id 隔离。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import uuid4

from app.schemas.job_search import (
    BrowserJobCaptureCreateRequest,
    BrowserJobCaptureRecord,
)
from app.storage.database import get_connection, init_database


class BrowserJobCaptureRepository:
    """封装浏览器职位职位采集的 SQLite 读写与模型重建。"""
    def create(
        self,
        *,
        user_id: str,
        payload: BrowserJobCaptureCreateRequest,
    ) -> BrowserJobCaptureRecord:
        """按方法参数限定的主键或用户范围创建相关数据。"""
        created_at = datetime.now(timezone.utc)
        record = BrowserJobCaptureRecord(
            **payload.model_dump(),
            capture_id=str(uuid4()),
            user_id=user_id,
            created_at=created_at,
        )
        with get_connection() as connection:
            init_database(connection)
            connection.execute(
                """
                INSERT INTO browser_job_captures (
                    capture_id, user_id, source, source_url, page_title, title,
                    company, location, salary, jd_text, visible_text, captured_at,
                    extractor_version, warnings_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.capture_id, user_id, record.source, record.source_url,
                    record.page_title, record.title, record.company, record.location,
                    record.salary, record.jd_text, record.visible_text,
                    record.captured_at.isoformat(), record.extractor_version,
                    json.dumps(record.warnings), created_at.isoformat(),
                ),
            )
            connection.commit()
        return record

    def get(self, *, user_id: str, capture_id: str) -> BrowserJobCaptureRecord | None:
        """按方法参数限定的主键或用户范围获取相关数据。"""
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
            source=row["source"],
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
