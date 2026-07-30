"""读写 SQLite 中的简历到搜索的流程会话，并在查询和更新时强制 user_id 隔离。"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from app.schemas.profile_session import (
    ProfileSession,
    ProfileSessionStatus,
    ProfileSessionStep,
)
from app.storage.database import LOCAL_USER_ID, get_connection, init_database


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ProfileSessionRepository:
    """封装画像会话的 SQLite 读写与模型重建。"""
    def create(self, *, user_id: str = LOCAL_USER_ID) -> ProfileSession:
        """按方法参数限定的主键或用户范围创建相关数据。"""
        now = _utc_now()
        session = ProfileSession(
            session_id=str(uuid4()),
            status=ProfileSessionStatus.active,
            created_at=now,
            updated_at=now,
            current_step=ProfileSessionStep.created,
        )
        with get_connection() as connection:
            init_database(connection)
            connection.execute(
                """
                INSERT INTO profile_sessions (
                    session_id,
                    user_id,
                    status,
                    created_at,
                    updated_at,
                    resume_document_id,
                    parsed_review_id,
                    profile_draft_id,
                    confirmed_profile_id,
                    current_step
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session.session_id,
                    user_id,
                    session.status.value,
                    session.created_at.isoformat(),
                    session.updated_at.isoformat(),
                    session.resume_document_id,
                    session.parsed_review_id,
                    session.profile_draft_id,
                    session.confirmed_profile_id,
                    session.current_step.value,
                ),
            )
            connection.commit()
        return session

    def get(self, session_id: str, *, user_id: str | None = None) -> ProfileSession | None:
        """按方法参数限定的主键或用户范围获取相关数据。"""
        with get_connection() as connection:
            init_database(connection)
            where_clause = "WHERE session_id = ?"
            parameters: tuple[str, ...] = (session_id,)
            if user_id is not None:
                where_clause += " AND user_id = ?"
                parameters = (session_id, user_id)
            row = connection.execute(
                f"""
                SELECT
                    session_id,
                    status,
                    created_at,
                    updated_at,
                    resume_document_id,
                    parsed_review_id,
                    profile_draft_id,
                    confirmed_profile_id,
                    current_step
                FROM profile_sessions
                {where_clause}
                """,
                parameters,
            ).fetchone()
        if row is None:
            return None
        return self._row_to_profile_session(row)

    def list_ready_by_user(self, user_id: str, *, limit: int = 20) -> list[ProfileSession]:
        """按方法参数限定的主键或用户范围列出readyby用户。"""
        with get_connection() as connection:
            init_database(connection)
            rows = connection.execute(
                """
                SELECT
                    session_id, status, created_at, updated_at, resume_document_id,
                    parsed_review_id, profile_draft_id, confirmed_profile_id, current_step
                FROM profile_sessions
                WHERE user_id = ? AND confirmed_profile_id IS NOT NULL
                ORDER BY updated_at DESC, created_at DESC
                LIMIT ?
                """,
                (user_id, limit),
            ).fetchall()
        return [self._row_to_profile_session(row) for row in rows]

    def attach_resume_document(
        self,
        *,
        session_id: str,
        resume_document_id: str,
    ) -> ProfileSession | None:
        """按方法参数限定的主键或用户范围关联简历文档。"""
        updated_at = _utc_now()
        with get_connection() as connection:
            init_database(connection)
            cursor = connection.execute(
                """
                UPDATE profile_sessions
                SET
                    resume_document_id = ?,
                    parsed_review_id = NULL,
                    profile_draft_id = NULL,
                    confirmed_profile_id = NULL,
                    current_step = ?,
                    updated_at = ?
                WHERE session_id = ?
                """,
                (
                    resume_document_id,
                    ProfileSessionStep.resume_ready.value,
                    updated_at.isoformat(),
                    session_id,
                ),
            )
            connection.commit()
            if cursor.rowcount == 0:
                return None
        return self.get(session_id)

    def attach_parsed_review(
        self,
        *,
        session_id: str,
        parsed_review_id: str,
    ) -> ProfileSession | None:
        """按方法参数限定的主键或用户范围关联parsed审阅结果。"""
        updated_at = _utc_now()
        with get_connection() as connection:
            init_database(connection)
            cursor = connection.execute(
                """
                UPDATE profile_sessions
                SET
                    parsed_review_id = ?,
                    profile_draft_id = NULL,
                    confirmed_profile_id = NULL,
                    current_step = ?,
                    updated_at = ?
                WHERE session_id = ?
                """,
                (
                    parsed_review_id,
                    ProfileSessionStep.resume_review.value,
                    updated_at.isoformat(),
                    session_id,
                ),
            )
            connection.commit()
            if cursor.rowcount == 0:
                return None
        return self.get(session_id)

    def attach_profile_draft(
        self,
        *,
        session_id: str,
        profile_draft_id: str,
    ) -> ProfileSession | None:
        """按方法参数限定的主键或用户范围关联画像草稿。"""
        updated_at = _utc_now()
        with get_connection() as connection:
            init_database(connection)
            cursor = connection.execute(
                """
                UPDATE profile_sessions
                SET
                    profile_draft_id = ?,
                    confirmed_profile_id = NULL,
                    current_step = ?,
                    updated_at = ?
                WHERE session_id = ?
                """,
                (
                    profile_draft_id,
                    ProfileSessionStep.profile_draft.value,
                    updated_at.isoformat(),
                    session_id,
                ),
            )
            connection.commit()
            if cursor.rowcount == 0:
                return None
        return self.get(session_id)

    def attach_confirmed_profile(
        self,
        *,
        session_id: str,
        confirmed_profile_id: str,
    ) -> ProfileSession | None:
        """按方法参数限定的主键或用户范围关联已确认画像。"""
        updated_at = _utc_now()
        with get_connection() as connection:
            init_database(connection)
            cursor = connection.execute(
                """
                UPDATE profile_sessions
                SET
                    confirmed_profile_id = ?,
                    current_step = ?,
                    updated_at = ?
                WHERE session_id = ?
                """,
                (
                    confirmed_profile_id,
                    ProfileSessionStep.job_search_ready.value,
                    updated_at.isoformat(),
                    session_id,
                ),
            )
            connection.commit()
            if cursor.rowcount == 0:
                return None
        return self.get(session_id)

    def mark_job_search_running(self, *, session_id: str) -> ProfileSession | None:
        """按方法参数限定的主键或用户范围标记职位搜索running。"""
        updated_at = _utc_now()
        with get_connection() as connection:
            init_database(connection)
            cursor = connection.execute(
                """
                UPDATE profile_sessions
                SET
                    current_step = ?,
                    updated_at = ?
                WHERE session_id = ?
                """,
                (
                    ProfileSessionStep.job_search_running.value,
                    updated_at.isoformat(),
                    session_id,
                ),
            )
            connection.commit()
            if cursor.rowcount == 0:
                return None
        return self.get(session_id)

    def mark_job_search_completed(self, *, session_id: str) -> ProfileSession | None:
        """按方法参数限定的主键或用户范围标记职位搜索completed。"""
        updated_at = _utc_now()
        with get_connection() as connection:
            init_database(connection)
            cursor = connection.execute(
                """
                UPDATE profile_sessions
                SET
                    current_step = ?,
                    updated_at = ?
                WHERE session_id = ?
                """,
                (
                    ProfileSessionStep.job_search_completed.value,
                    updated_at.isoformat(),
                    session_id,
                ),
            )
            connection.commit()
            if cursor.rowcount == 0:
                return None
        return self.get(session_id)

    @staticmethod
    def _row_to_profile_session(row: object) -> ProfileSession:
        return ProfileSession(
            session_id=row["session_id"],
            status=ProfileSessionStatus(row["status"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            resume_document_id=row["resume_document_id"],
            parsed_review_id=row["parsed_review_id"],
            profile_draft_id=row["profile_draft_id"],
            confirmed_profile_id=row["confirmed_profile_id"],
            current_step=ProfileSessionStep(row["current_step"]),
        )


profile_session_repository = ProfileSessionRepository()
