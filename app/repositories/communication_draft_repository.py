from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from uuid import uuid4

from app.schemas.communication import CommunicationDraft, CommunicationDraftStatus
from app.storage.database import get_connection, init_database


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class CommunicationDraftRepository:
    def create(
        self,
        *,
        user_id: str,
        generated_content: str,
        evidence_used: list[str],
        avoid_claims: list[str],
        generation_context: dict[str, object],
        analysis_provider: str | None,
        saved_job_id: str,
        application_id: str | None = None,
        browser_capture_id: str | None = None,
    ) -> CommunicationDraft:
        now = _utc_now()
        draft = CommunicationDraft(
            draft_id=str(uuid4()),
            user_id=user_id,
            saved_job_id=saved_job_id,
            application_id=application_id,
            browser_capture_id=browser_capture_id,
            generated_content=generated_content,
            status="generated",
            evidence_used=evidence_used,
            avoid_claims=avoid_claims,
            generation_context=generation_context,
            analysis_provider=analysis_provider,
            created_at=now,
            updated_at=now,
        )
        with get_connection() as connection:
            init_database(connection)
            connection.execute(
                """
                INSERT INTO communication_drafts (
                    draft_id, user_id, saved_job_id, application_id, browser_capture_id, draft_type,
                    generated_content, approved_content, status, evidence_used_json,
                    avoid_claims_json, generation_context_json, analysis_mode,
                    analysis_provider, fallback_reason, created_at, updated_at, sent_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                self._values(draft),
            )
            connection.commit()
        return draft

    def get(
        self,
        *,
        user_id: str,
        draft_id: str,
        connection: sqlite3.Connection | None = None,
    ) -> CommunicationDraft | None:
        if connection is not None:
            row = connection.execute(
                "SELECT * FROM communication_drafts WHERE user_id = ? AND draft_id = ?",
                (user_id, draft_id),
            ).fetchone()
            return self._row_to_draft(row) if row is not None else None
        with get_connection() as owned:
            init_database(owned)
            row = owned.execute(
                "SELECT * FROM communication_drafts WHERE user_id = ? AND draft_id = ?",
                (user_id, draft_id),
            ).fetchone()
        return self._row_to_draft(row) if row is not None else None

    def latest_for_saved_job(
        self,
        *,
        user_id: str,
        saved_job_id: str,
    ) -> CommunicationDraft | None:
        with get_connection() as connection:
            init_database(connection)
            row = connection.execute(
                """
                SELECT * FROM communication_drafts
                WHERE user_id = ? AND saved_job_id = ?
                ORDER BY updated_at DESC, created_at DESC
                LIMIT 1
                """,
                (user_id, saved_job_id),
            ).fetchone()
        return self._row_to_draft(row) if row is not None else None

    def update_review(
        self,
        *,
        user_id: str,
        draft_id: str,
        approved_content: str | None,
        status: CommunicationDraftStatus | None,
    ) -> CommunicationDraft | None:
        existing = self.get(user_id=user_id, draft_id=draft_id)
        if existing is None:
            return None
        next_status = status or existing.status
        next_content = approved_content if approved_content is not None else existing.approved_content
        if next_status == "approved" and not (next_content or existing.generated_content).strip():
            raise ValueError("approved draft requires content")
        updated_at = _utc_now()
        with get_connection() as connection:
            init_database(connection)
            connection.execute(
                """
                UPDATE communication_drafts
                SET approved_content = ?, status = ?, updated_at = ?
                WHERE user_id = ? AND draft_id = ?
                """,
                (
                    next_content,
                    next_status,
                    updated_at.isoformat(),
                    user_id,
                    draft_id,
                ),
            )
            connection.commit()
        return self.get(user_id=user_id, draft_id=draft_id)

    def mark_sent(
        self,
        *,
        connection: sqlite3.Connection,
        user_id: str,
        draft_id: str,
        application_id: str,
        sent_content: str,
        sent_at: datetime,
    ) -> CommunicationDraft:
        connection.execute(
            """
            UPDATE communication_drafts
            SET application_id = ?, approved_content = ?, status = 'sent',
                updated_at = ?, sent_at = ?
            WHERE user_id = ? AND draft_id = ?
            """,
            (
                application_id,
                sent_content,
                sent_at.isoformat(),
                sent_at.isoformat(),
                user_id,
                draft_id,
            ),
        )
        draft = self.get(user_id=user_id, draft_id=draft_id, connection=connection)
        if draft is None:
            raise RuntimeError("Communication draft disappeared after update.")
        return draft

    @staticmethod
    def _values(draft: CommunicationDraft) -> tuple[object, ...]:
        return (
            draft.draft_id,
            draft.user_id,
            draft.saved_job_id,
            draft.application_id,
            draft.browser_capture_id,
            draft.draft_type,
            draft.generated_content,
            draft.approved_content,
            draft.status,
            json.dumps(draft.evidence_used),
            json.dumps(draft.avoid_claims),
            json.dumps(draft.generation_context),
            "llm",
            draft.analysis_provider,
            None,
            draft.created_at.isoformat(),
            draft.updated_at.isoformat(),
            draft.sent_at.isoformat() if draft.sent_at else None,
        )

    @staticmethod
    def _row_to_draft(row: object) -> CommunicationDraft:
        return CommunicationDraft(
            draft_id=row["draft_id"],
            user_id=row["user_id"],
            saved_job_id=row["saved_job_id"],
            application_id=row["application_id"],
            browser_capture_id=row["browser_capture_id"],
            draft_type=row["draft_type"],
            generated_content=row["generated_content"],
            approved_content=row["approved_content"],
            status=row["status"],
            evidence_used=json.loads(row["evidence_used_json"] or "[]"),
            avoid_claims=json.loads(row["avoid_claims_json"] or "[]"),
            generation_context=json.loads(row["generation_context_json"] or "{}"),
            analysis_provider=row["analysis_provider"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            sent_at=datetime.fromisoformat(row["sent_at"]) if row["sent_at"] else None,
        )


communication_draft_repository = CommunicationDraftRepository()
