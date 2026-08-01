from __future__ import annotations

from datetime import datetime, timezone
from sqlite3 import Connection
from uuid import uuid4

from app.schemas.tailored_resume import (
    ResumeFactValidation,
    TailoredResumeStatus,
    TailoredResumeVersion,
)
from app.storage.database import get_connection, init_database


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TailoredResumeRepository:
    def create(
        self,
        *,
        user_id: str,
        saved_job_id: str,
        resume_profile_id: str,
        content: str,
        validation: ResumeFactValidation,
        status: TailoredResumeStatus,
        analysis_provider: str | None,
    ) -> TailoredResumeVersion:
        now = _utc_now()
        with get_connection() as connection:
            init_database(connection)
            row = connection.execute(
                "SELECT COALESCE(MAX(version), 0) AS value FROM tailored_resume_versions WHERE user_id = ? AND saved_job_id = ?",
                (user_id, saved_job_id),
            ).fetchone()
            item = TailoredResumeVersion(
                tailored_resume_id=str(uuid4()),
                user_id=user_id,
                saved_job_id=saved_job_id,
                resume_profile_id=resume_profile_id,
                version=int(row["value"]) + 1,
                content=content,
                validation=validation,
                status=status,
                analysis_provider=analysis_provider,
                created_at=now,
                updated_at=now,
            )
            self.insert_with_connection(connection, item)
            connection.commit()
        return item

    def insert_with_connection(self, connection: Connection, item: TailoredResumeVersion) -> None:
        connection.execute(
            """
            INSERT INTO tailored_resume_versions (
                tailored_resume_id, user_id, saved_job_id,
                resume_profile_id, version, content, changes_json,
                validation_json, status, analysis_mode, analysis_provider,
                fallback_reason, created_at, updated_at, approved_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item.tailored_resume_id,
                item.user_id,
                item.saved_job_id,
                item.resume_profile_id,
                item.version,
                item.content,
                "[]",
                item.validation.model_dump_json(),
                item.status,
                "llm",
                item.analysis_provider,
                None,
                item.created_at.isoformat(),
                item.updated_at.isoformat(),
                item.approved_at.isoformat() if item.approved_at else None,
            ),
        )

    def get(self, *, user_id: str, tailored_resume_id: str) -> TailoredResumeVersion | None:
        with get_connection() as connection:
            init_database(connection)
            row = connection.execute(
                "SELECT * FROM tailored_resume_versions WHERE user_id = ? AND tailored_resume_id = ?",
                (user_id, tailored_resume_id),
            ).fetchone()
        return self._row_to_item(row) if row is not None else None

    def latest_for_saved_job(
        self, *, user_id: str, saved_job_id: str
    ) -> TailoredResumeVersion | None:
        with get_connection() as connection:
            init_database(connection)
            row = connection.execute(
                """
                SELECT * FROM tailored_resume_versions
                WHERE user_id = ? AND saved_job_id = ?
                ORDER BY version DESC LIMIT 1
                """,
                (user_id, saved_job_id),
            ).fetchone()
        return self._row_to_item(row) if row is not None else None

    def update_content(
        self,
        *,
        user_id: str,
        tailored_resume_id: str,
        content: str,
        validation: ResumeFactValidation,
    ) -> TailoredResumeVersion | None:
        now = _utc_now().isoformat()
        status: TailoredResumeStatus = "needs_review"
        with get_connection() as connection:
            init_database(connection)
            cursor = connection.execute(
                """
                UPDATE tailored_resume_versions
                SET content = ?, validation_json = ?, status = ?, approved_at = NULL, updated_at = ?
                WHERE user_id = ? AND tailored_resume_id = ?
                """,
                (
                    content,
                    validation.model_dump_json(),
                    status,
                    now,
                    user_id,
                    tailored_resume_id,
                ),
            )
            connection.commit()
        if cursor.rowcount == 0:
            return None
        return self.get(user_id=user_id, tailored_resume_id=tailored_resume_id)

    def approve(self, *, user_id: str, tailored_resume_id: str) -> TailoredResumeVersion | None:
        now = _utc_now().isoformat()
        with get_connection() as connection:
            init_database(connection)
            cursor = connection.execute(
                """
                UPDATE tailored_resume_versions
                SET status = 'approved', approved_at = ?, updated_at = ?
                WHERE user_id = ? AND tailored_resume_id = ?
                """,
                (now, now, user_id, tailored_resume_id),
            )
            connection.commit()
        if cursor.rowcount == 0:
            return None
        return self.get(user_id=user_id, tailored_resume_id=tailored_resume_id)

    @staticmethod
    def _row_to_item(row: object) -> TailoredResumeVersion:
        return TailoredResumeVersion(
            tailored_resume_id=row["tailored_resume_id"],
            user_id=row["user_id"],
            saved_job_id=row["saved_job_id"],
            resume_profile_id=row["resume_profile_id"],
            version=int(row["version"]),
            content=row["content"],
            validation=ResumeFactValidation.model_validate_json(row["validation_json"]),
            status=row["status"],
            analysis_provider=row["analysis_provider"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            approved_at=(
                datetime.fromisoformat(row["approved_at"])
                if row["approved_at"] is not None
                else None
            ),
        )


tailored_resume_repository = TailoredResumeRepository()
