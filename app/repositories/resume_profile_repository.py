from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import uuid4

from app.schemas.confirmed_profile import ConfirmedProfile
from app.schemas.resume_profile import ResumeProfile, ResumeProfileUpdateRequest
from app.storage.database import get_connection, init_database


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ResumeProfileRepository:
    def create_or_update_from_confirmed(
        self,
        *,
        user_id: str,
        confirmed_profile: ConfirmedProfile,
        raw_resume_text: str | None = None,
    ) -> ResumeProfile:
        existing = self.get_by_confirmed_profile(
            user_id=user_id,
            confirmed_profile_id=confirmed_profile.confirmed_profile_id,
        )
        if existing is not None:
            return self._update_from_confirmed(
                existing,
                confirmed_profile=confirmed_profile,
                raw_resume_text=raw_resume_text,
            )

        now = _utc_now()
        profile = ResumeProfile(
            resume_profile_id=str(uuid4()),
            user_id=user_id,
            source_session_id=confirmed_profile.session_id,
            source_confirmed_profile_id=confirmed_profile.confirmed_profile_id,
            name=_profile_name(confirmed_profile),
            summary=confirmed_profile.summary,
            target_roles=confirmed_profile.target_roles,
            target_directions=confirmed_profile.target_directions,
            core_skills=confirmed_profile.core_skills,
            supporting_skills=confirmed_profile.supporting_skills,
            search_keywords=confirmed_profile.search_keywords,
            preferred_locations=confirmed_profile.preferred_locations,
            work_arrangements=confirmed_profile.work_arrangements,
            strengths=confirmed_profile.strengths,
            risks=confirmed_profile.risks,
            profile=confirmed_profile.model_dump(mode="json"),
            raw_resume_text=raw_resume_text,
            is_default=not self._has_active_default(user_id),
            created_at=now,
            updated_at=now,
        )
        with get_connection() as connection:
            init_database(connection)
            connection.execute(
                """
                INSERT INTO resume_profiles (
                    resume_profile_id,
                    user_id,
                    source_session_id,
                    source_confirmed_profile_id,
                    name,
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
                    profile_json,
                    raw_resume_text,
                    is_default,
                    archived_at,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                self._profile_values(profile),
            )
            connection.commit()
        return profile

    def list_by_user(self, user_id: str, *, include_archived: bool = False) -> list[ResumeProfile]:
        where_clause = "WHERE user_id = ?"
        parameters: tuple[object, ...] = (user_id,)
        if not include_archived:
            where_clause += " AND archived_at IS NULL"
        with get_connection() as connection:
            init_database(connection)
            rows = connection.execute(
                f"""
                SELECT *
                FROM resume_profiles
                {where_clause}
                ORDER BY is_default DESC, updated_at DESC, created_at DESC
                """,
                parameters,
            ).fetchall()
        return [self._row_to_profile(row) for row in rows]

    def get(self, *, user_id: str, resume_profile_id: str) -> ResumeProfile | None:
        with get_connection() as connection:
            init_database(connection)
            row = connection.execute(
                """
                SELECT *
                FROM resume_profiles
                WHERE user_id = ? AND resume_profile_id = ?
                """,
                (user_id, resume_profile_id),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_profile(row)

    def get_by_confirmed_profile(
        self,
        *,
        user_id: str,
        confirmed_profile_id: str,
    ) -> ResumeProfile | None:
        with get_connection() as connection:
            init_database(connection)
            row = connection.execute(
                """
                SELECT *
                FROM resume_profiles
                WHERE user_id = ? AND source_confirmed_profile_id = ?
                """,
                (user_id, confirmed_profile_id),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_profile(row)

    def update(
        self,
        *,
        user_id: str,
        resume_profile_id: str,
        payload: ResumeProfileUpdateRequest,
    ) -> ResumeProfile | None:
        existing = self.get(user_id=user_id, resume_profile_id=resume_profile_id)
        if existing is None:
            return None

        update_data = {
            key: value
            for key, value in payload.model_dump(exclude_unset=True).items()
            if value is not None
        }
        if "name" in update_data:
            update_data["name"] = str(update_data["name"]).strip()
        if "summary" in update_data:
            update_data["summary"] = str(update_data["summary"]).strip()
        updated = existing.model_copy(update={**update_data, "updated_at": _utc_now()})
        updated.profile = {
            **updated.profile,
            "summary": updated.summary,
            "target_roles": updated.target_roles,
            "target_directions": updated.target_directions,
            "core_skills": updated.core_skills,
            "supporting_skills": updated.supporting_skills,
            "search_keywords": updated.search_keywords,
            "preferred_locations": updated.preferred_locations,
            "work_arrangements": updated.work_arrangements,
            "strengths": updated.strengths,
            "risks": updated.risks,
        }
        with get_connection() as connection:
            init_database(connection)
            connection.execute(
                """
                UPDATE resume_profiles
                SET
                    name = ?,
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
                    profile_json = ?,
                    raw_resume_text = ?,
                    updated_at = ?
                WHERE user_id = ? AND resume_profile_id = ?
                """,
                (
                    updated.name,
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
                    json.dumps(updated.profile),
                    updated.raw_resume_text,
                    updated.updated_at.isoformat(),
                    user_id,
                    resume_profile_id,
                ),
            )
            connection.commit()
        return updated

    def set_default(self, *, user_id: str, resume_profile_id: str) -> ResumeProfile | None:
        existing = self.get(user_id=user_id, resume_profile_id=resume_profile_id)
        if existing is None or existing.archived_at is not None:
            return None
        now = _utc_now().isoformat()
        with get_connection() as connection:
            init_database(connection)
            connection.execute(
                """
                UPDATE resume_profiles
                SET is_default = 0, updated_at = ?
                WHERE user_id = ?
                """,
                (now, user_id),
            )
            connection.execute(
                """
                UPDATE resume_profiles
                SET is_default = 1, updated_at = ?
                WHERE user_id = ? AND resume_profile_id = ?
                """,
                (now, user_id, resume_profile_id),
            )
            connection.commit()
        return self.get(user_id=user_id, resume_profile_id=resume_profile_id)

    def archive(self, *, user_id: str, resume_profile_id: str) -> ResumeProfile | None:
        existing = self.get(user_id=user_id, resume_profile_id=resume_profile_id)
        if existing is None:
            return None
        now = _utc_now().isoformat()
        with get_connection() as connection:
            init_database(connection)
            connection.execute(
                """
                UPDATE resume_profiles
                SET archived_at = ?, is_default = 0, updated_at = ?
                WHERE user_id = ? AND resume_profile_id = ?
                """,
                (now, now, user_id, resume_profile_id),
            )
            connection.commit()
        return self.get(user_id=user_id, resume_profile_id=resume_profile_id)

    def _update_from_confirmed(
        self,
        existing: ResumeProfile,
        *,
        confirmed_profile: ConfirmedProfile,
        raw_resume_text: str | None,
    ) -> ResumeProfile:
        payload = ResumeProfileUpdateRequest(
            summary=confirmed_profile.summary,
            target_roles=confirmed_profile.target_roles,
            target_directions=confirmed_profile.target_directions,
            core_skills=confirmed_profile.core_skills,
            supporting_skills=confirmed_profile.supporting_skills,
            search_keywords=confirmed_profile.search_keywords,
            preferred_locations=confirmed_profile.preferred_locations,
            work_arrangements=confirmed_profile.work_arrangements,
            strengths=confirmed_profile.strengths,
            risks=confirmed_profile.risks,
            raw_resume_text=raw_resume_text,
        )
        updated = self.update(
            user_id=existing.user_id,
            resume_profile_id=existing.resume_profile_id,
            payload=payload,
        )
        if updated is None:
            raise RuntimeError("Existing resume profile disappeared during update.")
        return updated

    def _has_active_default(self, user_id: str) -> bool:
        with get_connection() as connection:
            init_database(connection)
            row = connection.execute(
                """
                SELECT 1
                FROM resume_profiles
                WHERE user_id = ? AND is_default = 1 AND archived_at IS NULL
                LIMIT 1
                """,
                (user_id,),
            ).fetchone()
        return row is not None

    @staticmethod
    def _profile_values(profile: ResumeProfile) -> tuple[object, ...]:
        return (
            profile.resume_profile_id,
            profile.user_id,
            profile.source_session_id,
            profile.source_confirmed_profile_id,
            profile.name,
            profile.summary,
            json.dumps(profile.target_roles),
            json.dumps(profile.target_directions),
            json.dumps(profile.core_skills),
            json.dumps(profile.supporting_skills),
            json.dumps(profile.search_keywords),
            json.dumps(profile.preferred_locations),
            json.dumps(profile.work_arrangements),
            json.dumps(profile.strengths),
            json.dumps(profile.risks),
            json.dumps(profile.profile),
            profile.raw_resume_text,
            1 if profile.is_default else 0,
            profile.archived_at.isoformat() if profile.archived_at else None,
            profile.created_at.isoformat(),
            profile.updated_at.isoformat(),
        )

    @staticmethod
    def _row_to_profile(row: object) -> ResumeProfile:
        return ResumeProfile(
            resume_profile_id=row["resume_profile_id"],
            user_id=row["user_id"],
            source_session_id=row["source_session_id"],
            source_confirmed_profile_id=row["source_confirmed_profile_id"],
            name=row["name"],
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
            profile=json.loads(row["profile_json"]),
            raw_resume_text=row["raw_resume_text"],
            is_default=bool(row["is_default"]),
            archived_at=(
                datetime.fromisoformat(row["archived_at"])
                if row["archived_at"] is not None
                else None
            ),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )


def _profile_name(confirmed_profile: ConfirmedProfile) -> str:
    if confirmed_profile.target_roles:
        return f"{confirmed_profile.target_roles[0]} profile"
    return "Resume profile"


resume_profile_repository = ResumeProfileRepository()
