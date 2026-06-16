from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import uuid4

from app.schemas.confirmed_profile import ConfirmedProfile
from app.schemas.profile_draft import ProfileDraft
from app.storage.database import get_connection, init_database


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ConfirmedProfileRepository:
    def create_from_draft(
        self,
        *,
        session_id: str,
        resume_document_id: str,
        parsed_review_id: str,
        profile_draft: ProfileDraft,
    ) -> ConfirmedProfile:
        now = _utc_now()
        confirmed = ConfirmedProfile(
            confirmed_profile_id=str(uuid4()),
            session_id=session_id,
            resume_document_id=resume_document_id,
            parsed_review_id=parsed_review_id,
            profile_draft_id=profile_draft.profile_draft_id,
            summary=profile_draft.summary,
            target_roles=profile_draft.target_roles,
            target_directions=profile_draft.target_directions,
            core_skills=profile_draft.core_skills,
            supporting_skills=profile_draft.supporting_skills,
            search_keywords=profile_draft.search_keywords,
            preferred_locations=profile_draft.preferred_locations,
            work_arrangements=profile_draft.work_arrangements,
            strengths=profile_draft.strengths,
            risks=profile_draft.risks,
            missing_info_questions=profile_draft.missing_info_questions,
            created_at=now,
            updated_at=now,
        )
        with get_connection() as connection:
            init_database(connection)
            connection.execute(
                """
                INSERT INTO confirmed_profiles (
                    confirmed_profile_id,
                    session_id,
                    resume_document_id,
                    parsed_review_id,
                    profile_draft_id,
                    summary,
                    target_roles_json,
                    target_directions_json,
                    core_skills_json,
                    supporting_skills_json,
                    search_keywords_json,
                    preferred_locations_json,
                    work_arrangements_json,
                    strengths_json,
                    risks_json,
                    missing_info_questions_json,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    confirmed.confirmed_profile_id,
                    confirmed.session_id,
                    confirmed.resume_document_id,
                    confirmed.parsed_review_id,
                    confirmed.profile_draft_id,
                    confirmed.summary,
                    json.dumps(confirmed.target_roles),
                    json.dumps(confirmed.target_directions),
                    json.dumps(confirmed.core_skills),
                    json.dumps(confirmed.supporting_skills),
                    json.dumps(confirmed.search_keywords),
                    json.dumps(confirmed.preferred_locations),
                    json.dumps(confirmed.work_arrangements),
                    json.dumps(confirmed.strengths),
                    json.dumps(confirmed.risks),
                    json.dumps(confirmed.missing_info_questions),
                    confirmed.created_at.isoformat(),
                    confirmed.updated_at.isoformat(),
                ),
            )
            connection.commit()
        return confirmed

    def get(self, confirmed_profile_id: str) -> ConfirmedProfile | None:
        with get_connection() as connection:
            init_database(connection)
            row = connection.execute(
                """
                SELECT
                    confirmed_profile_id,
                    session_id,
                    resume_document_id,
                    parsed_review_id,
                    profile_draft_id,
                    summary,
                    target_roles_json,
                    target_directions_json,
                    core_skills_json,
                    supporting_skills_json,
                    search_keywords_json,
                    preferred_locations_json,
                    work_arrangements_json,
                    strengths_json,
                    risks_json,
                    missing_info_questions_json,
                    created_at,
                    updated_at
                FROM confirmed_profiles
                WHERE confirmed_profile_id = ?
                """,
                (confirmed_profile_id,),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_confirmed_profile(row)

    def get_current_for_session(
        self,
        *,
        session_id: str,
        profile_draft_id: str,
    ) -> ConfirmedProfile | None:
        with get_connection() as connection:
            init_database(connection)
            row = connection.execute(
                """
                SELECT
                    confirmed_profile_id,
                    session_id,
                    resume_document_id,
                    parsed_review_id,
                    profile_draft_id,
                    summary,
                    target_roles_json,
                    target_directions_json,
                    core_skills_json,
                    supporting_skills_json,
                    search_keywords_json,
                    preferred_locations_json,
                    work_arrangements_json,
                    strengths_json,
                    risks_json,
                    missing_info_questions_json,
                    created_at,
                    updated_at
                FROM confirmed_profiles
                WHERE session_id = ? AND profile_draft_id = ?
                ORDER BY updated_at DESC, created_at DESC
                LIMIT 1
                """,
                (session_id, profile_draft_id),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_confirmed_profile(row)

    @staticmethod
    def _row_to_confirmed_profile(row: object) -> ConfirmedProfile:
        return ConfirmedProfile(
            confirmed_profile_id=row["confirmed_profile_id"],
            session_id=row["session_id"],
            resume_document_id=row["resume_document_id"],
            parsed_review_id=row["parsed_review_id"],
            profile_draft_id=row["profile_draft_id"],
            summary=row["summary"],
            target_roles=json.loads(row["target_roles_json"]),
            target_directions=json.loads(row["target_directions_json"]),
            core_skills=json.loads(row["core_skills_json"]),
            supporting_skills=json.loads(row["supporting_skills_json"]),
            search_keywords=json.loads(row["search_keywords_json"]),
            preferred_locations=json.loads(row["preferred_locations_json"]),
            work_arrangements=json.loads(row["work_arrangements_json"]),
            strengths=json.loads(row["strengths_json"]),
            risks=json.loads(row["risks_json"]),
            missing_info_questions=json.loads(row["missing_info_questions_json"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )


confirmed_profile_repository = ConfirmedProfileRepository()
