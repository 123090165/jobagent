from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from app.schemas.resume_document import ResumeDocument, ResumeDocumentSourceType
from app.storage.database import get_connection, init_database


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ResumeDocumentRepository:
    def create(
        self,
        *,
        session_id: str,
        source_type: ResumeDocumentSourceType,
        text: str,
        filename: str | None = None,
        file_type: str | None = None,
    ) -> ResumeDocument:
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
                    source_type,
                    filename,
                    file_type,
                    text,
                    text_length,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    document.resume_document_id,
                    document.session_id,
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

    def get(self, resume_document_id: str) -> ResumeDocument | None:
        with get_connection() as connection:
            init_database(connection)
            row = connection.execute(
                """
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
                WHERE resume_document_id = ?
                """,
                (resume_document_id,),
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
