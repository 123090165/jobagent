"""读写 SQLite 中的搜索意图与约束，并在查询和更新时强制 user_id 隔离。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import uuid4

from app.schemas.search_mission import (
    SearchMission,
    SearchMissionInput,
    SearchMissionInterpretation,
)
from app.storage.database import get_connection, init_database


class SearchMissionRepository:
    """封装搜索意图的 SQLite 读写与模型重建。"""
    def get(self, *, user_id: str, session_id: str) -> SearchMission | None:
        """按方法参数限定的主键或用户范围获取相关数据。"""
        with get_connection() as connection:
            init_database(connection)
            row = connection.execute(
                "SELECT * FROM search_missions WHERE user_id = ? AND session_id = ?",
                (user_id, session_id),
            ).fetchone()
        return self._from_row(row) if row is not None else None

    def save_input(
        self,
        *,
        user_id: str,
        session_id: str,
        confirmed_profile_id: str,
        payload: SearchMissionInput,
    ) -> SearchMission:
        """按方法参数限定的主键或用户范围保存input。"""
        existing = self.get(user_id=user_id, session_id=session_id)
        now = datetime.now(timezone.utc)
        mission = SearchMission(
            search_mission_id=existing.search_mission_id if existing else str(uuid4()),
            user_id=user_id,
            session_id=session_id,
            confirmed_profile_id=confirmed_profile_id,
            status="draft",
            input=payload,
            mission=existing.mission if existing else SearchMissionInterpretation(),
            analysis_mode=existing.analysis_mode if existing else "deterministic",
            analysis_provider=existing.analysis_provider if existing else None,
            fallback_reason=existing.fallback_reason if existing else None,
            revision=(
                existing.revision + 1
                if existing and existing.status == "confirmed"
                else existing.revision if existing else 1
            ),
            created_at=existing.created_at if existing else now,
            updated_at=now,
            confirmed_at=None,
        )
        self._upsert(mission)
        return mission

    def save_interpretation(
        self,
        mission: SearchMission,
        *,
        interpretation: SearchMissionInterpretation,
        analysis_mode: str,
        analysis_provider: str | None,
        fallback_reason: str | None,
    ) -> SearchMission:
        """按方法参数限定的主键或用户范围保存interpretation。"""
        updated = mission.model_copy(
            update={
                "status": "review",
                "mission": interpretation,
                "analysis_mode": analysis_mode,
                "analysis_provider": analysis_provider,
                "fallback_reason": fallback_reason,
                "updated_at": datetime.now(timezone.utc),
                "confirmed_at": None,
            }
        )
        self._upsert(updated)
        return updated

    def confirm(self, mission: SearchMission) -> SearchMission:
        """按方法参数限定的主键或用户范围确认相关数据。"""
        now = datetime.now(timezone.utc)
        updated = mission.model_copy(
            update={
                "status": "confirmed",
                "revision": mission.revision,
                "updated_at": now,
                "confirmed_at": now,
            }
        )
        self._upsert(updated)
        return updated

    def _upsert(self, mission: SearchMission) -> None:
        with get_connection() as connection:
            init_database(connection)
            connection.execute(
                """
                INSERT INTO search_missions (
                    search_mission_id, user_id, session_id, confirmed_profile_id,
                    status, input_json, mission_json, analysis_mode,
                    analysis_provider, fallback_reason, revision, created_at,
                    updated_at, confirmed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, session_id) DO UPDATE SET
                    confirmed_profile_id = excluded.confirmed_profile_id,
                    status = excluded.status,
                    input_json = excluded.input_json,
                    mission_json = excluded.mission_json,
                    analysis_mode = excluded.analysis_mode,
                    analysis_provider = excluded.analysis_provider,
                    fallback_reason = excluded.fallback_reason,
                    revision = excluded.revision,
                    updated_at = excluded.updated_at,
                    confirmed_at = excluded.confirmed_at
                """,
                (
                    mission.search_mission_id,
                    mission.user_id,
                    mission.session_id,
                    mission.confirmed_profile_id,
                    mission.status,
                    json.dumps(mission.input.model_dump(mode="json")),
                    json.dumps(mission.mission.model_dump(mode="json")),
                    mission.analysis_mode,
                    mission.analysis_provider,
                    mission.fallback_reason,
                    mission.revision,
                    mission.created_at.isoformat(),
                    mission.updated_at.isoformat(),
                    mission.confirmed_at.isoformat() if mission.confirmed_at else None,
                ),
            )
            connection.commit()

    @staticmethod
    def _from_row(row: object) -> SearchMission:
        return SearchMission(
            search_mission_id=row["search_mission_id"],
            user_id=row["user_id"],
            session_id=row["session_id"],
            confirmed_profile_id=row["confirmed_profile_id"],
            status=row["status"],
            input=SearchMissionInput.model_validate(json.loads(row["input_json"])),
            mission=SearchMissionInterpretation.model_validate(json.loads(row["mission_json"])),
            analysis_mode=row["analysis_mode"],
            analysis_provider=row["analysis_provider"],
            fallback_reason=row["fallback_reason"],
            revision=row["revision"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            confirmed_at=(
                datetime.fromisoformat(row["confirmed_at"]) if row["confirmed_at"] else None
            ),
        )


search_mission_repository = SearchMissionRepository()
