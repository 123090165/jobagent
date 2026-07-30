"""读写 SQLite 中的职位搜索 run、结果与 trace，并在查询和更新时强制 user_id 隔离。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import uuid4

from app.schemas.job_search import (
    JobSearchItem,
    JobSearchResult,
    JobSearchRun,
    JobSearchTraceStep,
)
from app.services.job_search_providers import selected_sources_from_provider_name
from app.storage.database import LOCAL_USER_ID, get_connection, init_database


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class JobSearchRepository:
    """封装职位搜索的 SQLite 读写与模型重建。"""
    def create(
        self,
        *,
        session_id: str,
        confirmed_profile_id: str,
        resume_profile_id: str | None = None,
        query: str,
        locations: list[str],
        target_roles: list[str],
        keywords: list[str],
        results: list[JobSearchResult],
        search_mission_id: str | None = None,
        search_mission_revision: int | None = None,
        mission_constraints: list[str] | None = None,
        mission_excluded_roles: list[str] | None = None,
        mission_ranking_priorities: list[str] | None = None,
        user_id: str = LOCAL_USER_ID,
    ) -> JobSearchRun:
        """按方法参数限定的主键或用户范围创建相关数据。"""
        return self._create_run(
            session_id=session_id,
            confirmed_profile_id=confirmed_profile_id,
            resume_profile_id=resume_profile_id,
            user_id=user_id,
            query=query,
            locations=locations,
            target_roles=target_roles,
            keywords=keywords,
            search_mode="local_mock",
            llm_enabled=False,
            search_provider="local_mock",
            status="completed",
            error_message=None,
            results=results,
            search_mission_id=search_mission_id,
            search_mission_revision=search_mission_revision,
            mission_constraints=mission_constraints or [],
            mission_excluded_roles=mission_excluded_roles or [],
            mission_ranking_priorities=mission_ranking_priorities or [],
        )

    def create_pending(
        self,
        *,
        session_id: str,
        confirmed_profile_id: str,
        resume_profile_id: str | None = None,
        query: str,
        locations: list[str],
        target_roles: list[str],
        keywords: list[str],
        search_mode: str,
        llm_enabled: bool,
        search_provider: str | None,
        search_mission_id: str | None = None,
        search_mission_revision: int | None = None,
        mission_constraints: list[str] | None = None,
        mission_excluded_roles: list[str] | None = None,
        mission_ranking_priorities: list[str] | None = None,
        user_id: str = LOCAL_USER_ID,
    ) -> JobSearchRun:
        """按方法参数限定的主键或用户范围创建pending。"""
        return self._create_run(
            session_id=session_id,
            confirmed_profile_id=confirmed_profile_id,
            resume_profile_id=resume_profile_id,
            user_id=user_id,
            query=query,
            locations=locations,
            target_roles=target_roles,
            keywords=keywords,
            search_mode=search_mode,
            llm_enabled=llm_enabled,
            search_provider=search_provider,
            status="pending",
            error_message=None,
            results=[],
            search_mission_id=search_mission_id,
            search_mission_revision=search_mission_revision,
            mission_constraints=mission_constraints or [],
            mission_excluded_roles=mission_excluded_roles or [],
            mission_ranking_priorities=mission_ranking_priorities or [],
        )

    def mark_running(self, run_id: str) -> JobSearchRun | None:
        """按方法参数限定的主键或用户范围标记running。"""
        return self._update_run_state(run_id, status="running", error_message=None)

    def complete_run(self, run_id: str, results: list[JobSearchResult]) -> JobSearchRun | None:
        """按方法参数限定的主键或用户范围完成运行记录。"""
        now = _utc_now()
        with get_connection() as connection:
            init_database(connection)
            cursor = connection.execute(
                """
                UPDATE job_search_runs
                SET
                    status = ?,
                    error_message = NULL,
                    results_json = ?,
                    updated_at = ?
                WHERE job_search_run_id = ?
                """,
                (
                    "completed",
                    json.dumps([item.model_dump(mode="json") for item in results]),
                    now.isoformat(),
                    run_id,
                ),
            )
            connection.commit()
            if cursor.rowcount == 0:
                return None
        return self.get(run_id)

    def upsert_items(
        self,
        *,
        user_id: str,
        run_id: str,
        items: list[JobSearchItem],
        replace_existing: bool = False,
    ) -> None:
        """按方法参数限定的主键或用户范围新增或更新items。"""
        with get_connection() as connection:
            init_database(connection)
            if replace_existing:
                connection.execute(
                    "DELETE FROM job_search_items WHERE user_id = ? AND job_search_run_id = ?",
                    (user_id, run_id),
                )
            if items:
                connection.executemany(
                    """
                INSERT INTO job_search_items (
                    job_search_item_id,
                    user_id,
                    job_search_run_id,
                    stable_candidate_key,
                    rank,
                    stage,
                    candidate_json,
                    result_json,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, job_search_run_id, stable_candidate_key)
                DO UPDATE SET
                    rank = excluded.rank,
                    stage = excluded.stage,
                    candidate_json = excluded.candidate_json,
                    result_json = excluded.result_json,
                    updated_at = excluded.updated_at
                """,
                    [
                        (
                            item.job_search_item_id,
                            user_id,
                            run_id,
                            item.stable_candidate_key,
                            item.rank,
                            item.stage,
                            json.dumps(item.candidate.model_dump(mode="json")),
                            (
                                json.dumps(item.result.model_dump(mode="json"))
                                if item.result is not None
                                else None
                            ),
                            item.created_at.isoformat(),
                            item.updated_at.isoformat(),
                        )
                        for item in items
                    ],
                )
            connection.commit()

    def list_items(
        self,
        *,
        user_id: str,
        run_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[JobSearchItem]:
        """按方法参数限定的主键或用户范围列出items。"""
        with get_connection() as connection:
            init_database(connection)
            rows = connection.execute(
                """
                SELECT *
                FROM job_search_items
                WHERE user_id = ? AND job_search_run_id = ?
                ORDER BY rank ASC, created_at ASC
                LIMIT ? OFFSET ?
                """,
                (user_id, run_id, limit, offset),
            ).fetchall()
        return [self._row_to_job_search_item(row) for row in rows]

    def count_items(self, *, user_id: str, run_id: str) -> int:
        """按方法参数限定的主键或用户范围处理countitems。"""
        with get_connection() as connection:
            init_database(connection)
            row = connection.execute(
                """
                SELECT COUNT(*) AS item_count
                FROM job_search_items
                WHERE user_id = ? AND job_search_run_id = ?
                """,
                (user_id, run_id),
            ).fetchone()
        return int(row["item_count"]) if row is not None else 0

    def get_item(
        self,
        *,
        user_id: str,
        run_id: str,
        item_id: str,
    ) -> JobSearchItem | None:
        """按方法参数限定的主键或用户范围获取条目。"""
        with get_connection() as connection:
            init_database(connection)
            row = connection.execute(
                """
                SELECT *
                FROM job_search_items
                WHERE user_id = ? AND job_search_run_id = ? AND job_search_item_id = ?
                """,
                (user_id, run_id, item_id),
            ).fetchone()
        return self._row_to_job_search_item(row) if row is not None else None

    def fail_run(self, run_id: str, error_message: str) -> JobSearchRun | None:
        """按方法参数限定的主键或用户范围标记失败运行记录。"""
        return self._update_run_state(run_id, status="failed", error_message=error_message)

    def get(self, job_search_run_id: str, *, user_id: str | None = None) -> JobSearchRun | None:
        """按方法参数限定的主键或用户范围获取相关数据。"""
        with get_connection() as connection:
            init_database(connection)
            where_clause = "WHERE job_search_run_id = ?"
            parameters: tuple[str, ...] = (job_search_run_id,)
            if user_id is not None:
                where_clause += " AND user_id = ?"
                parameters = (job_search_run_id, user_id)
            row = connection.execute(
                f"""
                SELECT
                    job_search_run_id,
                    session_id,
                    confirmed_profile_id,
                    resume_profile_id,
                    query,
                    locations_json,
                    target_roles_json,
                    keywords_json,
                    search_mode,
                    llm_enabled,
                    search_provider,
                    search_mission_id,
                    search_mission_revision,
                    mission_constraints_json,
                    mission_excluded_roles_json,
                    mission_ranking_priorities_json,
                    status,
                    error_message,
                    results_json,
                    created_at,
                    updated_at
                FROM job_search_runs
                {where_clause}
                """,
                parameters,
            ).fetchone()
        if row is None:
            return None
        return self._row_to_job_search_run(row)

    def list_recent_by_session(
        self,
        session_id: str,
        *,
        user_id: str | None = None,
    ) -> list[JobSearchRun]:
        """按方法参数限定的主键或用户范围列出recentby会话。"""
        with get_connection() as connection:
            init_database(connection)
            where_clause = "WHERE session_id = ?"
            parameters: tuple[str, ...] = (session_id,)
            if user_id is not None:
                where_clause += " AND user_id = ?"
                parameters = (session_id, user_id)
            rows = connection.execute(
                f"""
                SELECT
                    job_search_run_id,
                    session_id,
                    confirmed_profile_id,
                    resume_profile_id,
                    query,
                    locations_json,
                    target_roles_json,
                    keywords_json,
                    search_mode,
                    llm_enabled,
                    search_provider,
                    search_mission_id,
                    search_mission_revision,
                    mission_constraints_json,
                    mission_excluded_roles_json,
                    mission_ranking_priorities_json,
                    status,
                    error_message,
                    results_json,
                    created_at,
                    updated_at
                FROM job_search_runs
                {where_clause}
                ORDER BY updated_at DESC, created_at DESC
                """,
                parameters,
            ).fetchall()
        return [self._row_to_job_search_run(row) for row in rows]

    def list_recent_by_user(
        self,
        user_id: str,
        *,
        limit: int = 100,
    ) -> list[JobSearchRun]:
        """按方法参数限定的主键或用户范围列出recentby用户。"""
        with get_connection() as connection:
            init_database(connection)
            rows = connection.execute(
                """
                SELECT
                    job_search_run_id,
                    session_id,
                    confirmed_profile_id,
                    resume_profile_id,
                    query,
                    locations_json,
                    target_roles_json,
                    keywords_json,
                    search_mode,
                    llm_enabled,
                    search_provider,
                    search_mission_id,
                    search_mission_revision,
                    mission_constraints_json,
                    mission_excluded_roles_json,
                    mission_ranking_priorities_json,
                    status,
                    error_message,
                    results_json,
                    created_at,
                    updated_at
                FROM job_search_runs
                WHERE user_id = ?
                ORDER BY updated_at DESC, created_at DESC
                LIMIT ?
                """,
                (user_id, limit),
            ).fetchall()
        return [self._row_to_job_search_run(row) for row in rows]

    def delete(self, *, user_id: str, run_id: str) -> bool:
        """按方法参数限定的主键或用户范围删除相关数据。"""
        if self.get(run_id, user_id=user_id) is None:
            return False
        with get_connection() as connection:
            init_database(connection)
            connection.execute(
                """
                UPDATE saved_job_analyses
                SET source_job_search_run_id = NULL
                WHERE user_id = ? AND source_job_search_run_id = ?
                """,
                (user_id, run_id),
            )
            connection.execute(
                """
                UPDATE saved_job_origins
                SET job_search_run_id = NULL
                WHERE user_id = ? AND job_search_run_id = ?
                """,
                (user_id, run_id),
            )
            connection.execute(
                "DELETE FROM job_search_result_feedback WHERE user_id = ? AND job_search_run_id = ?",
                (user_id, run_id),
            )
            connection.execute(
                "DELETE FROM job_search_items WHERE user_id = ? AND job_search_run_id = ?",
                (user_id, run_id),
            )
            connection.execute(
                "DELETE FROM job_search_trace_steps WHERE job_search_run_id = ?",
                (run_id,),
            )
            cursor = connection.execute(
                "DELETE FROM job_search_runs WHERE user_id = ? AND job_search_run_id = ?",
                (user_id, run_id),
            )
            connection.commit()
        return cursor.rowcount > 0

    def create_trace_step(
        self,
        *,
        job_search_run_id: str,
        step_index: int,
        name: str,
        status: str = "pending",
        mode: str = "deterministic",
        summary: str = "Queued.",
        fallback_reason: str | None = None,
        guardrails: list[str] | None = None,
        quality_warnings: list[str] | None = None,
        details: dict[str, object] | None = None,
    ) -> JobSearchTraceStep:
        """按方法参数限定的主键或用户范围创建执行追踪阶段。"""
        now = _utc_now()
        step = JobSearchTraceStep(
            step_id=str(uuid4()),
            job_search_run_id=job_search_run_id,
            step_index=step_index,
            name=name,
            status=status,
            mode=mode,
            summary=summary,
            fallback_reason=fallback_reason,
            guardrails=guardrails or [],
            quality_warnings=quality_warnings or [],
            details=details or {},
            started_at=None,
            completed_at=None,
            duration_ms=None,
        )
        with get_connection() as connection:
            init_database(connection)
            connection.execute(
                """
                INSERT INTO job_search_trace_steps (
                    step_id,
                    job_search_run_id,
                    step_index,
                    name,
                    status,
                    mode,
                    summary,
                    fallback_reason,
                    guardrails_json,
                    quality_warnings_json,
                    details_json,
                    started_at,
                    completed_at,
                    duration_ms,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    step.step_id,
                    step.job_search_run_id,
                    step.step_index,
                    step.name,
                    step.status,
                    step.mode,
                    step.summary,
                    step.fallback_reason,
                    json.dumps(step.guardrails),
                    json.dumps(step.quality_warnings),
                    json.dumps(step.details),
                    None,
                    None,
                    None,
                    now.isoformat(),
                    now.isoformat(),
                ),
            )
            connection.commit()
        return step

    def mark_trace_step_running(
        self,
        step_id: str,
        *,
        mode: str,
        summary: str,
        guardrails: list[str] | None = None,
        quality_warnings: list[str] | None = None,
        details: dict[str, object] | None = None,
    ) -> JobSearchTraceStep | None:
        """按方法参数限定的主键或用户范围标记执行追踪阶段running。"""
        now = _utc_now()
        with get_connection() as connection:
            init_database(connection)
            cursor = connection.execute(
                """
                UPDATE job_search_trace_steps
                SET
                    status = ?,
                    mode = ?,
                    summary = ?,
                    fallback_reason = NULL,
                    guardrails_json = ?,
                    quality_warnings_json = ?,
                    details_json = ?,
                    started_at = COALESCE(started_at, ?),
                    updated_at = ?
                WHERE step_id = ?
                """,
                (
                    "running",
                    mode,
                    summary,
                    json.dumps(guardrails or []),
                    json.dumps(quality_warnings or []),
                    json.dumps(details or {}),
                    now.isoformat(),
                    now.isoformat(),
                    step_id,
                ),
            )
            connection.commit()
            if cursor.rowcount == 0:
                return None
        return self.get_trace_step(step_id)

    def complete_trace_step(
        self,
        step_id: str,
        *,
        mode: str,
        summary: str,
        fallback_reason: str | None = None,
        guardrails: list[str] | None = None,
        quality_warnings: list[str] | None = None,
        details: dict[str, object] | None = None,
    ) -> JobSearchTraceStep | None:
        """按方法参数限定的主键或用户范围完成执行追踪阶段。"""
        return self._finalize_trace_step(
            step_id,
            status="completed",
            mode=mode,
            summary=summary,
            fallback_reason=fallback_reason,
            guardrails=guardrails,
            quality_warnings=quality_warnings,
            details=details,
        )

    def fail_trace_step(
        self,
        step_id: str,
        *,
        mode: str,
        summary: str,
        fallback_reason: str | None = None,
        guardrails: list[str] | None = None,
        quality_warnings: list[str] | None = None,
        details: dict[str, object] | None = None,
    ) -> JobSearchTraceStep | None:
        """按方法参数限定的主键或用户范围标记失败执行追踪阶段。"""
        return self._finalize_trace_step(
            step_id,
            status="failed",
            mode=mode,
            summary=summary,
            fallback_reason=fallback_reason,
            guardrails=guardrails,
            quality_warnings=quality_warnings,
            details=details,
        )

    def list_trace_steps(self, run_id: str) -> list[JobSearchTraceStep]:
        """按方法参数限定的主键或用户范围列出执行追踪steps。"""
        with get_connection() as connection:
            init_database(connection)
            rows = connection.execute(
                """
                SELECT
                    step_id,
                    job_search_run_id,
                    step_index,
                    name,
                    status,
                    mode,
                    summary,
                    fallback_reason,
                    guardrails_json,
                    quality_warnings_json,
                    details_json,
                    started_at,
                    completed_at,
                    duration_ms
                FROM job_search_trace_steps
                WHERE job_search_run_id = ?
                ORDER BY step_index ASC, created_at ASC
                """,
                (run_id,),
            ).fetchall()
        return [self._row_to_job_search_trace_step(row) for row in rows]

    def get_trace_step(self, step_id: str) -> JobSearchTraceStep | None:
        """按方法参数限定的主键或用户范围获取执行追踪阶段。"""
        with get_connection() as connection:
            init_database(connection)
            row = connection.execute(
                """
                SELECT
                    step_id,
                    job_search_run_id,
                    step_index,
                    name,
                    status,
                    mode,
                    summary,
                   fallback_reason,
                   guardrails_json,
                   quality_warnings_json,
                    details_json,
                   started_at,
                   completed_at,
                    duration_ms
                FROM job_search_trace_steps
                WHERE step_id = ?
                """,
                (step_id,),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_job_search_trace_step(row)

    def _create_run(
        self,
        *,
        session_id: str,
        confirmed_profile_id: str,
        resume_profile_id: str | None,
        user_id: str,
        query: str,
        locations: list[str],
        target_roles: list[str],
        keywords: list[str],
        search_mode: str,
        llm_enabled: bool,
        search_provider: str | None,
        status: str,
        error_message: str | None,
        results: list[JobSearchResult],
        search_mission_id: str | None,
        search_mission_revision: int | None,
        mission_constraints: list[str],
        mission_excluded_roles: list[str],
        mission_ranking_priorities: list[str],
    ) -> JobSearchRun:
        now = _utc_now()
        run = JobSearchRun(
            job_search_run_id=str(uuid4()),
            session_id=session_id,
            confirmed_profile_id=confirmed_profile_id,
            resume_profile_id=resume_profile_id,
            query=query,
            locations=locations,
            target_roles=target_roles,
            keywords=keywords,
            search_mode=search_mode,
            llm_enabled=llm_enabled,
            search_provider=search_provider,
            selected_sources=selected_sources_from_provider_name(search_provider),
            search_mission_id=search_mission_id,
            search_mission_revision=search_mission_revision,
            mission_constraints=mission_constraints,
            mission_excluded_roles=mission_excluded_roles,
            mission_ranking_priorities=mission_ranking_priorities,
            status=status,
            error_message=error_message,
            results=results,
            created_at=now,
            updated_at=now,
        )
        with get_connection() as connection:
            init_database(connection)
            connection.execute(
                """
                INSERT INTO job_search_runs (
                    job_search_run_id,
                    session_id,
                    confirmed_profile_id,
                    resume_profile_id,
                    user_id,
                    query,
                    locations_json,
                    target_roles_json,
                    keywords_json,
                    search_mode,
                    llm_enabled,
                    search_provider,
                    search_mission_id,
                    search_mission_revision,
                    mission_constraints_json,
                    mission_excluded_roles_json,
                    mission_ranking_priorities_json,
                    status,
                    error_message,
                    results_json,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run.job_search_run_id,
                    run.session_id,
                    run.confirmed_profile_id,
                    run.resume_profile_id,
                    user_id,
                    run.query,
                    json.dumps(run.locations),
                    json.dumps(run.target_roles),
                    json.dumps(run.keywords),
                    run.search_mode,
                    1 if run.llm_enabled else 0,
                    run.search_provider,
                    run.search_mission_id,
                    run.search_mission_revision,
                    json.dumps(run.mission_constraints),
                    json.dumps(run.mission_excluded_roles),
                    json.dumps(run.mission_ranking_priorities),
                    run.status,
                    run.error_message,
                    json.dumps([item.model_dump(mode="json") for item in run.results]),
                    run.created_at.isoformat(),
                    run.updated_at.isoformat(),
                ),
            )
            connection.commit()
        return run

    def _update_run_state(
        self,
        run_id: str,
        *,
        status: str,
        error_message: str | None,
    ) -> JobSearchRun | None:
        now = _utc_now()
        with get_connection() as connection:
            init_database(connection)
            cursor = connection.execute(
                """
                UPDATE job_search_runs
                SET
                    status = ?,
                    error_message = ?,
                    updated_at = ?
                WHERE job_search_run_id = ?
                """,
                (
                    status,
                    error_message,
                    now.isoformat(),
                    run_id,
                ),
            )
            connection.commit()
            if cursor.rowcount == 0:
                return None
        return self.get(run_id)

    def _finalize_trace_step(
        self,
        step_id: str,
        *,
        status: str,
        mode: str,
        summary: str,
        fallback_reason: str | None,
        guardrails: list[str] | None,
        quality_warnings: list[str] | None,
        details: dict[str, object] | None,
    ) -> JobSearchTraceStep | None:
        existing = self.get_trace_step(step_id)
        if existing is None:
            return None

        now = _utc_now()
        started_at = existing.started_at or now
        duration_ms = max(0.0, (now - started_at).total_seconds() * 1000.0)
        with get_connection() as connection:
            init_database(connection)
            connection.execute(
                """
                UPDATE job_search_trace_steps
                SET
                    status = ?,
                    mode = ?,
                    summary = ?,
                    fallback_reason = ?,
                    guardrails_json = ?,
                    quality_warnings_json = ?,
                    details_json = ?,
                    started_at = ?,
                    completed_at = ?,
                    duration_ms = ?,
                    updated_at = ?
                WHERE step_id = ?
                """,
                (
                    status,
                    mode,
                    summary,
                    fallback_reason,
                    json.dumps(guardrails or []),
                    json.dumps(quality_warnings or []),
                    json.dumps(details if details is not None else existing.details),
                    started_at.isoformat(),
                    now.isoformat(),
                    duration_ms,
                    now.isoformat(),
                    step_id,
                ),
            )
            connection.commit()
        return self.get_trace_step(step_id)

    @staticmethod
    def _row_to_job_search_run(row: object) -> JobSearchRun:
        return JobSearchRun(
            job_search_run_id=row["job_search_run_id"],
            session_id=row["session_id"],
            confirmed_profile_id=row["confirmed_profile_id"],
            resume_profile_id=row["resume_profile_id"],
            query=row["query"],
            locations=json.loads(row["locations_json"]),
            target_roles=json.loads(row["target_roles_json"]),
            keywords=json.loads(row["keywords_json"]),
            search_mode=row["search_mode"],
            llm_enabled=bool(row["llm_enabled"]),
            search_provider=row["search_provider"],
            selected_sources=selected_sources_from_provider_name(row["search_provider"]),
            search_mission_id=row["search_mission_id"],
            search_mission_revision=row["search_mission_revision"],
            mission_constraints=json.loads(row["mission_constraints_json"] or "[]"),
            mission_excluded_roles=json.loads(row["mission_excluded_roles_json"] or "[]"),
            mission_ranking_priorities=json.loads(row["mission_ranking_priorities_json"] or "[]"),
            status=row["status"],
            error_message=row["error_message"],
            results=[
                JobSearchResult.model_validate(item)
                for item in json.loads(row["results_json"])
            ],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    @staticmethod
    def _row_to_job_search_item(row: object) -> JobSearchItem:
        return JobSearchItem(
            job_search_item_id=row["job_search_item_id"],
            job_search_run_id=row["job_search_run_id"],
            stable_candidate_key=row["stable_candidate_key"],
            rank=row["rank"],
            stage=row["stage"],
            candidate=json.loads(row["candidate_json"]),
            result=(
                JobSearchResult.model_validate(json.loads(row["result_json"]))
                if row["result_json"]
                else None
            ),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    @staticmethod
    def _row_to_job_search_trace_step(row: object) -> JobSearchTraceStep:
        return JobSearchTraceStep(
            step_id=row["step_id"],
            job_search_run_id=row["job_search_run_id"],
            step_index=row["step_index"],
            name=row["name"],
            status=row["status"],
            mode=row["mode"],
            summary=row["summary"],
            fallback_reason=row["fallback_reason"],
            guardrails=json.loads(row["guardrails_json"]),
            quality_warnings=json.loads(row["quality_warnings_json"]),
            details=json.loads(row["details_json"] or "{}"),
            started_at=datetime.fromisoformat(row["started_at"]) if row["started_at"] else None,
            completed_at=(
                datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None
            ),
            duration_ms=row["duration_ms"],
        )


job_search_repository = JobSearchRepository()
