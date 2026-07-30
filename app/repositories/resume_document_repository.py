"""读写 SQLite 中的原始简历文档，并在查询和更新时强制 user_id 隔离。"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from app.schemas.resume_document import ResumeDocument, ResumeDocumentSourceType
from app.storage.database import LOCAL_USER_ID, get_connection, init_database


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ResumeDocumentRepository:
    """封装文档的 SQLite 读写与模型重建。"""
    def create(
        self,
        *,
        session_id: str,
        source_type: ResumeDocumentSourceType,
        text: str,
        user_id: str = LOCAL_USER_ID,
        filename: str | None = None,
        file_type: str | None = None,
    ) -> ResumeDocument:
        """按方法参数限定的主键或用户范围创建相关数据。"""
        now = _utc_now()
        document = ResumeDocument(
            resume_document_id=str(uuid4()),
            session_id=session_id,
            source_type=source_type,
            filename=filename,
            file_type=file_type,
            text=text,
            text_length=len(text),
            created_at=now,
            updated_at=now,
        )
        with get_connection() as connection:
            init_database(connection)
            connection.execute(
                """
                INSERT INTO resume_documents (
                    resume_document_id,
                    session_id,
                    user_id,
                    source_type,
                    filename,
                    file_type,
                    text,
                    text_length,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    document.resume_document_id,
                    document.session_id,
                    user_id,
                    document.source_type,
                    document.filename,
                    document.file_type,
                    document.text,
                    document.text_length,
                    document.created_at.isoformat(),
                    document.updated_at.isoformat(),
                ),
            )
            connection.commit()
        return document

    def get(self, resume_document_id: str, *, user_id: str | None = None) -> ResumeDocument | None:
        """按方法参数限定的主键或用户范围获取相关数据。"""
        with get_connection() as connection:
            init_database(connection)
            where_clause = "WHERE resume_document_id = ?"
            parameters: tuple[str, ...] = (resume_document_id,)
            if user_id is not None:
                where_clause += " AND user_id = ?"
                parameters = (resume_document_id, user_id)
            row = connection.execute(
                f"""
                SELECT
                    resume_document_id,
                    session_id,
                    source_type,
                    filename,
                    file_type,
                    text,
                    text_length,
                    created_at,
                    updated_at
                FROM resume_documents
                {where_clause}
                """,
                parameters,
            ).fetchone()
        if row is None:
            return None
        return ResumeDocument(
            resume_document_id=row["resume_document_id"],
            session_id=row["session_id"],
            source_type=row["source_type"],
            filename=row["filename"],
            file_type=row["file_type"],
            text=row["text"],
            text_length=row["text_length"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )


resume_document_repository = ResumeDocumentRepository()
