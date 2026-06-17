from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import uuid4

from app.schemas.job_search import JobSearchResult, JobSearchRun
from app.storage.database import get_connection, init_database


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class JobSearchRepository:
    def create(
        self,
        *,
        session_id: str,
        confirmed_profile_id: str,
        query: str,
        locations: list[str],
        target_roles: list[str],
        keywords: list[str],
        results: list[JobSearchResult],
    ) -> JobSearchRun:
        now = _utc_now()
        run = JobSearchRun(
            job_search_run_id=str(uuid4()),
            session_id=session_id,
            confirmed_profile_id=confirmed_profile_id,
            query=query,
            locations=locations,
            target_roles=target_roles,
            keywords=keywords,
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
                    query,
                    locations_json,
                    target_roles_json,
                    keywords_json,
                    status,
                    results_json,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run.job_search_run_id,
                    run.session_id,
                    run.confirmed_profile_id,
                    run.query,
                    json.dumps(run.locations),
                    json.dumps(run.target_roles),
                    json.dumps(run.keywords),
                    run.status,
                    json.dumps([item.model_dump(mode="json") for item in run.results]),
                    run.created_at.isoformat(),
                    run.updated_at.isoformat(),
                ),
            )
            connection.commit()
        return run

    def get(self, job_search_run_id: str) -> JobSearchRun | None:
        with get_connection() as connection:
            init_database(connection)
            row = connection.execute(
                """
                SELECT
                    job_search_run_id,
                    session_id,
                    confirmed_profile_id,
                    query,
                    locations_json,
                    target_roles_json,
                    keywords_json,
                    status,
                    results_json,
                    created_at,
                    updated_at
                FROM job_search_runs
                WHERE job_search_run_id = ?
                """,
                (job_search_run_id,),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_job_search_run(row)

    def list_recent_by_session(self, session_id: str) -> list[JobSearchRun]:
        with get_connection() as connection:
            init_database(connection)
            rows = connection.execute(
                """
                SELECT
                    job_search_run_id,
                    session_id,
                    confirmed_profile_id,
                    query,
                    locations_json,
                    target_roles_json,
                    keywords_json,
                    status,
                    results_json,
                    created_at,
                    updated_at
                FROM job_search_runs
                WHERE session_id = ?
                ORDER BY updated_at DESC, created_at DESC
                """,
                (session_id,),
            ).fetchall()
        return [self._row_to_job_search_run(row) for row in rows]

    @staticmethod
    def _row_to_job_search_run(row: object) -> JobSearchRun:
        return JobSearchRun(
            job_search_run_id=row["job_search_run_id"],
            session_id=row["session_id"],
            confirmed_profile_id=row["confirmed_profile_id"],
            query=row["query"],
            locations=json.loads(row["locations_json"]),
            target_roles=json.loads(row["target_roles_json"]),
            keywords=json.loads(row["keywords_json"]),
            status=row["status"],
            results=[
                JobSearchResult.model_validate(item)
                for item in json.loads(row["results_json"])
            ],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )


job_search_repository = JobSearchRepository()
