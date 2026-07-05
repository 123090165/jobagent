from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import uuid4

from app.schemas.profile_draft import ProfileDraft, UpdateProfileDraftRequest
from app.storage.database import LOCAL_USER_ID, get_connection, init_database


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ProfileDraftRepository:
    def create(
        self,
        *,
        session_id: str,
        parsed_review_id: str,
        summary: str,
        target_roles: list[str],
        target_directions: list[str],
        core_skills: list[str],
        supporting_skills: list[str],
        search_keywords: list[str],
        preferred_locations: list[str],
        work_arrangements: list[str],
        strengths: list[str],
        risks: list[str],
        missing_info_questions: list[str],
        user_id: str = LOCAL_USER_ID,
    ) -> ProfileDraft:
        now = _utc_now()
        draft = ProfileDraft(
            profile_draft_id=str(uuid4()),
            session_id=session_id,
            parsed_review_id=parsed_review_id,
            summary=summary,
            target_roles=target_roles,
            target_directions=target_directions,
            core_skills=core_skills,
            supporting_skills=supporting_skills,
            search_keywords=search_keywords,
            preferred_locations=preferred_locations,
            work_arrangements=work_arrangements,
            strengths=strengths,
            risks=risks,
            missing_info_questions=missing_info_questions,
            created_at=now,
            updated_at=now,
        )
        with get_connection() as connection:
            init_database(connection)
            connection.execute(
                """
                INSERT INTO profile_drafts (
                    profile_draft_id,
                    session_id,
                    parsed_review_id,
                    user_id,
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
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    draft.profile_draft_id,
                    draft.session_id,
                    draft.parsed_review_id,
                    user_id,
                    draft.summary,
                    json.dumps(draft.target_roles),
                    json.dumps(draft.target_directions),
                    json.dumps(draft.core_skills),
                    json.dumps(draft.supporting_skills),
                    json.dumps(draft.search_keywords),
                    json.dumps(draft.preferred_locations),
                    json.dumps(draft.work_arrangements),
                    json.dumps(draft.strengths),
                    json.dumps(draft.risks),
                    json.dumps(draft.missing_info_questions),
                    draft.created_at.isoformat(),
                    draft.updated_at.isoformat(),
                ),
            )
            connection.commit()
        return draft

    def get(self, profile_draft_id: str, *, user_id: str | None = None) -> ProfileDraft | None:
        with get_connection() as connection:
            init_database(connection)
            where_clause = "WHERE profile_draft_id = ?"
            parameters: tuple[str, ...] = (profile_draft_id,)
            if user_id is not None:
                where_clause += " AND user_id = ?"
                parameters = (profile_draft_id, user_id)
            row = connection.execute(
                f"""
                SELECT
                    profile_draft_id,
                    session_id,
                    parsed_review_id,
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
                FROM profile_drafts
                {where_clause}
                """,
                parameters,
            ).fetchone()
        if row is None:
            return None
        return self._row_to_profile_draft(row)

    def get_current_for_session(
        self,
        *,
        session_id: str,
        parsed_review_id: str,
        user_id: str | None = None,
    ) -> ProfileDraft | None:
        with get_connection() as connection:
            init_database(connection)
            where_clause = "WHERE session_id = ? AND parsed_review_id = ?"
            parameters: tuple[str, ...] = (session_id, parsed_review_id)
            if user_id is not None:
                where_clause += " AND user_id = ?"
                parameters = (session_id, parsed_review_id, user_id)
            row = connection.execute(
                f"""
                SELECT
                    profile_draft_id,
                    session_id,
                    parsed_review_id,
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
                FROM profile_drafts
                {where_clause}
                ORDER BY updated_at DESC, created_at DESC
                LIMIT 1
                """,
                parameters,
            ).fetchone()
        if row is None:
            return None
        return self._row_to_profile_draft(row)

    def update(
        self,
        profile_draft_id: str,
        payload: UpdateProfileDraftRequest,
        *,
        user_id: str | None = None,
    ) -> ProfileDraft | None:
        existing = self.get(profile_draft_id, user_id=user_id)
        if existing is None:
            return None

        updated = existing.model_copy(
            update={
                "summary": payload.summary if payload.summary is not None else existing.summary,
                "target_roles": (
                    payload.target_roles if payload.target_roles is not None else existing.target_roles
                ),
                "target_directions": (
                    payload.target_directions
                    if payload.target_directions is not None
                    else existing.target_directions
                ),
                "core_skills": (
                    payload.core_skills if payload.core_skills is not None else existing.core_skills
                ),
                "supporting_skills": (
                    payload.supporting_skills
                    if payload.supporting_skills is not None
                    else existing.supporting_skills
                ),
                "search_keywords": (
                    payload.search_keywords
                    if payload.search_keywords is not None
                    else existing.search_keywords
                ),
                "preferred_locations": (
                    payload.preferred_locations
                    if payload.preferred_locations is not None
                    else existing.preferred_locations
                ),
                "work_arrangements": (
                    payload.work_arrangements
                    if payload.work_arrangements is not None
                    else existing.work_arrangements
                ),
                "strengths": payload.strengths if payload.strengths is not None else existing.strengths,
                "risks": payload.risks if payload.risks is not None else existing.risks,
                "missing_info_questions": (
                    payload.missing_info_questions
                    if payload.missing_info_questions is not None
                    else existing.missing_info_questions
                ),
                "updated_at": _utc_now(),
            }
        )

        with get_connection() as connection:
            init_database(connection)
            connection.execute(
                """
                UPDATE profile_drafts
                SET
                    summary = ?,
                    target_roles_json = ?,
                    target_directions_json = ?,
                    core_skills_json = ?,
                    supporting_skills_json = ?,
                    search_keywords_json = ?,
                    preferred_locations_json = ?,
                    work_arrangements_json = ?,
                    strengths_json = ?,
                    risks_json = ?,
                    missing_info_questions_json = ?,
                    updated_at = ?
                WHERE profile_draft_id = ?
                """,
                (
                    updated.summary,
                    json.dumps(updated.target_roles),
                    json.dumps(updated.target_directions),
                    json.dumps(updated.core_skills),
                    json.dumps(updated.supporting_skills),
                    json.dumps(updated.search_keywords),
                    json.dumps(updated.preferred_locations),
                    json.dumps(updated.work_arrangements),
                    json.dumps(updated.strengths),
                    json.dumps(updated.risks),
                    json.dumps(updated.missing_info_questions),
                    updated.updated_at.isoformat(),
                    profile_draft_id,
                ),
            )
            connection.commit()
        return updated

    @staticmethod
    def _row_to_profile_draft(row: object) -> ProfileDraft:
        return ProfileDraft(
            profile_draft_id=row["profile_draft_id"],
            session_id=row["session_id"],
            parsed_review_id=row["parsed_review_id"],
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


profile_draft_repository = ProfileDraftRepository()
