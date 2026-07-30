"""读写 SQLite 中的搜索结果反馈，并在查询和更新时强制 user_id 隔离。"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from app.schemas.job_search_feedback import JobSearchResultFeedback
from app.storage.database import get_connection, init_database


class JobSearchFeedbackRepository:
    """封装职位搜索反馈的 SQLite 读写与模型重建。"""
    def upsert(
        self,
        *,
        user_id: str,
        job_search_run_id: str,
        job_result_id: str,
        confirmed_profile_id: str,
        resume_profile_id: str | None,
        source_provider: str | None,
        feedback_type: str,
        note: str | None,
    ) -> JobSearchResultFeedback:
        """按方法参数限定的主键或用户范围新增或更新相关数据。"""
        existing = self.get_for_result(
            user_id=user_id,
            job_search_run_id=job_search_run_id,
            job_result_id=job_result_id,
        )
        now = datetime.now(timezone.utc)
        feedback = JobSearchResultFeedback(
            feedback_id=existing.feedback_id if existing else str(uuid4()),
            user_id=user_id,
            job_search_run_id=job_search_run_id,
            job_result_id=job_result_id,
            confirmed_profile_id=confirmed_profile_id,
            resume_profile_id=resume_profile_id,
            source_provider=source_provider,
            feedback_type=feedback_type,
            note=note,
            created_at=existing.created_at if existing else now,
            updated_at=now,
        )
        with get_connection() as connection:
            init_database(connection)
            connection.execute(
                """
                INSERT INTO job_search_result_feedback (
                    feedback_id, user_id, job_search_run_id, job_result_id,
                    confirmed_profile_id, resume_profile_id, source_provider,
                    feedback_type, note, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, job_search_run_id, job_result_id) DO UPDATE SET
                    confirmed_profile_id = excluded.confirmed_profile_id,
                    resume_profile_id = excluded.resume_profile_id,
                    source_provider = excluded.source_provider,
                    feedback_type = excluded.feedback_type,
                    note = excluded.note,
                    updated_at = excluded.updated_at
                """,
                (
                    feedback.feedback_id,
                    feedback.user_id,
                    feedback.job_search_run_id,
                    feedback.job_result_id,
                    feedback.confirmed_profile_id,
                    feedback.resume_profile_id,
                    feedback.source_provider,
                    feedback.feedback_type,
                    feedback.note,
                    feedback.created_at.isoformat(),
                    feedback.updated_at.isoformat(),
                ),
            )
            connection.commit()
        return self.get_for_result(
            user_id=user_id,
            job_search_run_id=job_search_run_id,
            job_result_id=job_result_id,
        ) or feedback

    def list_for_run(self, *, user_id: str, job_search_run_id: str) -> list[JobSearchResultFeedback]:
        """按方法参数限定的主键或用户范围列出for运行记录。"""
        with get_connection() as connection:
            init_database(connection)
            rows = connection.execute(
                """
                SELECT * FROM job_search_result_feedback
                WHERE user_id = ? AND job_search_run_id = ?
                ORDER BY updated_at DESC
                """,
                (user_id, job_search_run_id),
            ).fetchall()
        return [self._from_row(row) for row in rows]

    def get_for_result(
        self, *, user_id: str, job_search_run_id: str, job_result_id: str
    ) -> JobSearchResultFeedback | None:
        """按方法参数限定的主键或用户范围获取for结果。"""
        with get_connection() as connection:
            init_database(connection)
            row = connection.execute(
                """
                SELECT * FROM job_search_result_feedback
                WHERE user_id = ? AND job_search_run_id = ? AND job_result_id = ?
                """,
                (user_id, job_search_run_id, job_result_id),
            ).fetchone()
        return self._from_row(row) if row is not None else None

    @staticmethod
    def _from_row(row: object) -> JobSearchResultFeedback:
        return JobSearchResultFeedback(
            feedback_id=row["feedback_id"],
            user_id=row["user_id"],
            job_search_run_id=row["job_search_run_id"],
            job_result_id=row["job_result_id"],
            confirmed_profile_id=row["confirmed_profile_id"],
            resume_profile_id=row["resume_profile_id"],
            source_provider=row["source_provider"],
            feedback_type=row["feedback_type"],
            note=row["note"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )


job_search_feedback_repository = JobSearchFeedbackRepository()
