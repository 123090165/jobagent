"""读写 SQLite 中的确认画像，并在查询和更新时强制 user_id 隔离。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import uuid4

from app.schemas.confirmed_profile import ConfirmedProfile
from app.schemas.profile_draft import ProfileDraft
from app.storage.database import LOCAL_USER_ID, get_connection, init_database


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ConfirmedProfileRepository:
    """封装已确认画像的 SQLite 读写与模型重建。"""
    def create_from_draft(
        self,
        *,
        session_id: str,
        resume_document_id: str,
        parsed_review_id: str,
        profile_draft: ProfileDraft,
        user_id: str = LOCAL_USER_ID,
    ) -> ConfirmedProfile:
        """按方法参数限定的主键或用户范围创建from草稿。"""
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
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    confirmed.confirmed_profile_id,
                    confirmed.session_id,
                    confirmed.resume_document_id,
                    confirmed.parsed_review_id,
                    confirmed.profile_draft_id,
                    user_id,
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

    def get(self, confirmed_profile_id: str, *, user_id: str | None = None) -> ConfirmedProfile | None:
        """按方法参数限定的主键或用户范围获取相关数据。"""
        with get_connection() as connection:
            init_database(connection)
            where_clause = "WHERE confirmed_profile_id = ?"
            parameters: tuple[str, ...] = (confirmed_profile_id,)
            if user_id is not None:
                where_clause += " AND user_id = ?"
                parameters = (confirmed_profile_id, user_id)
            row = connection.execute(
                f"""
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
                {where_clause}
                """,
                parameters,
            ).fetchone()
        if row is None:
            return None
        return self._row_to_confirmed_profile(row)

    def get_current_for_session(
        self,
        *,
        session_id: str,
        profile_draft_id: str,
        user_id: str | None = None,
    ) -> ConfirmedProfile | None:
        """按方法参数限定的主键或用户范围获取currentfor会话。"""
        with get_connection() as connection:
            init_database(connection)
            where_clause = "WHERE session_id = ? AND profile_draft_id = ?"
            parameters: tuple[str, ...] = (session_id, profile_draft_id)
            if user_id is not None:
                where_clause += " AND user_id = ?"
                parameters = (session_id, profile_draft_id, user_id)
            row = connection.execute(
                f"""
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
                {where_clause}
                ORDER BY updated_at DESC, created_at DESC
                LIMIT 1
                """,
                parameters,
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
