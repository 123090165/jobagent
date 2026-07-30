"""读写 SQLite 中的Job Brief，并在查询和更新时强制 user_id 隔离。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import uuid4

from app.schemas.job_brief import JobBrief, JobBriefContent
from app.storage.database import get_connection, init_database


class JobBriefRepository:
    """封装职位决策简报的 SQLite 读写与模型重建。"""
    def create(
        self,
        *,
        user_id: str,
        saved_job_id: str,
        content: JobBriefContent,
        analysis_mode: str,
        resume_profile_id: str | None = None,
        source_analysis_id: str | None = None,
        analysis_provider: str | None = None,
        fallback_reason: str | None = None,
    ) -> JobBrief:
        """按方法参数限定的主键或用户范围创建相关数据。"""
        created_at = datetime.now(timezone.utc)
        with get_connection() as connection:
            init_database(connection)
            row = connection.execute(
                "SELECT COALESCE(MAX(version), 0) + 1 AS version FROM job_briefs WHERE user_id = ? AND saved_job_id = ?",
                (user_id, saved_job_id),
            ).fetchone()
            item = JobBrief(
                job_brief_id=str(uuid4()), user_id=user_id, saved_job_id=saved_job_id,
                resume_profile_id=resume_profile_id, source_analysis_id=source_analysis_id,
                version=int(row["version"]), content=content, analysis_mode=analysis_mode,
                analysis_provider=analysis_provider, fallback_reason=fallback_reason,
                created_at=created_at,
            )
            connection.execute(
                """
                INSERT INTO job_briefs (
                    job_brief_id, saved_job_id, user_id, resume_profile_id,
                    source_analysis_id, version, content_json, analysis_mode,
                    analysis_provider, fallback_reason, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.job_brief_id, item.saved_job_id, item.user_id,
                    item.resume_profile_id, item.source_analysis_id, item.version,
                    json.dumps(item.content.model_dump(mode="json")), item.analysis_mode,
                    item.analysis_provider, item.fallback_reason, item.created_at.isoformat(),
                ),
            )
            connection.commit()
        return item

    def list_by_job(self, *, user_id: str, saved_job_id: str) -> list[JobBrief]:
        """按方法参数限定的主键或用户范围列出by职位。"""
        with get_connection() as connection:
            init_database(connection)
            rows = connection.execute(
                "SELECT * FROM job_briefs WHERE user_id = ? AND saved_job_id = ? ORDER BY version DESC",
                (user_id, saved_job_id),
            ).fetchall()
        return [self._row_to_brief(row) for row in rows]

    @staticmethod
    def _row_to_brief(row: object) -> JobBrief:
        return JobBrief(
            job_brief_id=row["job_brief_id"], saved_job_id=row["saved_job_id"],
            user_id=row["user_id"], resume_profile_id=row["resume_profile_id"],
            source_analysis_id=row["source_analysis_id"], version=row["version"],
            content=JobBriefContent.model_validate(json.loads(row["content_json"])),
            analysis_mode=row["analysis_mode"], analysis_provider=row["analysis_provider"],
            fallback_reason=row["fallback_reason"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )


job_brief_repository = JobBriefRepository()
