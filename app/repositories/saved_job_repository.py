from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from uuid import uuid4

from app.repositories.rag_sync_repository import rag_sync_repository
from app.schemas.saved_job import (
    SavedJob,
    SavedJobAnalysis,
    SavedJobCreateRequest,
    SavedJobOrigin,
    SavedJobStatus,
    SavedJobStatusEvent,
    SavedJobUpdateRequest,
)
from app.storage.database import get_connection, init_database


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SavedJobRepository:
    def save(
        self,
        *,
        user_id: str,
        payload: SavedJobCreateRequest,
    ) -> SavedJob:
        existing = self._get_by_identity(
            user_id=user_id,
            source_url=_clean_optional_string(payload.source_url),
            normalized_source_key=_normalized_source_key(
                title=payload.title,
                company=payload.company,
                location=payload.location,
                source_provider=payload.source_provider,
            ),
        )
        if existing is not None:
            next_status = (
                existing.status
                if payload.status == "saved" and existing.status != "archived"
                else payload.status
            )
            updated = self.update(
                user_id=user_id,
                saved_job_id=existing.saved_job_id,
                payload=SavedJobUpdateRequest(
                    status=next_status,
                    notes=payload.notes if payload.notes is not None else existing.notes,
                    tags=_clean_list(existing.tags + payload.tags),
                ),
            )
            return self._refresh_content_if_better(
                user_id=user_id,
                existing=updated or existing,
                payload=payload,
            )

        now = _utc_now()
        source_url = _clean_optional_string(payload.source_url)
        job = SavedJob(
            saved_job_id=str(uuid4()),
            user_id=user_id,
            source_provider=_clean_optional_string(payload.source_provider),
            source_url=source_url,
            normalized_source_key=_normalized_source_key(
                title=payload.title,
                company=payload.company,
                location=payload.location,
                source_provider=payload.source_provider,
            ),
            title=payload.title.strip(),
            company=_clean_optional_string(payload.company),
            location=_clean_optional_string(payload.location),
            salary=_clean_optional_string(payload.salary),
            employment_type=_clean_optional_string(payload.employment_type),
            raw_jd_text=payload.raw_jd_text.strip(),
            structured_jd=payload.structured_jd,
            tags=_clean_list(payload.tags),
            status=payload.status,
            notes=_clean_optional_string(payload.notes),
            first_seen_at=now,
            saved_at=now,
            updated_at=now,
        )
        with get_connection() as connection:
            init_database(connection)
            connection.execute(
                """
                INSERT INTO saved_jobs (
                    saved_job_id,
                    user_id,
                    source_provider,
                    source_url,
                    normalized_source_key,
                    title,
                    company,
                    location,
                    salary,
                    employment_type,
                    raw_jd_text,
                    structured_jd_json,
                    tags_json,
                    status,
                    notes,
                    first_seen_at,
                    saved_at,
                    updated_at,
                    archived_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                self._job_values(job),
            )
            self._insert_status_event(
                connection,
                user_id=user_id,
                saved_job_id=job.saved_job_id,
                from_status=None,
                to_status=job.status,
                reason="Job saved",
                changed_at=now,
            )
            rag_sync_repository.enqueue_if_enabled(
                connection=connection,
                user_id=user_id,
                resource_type="saved_job",
                resource_id=job.saved_job_id,
                operation="upsert",
            )
            connection.commit()
        return job

    def _refresh_content_if_better(
        self,
        *,
        user_id: str,
        existing: SavedJob,
        payload: SavedJobCreateRequest,
    ) -> SavedJob:
        incoming_jd = payload.raw_jd_text.strip()
        raw_jd_text = (
            incoming_jd
            if len(incoming_jd) > len(existing.raw_jd_text.strip())
            else existing.raw_jd_text
        )
        structured_jd = _merge_richer_values(
            existing.structured_jd,
            payload.structured_jd,
        )
        if (
            raw_jd_text == existing.raw_jd_text
            and structured_jd == existing.structured_jd
        ):
            return existing

        updated_at = _utc_now()
        with get_connection() as connection:
            init_database(connection)
            connection.execute(
                """
                UPDATE saved_jobs
                SET raw_jd_text = ?, structured_jd_json = ?, updated_at = ?
                WHERE user_id = ? AND saved_job_id = ?
                """,
                (
                    raw_jd_text,
                    json.dumps(structured_jd),
                    updated_at.isoformat(),
                    user_id,
                    existing.saved_job_id,
                ),
            )
            rag_sync_repository.enqueue_if_enabled(
                connection=connection,
                user_id=user_id,
                resource_type="saved_job",
                resource_id=existing.saved_job_id,
                operation="upsert",
            )
            connection.commit()
        return self.get(
            user_id=user_id,
            saved_job_id=existing.saved_job_id,
        ) or existing

    def create_analysis(
        self,
        *,
        user_id: str,
        saved_job_id: str,
        analysis: dict[str, object],
        analysis_mode: str,
        resume_profile_id: str | None = None,
        source_job_search_run_id: str | None = None,
        source_job_result_id: str | None = None,
        match_score: int | None = None,
        confidence_label: str | None = None,
        recommendation: str | None = None,
        matched_strengths: list[str] | None = None,
        critical_gaps: list[str] | None = None,
        resume_actions: list[str] | None = None,
        interview_questions: list[str] | None = None,
    ) -> SavedJobAnalysis:
        created_at = _utc_now()
        item = SavedJobAnalysis(
            saved_job_analysis_id=str(uuid4()),
            saved_job_id=saved_job_id,
            user_id=user_id,
            resume_profile_id=resume_profile_id,
            source_job_search_run_id=source_job_search_run_id,
            source_job_result_id=source_job_result_id,
            match_score=match_score,
            confidence_label=confidence_label,
            recommendation=recommendation,
            matched_strengths=_clean_list(matched_strengths or []),
            critical_gaps=_clean_list(critical_gaps or []),
            resume_actions=_clean_list(resume_actions or []),
            interview_questions=_clean_list(interview_questions or []),
            analysis=analysis,
            analysis_mode=analysis_mode,
            created_at=created_at,
        )
        with get_connection() as connection:
            init_database(connection)
            connection.execute(
                """
                INSERT INTO saved_job_analyses (
                    saved_job_analysis_id,
                    saved_job_id,
                    user_id,
                    resume_profile_id,
                    source_job_search_run_id,
                    source_job_result_id,
                    match_score,
                    confidence_label,
                    recommendation,
                    matched_strengths_json,
                    critical_gaps_json,
                    resume_actions_json,
                    interview_questions_json,
                    analysis_json,
                    analysis_mode,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.saved_job_analysis_id,
                    item.saved_job_id,
                    item.user_id,
                    item.resume_profile_id,
                    item.source_job_search_run_id,
                    item.source_job_result_id,
                    item.match_score,
                    item.confidence_label,
                    item.recommendation,
                    json.dumps(item.matched_strengths),
                    json.dumps(item.critical_gaps),
                    json.dumps(item.resume_actions),
                    json.dumps(item.interview_questions),
                    json.dumps(item.analysis),
                    item.analysis_mode,
                    item.created_at.isoformat(),
                ),
            )
            connection.commit()
        return item

    def create_origin(
        self,
        *,
        user_id: str,
        saved_job_id: str,
        origin_key: str,
        origin_type: str,
        resume_profile_id: str | None = None,
        job_search_run_id: str | None = None,
        job_search_result_id: str | None = None,
        saved_job_analysis_id: str | None = None,
        profile_label: str | None = None,
        search_query: str | None = None,
        source_provider: str | None = None,
    ) -> SavedJobOrigin:
        created_at = _utc_now()
        origin_id = str(uuid4())
        with get_connection() as connection:
            init_database(connection)
            connection.execute(
                """
                INSERT INTO saved_job_origins (
                    saved_job_origin_id, origin_key, user_id, saved_job_id,
                    origin_type, resume_profile_id, job_search_run_id,
                    job_search_result_id, saved_job_analysis_id,
                    profile_label_snapshot, search_query_snapshot,
                    source_provider, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, saved_job_id, origin_key) DO UPDATE SET
                    origin_type = excluded.origin_type,
                    resume_profile_id = excluded.resume_profile_id,
                    job_search_run_id = excluded.job_search_run_id,
                    job_search_result_id = excluded.job_search_result_id,
                    saved_job_analysis_id = excluded.saved_job_analysis_id,
                    profile_label_snapshot = excluded.profile_label_snapshot,
                    search_query_snapshot = excluded.search_query_snapshot,
                    source_provider = excluded.source_provider
                """,
                (
                    origin_id, origin_key, user_id, saved_job_id, origin_type,
                    resume_profile_id, job_search_run_id, job_search_result_id,
                    saved_job_analysis_id, _clean_optional_string(profile_label),
                    _clean_optional_string(search_query),
                    _clean_optional_string(source_provider), created_at.isoformat(),
                ),
            )
            row = connection.execute(
                """
                SELECT * FROM saved_job_origins
                WHERE user_id = ? AND saved_job_id = ? AND origin_key = ?
                """,
                (user_id, saved_job_id, origin_key),
            ).fetchone()
            connection.commit()
        if row is None:
            raise RuntimeError("Saved job origin disappeared after creation.")
        return self._row_to_origin(row)

    def list_origins(self, *, user_id: str, saved_job_id: str) -> list[SavedJobOrigin]:
        with get_connection() as connection:
            init_database(connection)
            rows = connection.execute(
                """
                SELECT * FROM saved_job_origins
                WHERE user_id = ? AND saved_job_id = ?
                ORDER BY created_at DESC, saved_job_origin_id DESC
                """,
                (user_id, saved_job_id),
            ).fetchall()
        return [self._row_to_origin(row) for row in rows]

    def list_by_user(self, user_id: str, *, include_archived: bool = False) -> list[SavedJob]:
        where_clause = "WHERE user_id = ?"
        if not include_archived:
            where_clause += " AND archived_at IS NULL"
        with get_connection() as connection:
            init_database(connection)
            rows = connection.execute(
                f"""
                SELECT *
                FROM saved_jobs
                {where_clause}
                ORDER BY updated_at DESC, saved_at DESC
                """,
                (user_id,),
            ).fetchall()
        return [self._with_latest_analysis(self._row_to_job(row)) for row in rows]

    def get(self, *, user_id: str, saved_job_id: str) -> SavedJob | None:
        with get_connection() as connection:
            init_database(connection)
            row = connection.execute(
                """
                SELECT *
                FROM saved_jobs
                WHERE user_id = ? AND saved_job_id = ?
                """,
                (user_id, saved_job_id),
            ).fetchone()
        if row is None:
            return None
        return self._with_latest_analysis(self._row_to_job(row))

    def update(
        self,
        *,
        user_id: str,
        saved_job_id: str,
        payload: SavedJobUpdateRequest,
    ) -> SavedJob | None:
        existing = self.get(user_id=user_id, saved_job_id=saved_job_id)
        if existing is None:
            return None
        next_status: SavedJobStatus = payload.status or existing.status
        archived_at = existing.archived_at
        if next_status == "archived" and archived_at is None:
            archived_at = _utc_now()
        elif next_status != "archived":
            archived_at = None
        updated = existing.model_copy(
            update={
                "status": next_status,
                "notes": _clean_optional_string(payload.notes)
                if payload.notes is not None
                else existing.notes,
                "tags": _clean_list(payload.tags)
                if payload.tags is not None
                else existing.tags,
                "archived_at": archived_at,
                "updated_at": _utc_now(),
            }
        )
        with get_connection() as connection:
            init_database(connection)
            connection.execute(
                """
                UPDATE saved_jobs
                SET status = ?, notes = ?, tags_json = ?, archived_at = ?, updated_at = ?
                WHERE user_id = ? AND saved_job_id = ?
                """,
                (
                    updated.status,
                    updated.notes,
                    json.dumps(updated.tags),
                    updated.archived_at.isoformat() if updated.archived_at else None,
                    updated.updated_at.isoformat(),
                    user_id,
                    saved_job_id,
                ),
            )
            if next_status != existing.status:
                self._insert_status_event(
                    connection,
                    user_id=user_id,
                    saved_job_id=saved_job_id,
                    from_status=existing.status,
                    to_status=next_status,
                    reason="Status updated",
                    changed_at=updated.updated_at,
                )
            rag_sync_repository.enqueue_if_enabled(
                connection=connection,
                user_id=user_id,
                resource_type="saved_job",
                resource_id=saved_job_id,
                operation="delete" if updated.archived_at is not None else "upsert",
            )
            connection.commit()
        return self.get(user_id=user_id, saved_job_id=saved_job_id)

    def archive(self, *, user_id: str, saved_job_id: str) -> SavedJob | None:
        existing = self.get(user_id=user_id, saved_job_id=saved_job_id)
        if existing is None:
            return None
        now = _utc_now().isoformat()
        with get_connection() as connection:
            init_database(connection)
            connection.execute(
                """
                UPDATE saved_jobs
                SET status = ?, archived_at = ?, updated_at = ?
                WHERE user_id = ? AND saved_job_id = ?
                """,
                ("archived", now, now, user_id, saved_job_id),
            )
            if existing.status != "archived":
                self._insert_status_event(
                    connection,
                    user_id=user_id,
                    saved_job_id=saved_job_id,
                    from_status=existing.status,
                    to_status="archived",
                    reason="Job archived",
                    changed_at=datetime.fromisoformat(now),
                )
            rag_sync_repository.enqueue_if_enabled(
                connection=connection,
                user_id=user_id,
                resource_type="saved_job",
                resource_id=saved_job_id,
                operation="delete",
            )
            connection.commit()
        return self.get(user_id=user_id, saved_job_id=saved_job_id)

    def delete(self, *, user_id: str, saved_job_id: str) -> bool:
        if self.get(user_id=user_id, saved_job_id=saved_job_id) is None:
            return False
        with get_connection() as connection:
            init_database(connection)
            connection.execute(
                "DELETE FROM saved_job_origins WHERE user_id = ? AND saved_job_id = ?",
                (user_id, saved_job_id),
            )
            connection.execute(
                "DELETE FROM interview_preparations WHERE user_id = ? AND saved_job_id = ?",
                (user_id, saved_job_id),
            )
            connection.execute(
                "DELETE FROM job_briefs WHERE user_id = ? AND saved_job_id = ?",
                (user_id, saved_job_id),
            )
            connection.execute(
                "DELETE FROM saved_job_analyses WHERE user_id = ? AND saved_job_id = ?",
                (user_id, saved_job_id),
            )
            connection.execute(
                "DELETE FROM saved_job_status_events WHERE user_id = ? AND saved_job_id = ?",
                (user_id, saved_job_id),
            )
            cursor = connection.execute(
                "DELETE FROM saved_jobs WHERE user_id = ? AND saved_job_id = ?",
                (user_id, saved_job_id),
            )
            rag_sync_repository.enqueue_if_enabled(
                connection=connection,
                user_id=user_id,
                resource_type="saved_job",
                resource_id=saved_job_id,
                operation="delete",
            )
            connection.commit()
        return cursor.rowcount > 0

    def latest_analysis(self, *, user_id: str, saved_job_id: str) -> SavedJobAnalysis | None:
        with get_connection() as connection:
            init_database(connection)
            row = connection.execute(
                """
                SELECT *
                FROM saved_job_analyses
                WHERE user_id = ? AND saved_job_id = ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (user_id, saved_job_id),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_analysis(row)

    def list_analyses(self, *, user_id: str, saved_job_id: str) -> list[SavedJobAnalysis]:
        with get_connection() as connection:
            init_database(connection)
            rows = connection.execute(
                """
                SELECT *
                FROM saved_job_analyses
                WHERE user_id = ? AND saved_job_id = ?
                ORDER BY created_at DESC, saved_job_analysis_id DESC
                """,
                (user_id, saved_job_id),
            ).fetchall()
        return [self._row_to_analysis(row) for row in rows]

    def list_status_events(
        self, *, user_id: str, saved_job_id: str
    ) -> list[SavedJobStatusEvent]:
        with get_connection() as connection:
            init_database(connection)
            rows = connection.execute(
                """
                SELECT * FROM saved_job_status_events
                WHERE user_id = ? AND saved_job_id = ?
                ORDER BY changed_at DESC, saved_job_status_event_id DESC
                """,
                (user_id, saved_job_id),
            ).fetchall()
        return [self._row_to_status_event(row) for row in rows]

    def _get_by_identity(
        self,
        *,
        user_id: str,
        source_url: str | None,
        normalized_source_key: str | None,
    ) -> SavedJob | None:
        if source_url is not None:
            with get_connection() as connection:
                init_database(connection)
                row = connection.execute(
                    """
                    SELECT *
                    FROM saved_jobs
                    WHERE user_id = ? AND source_url = ?
                    """,
                    (user_id, source_url),
                ).fetchone()
            if row is not None:
                return self._with_latest_analysis(self._row_to_job(row))

        if normalized_source_key is None:
            return None
        with get_connection() as connection:
            init_database(connection)
            row = connection.execute(
                """
                SELECT *
                FROM saved_jobs
                WHERE user_id = ? AND normalized_source_key = ?
                """,
                (user_id, normalized_source_key),
            ).fetchone()
        if row is None:
            return None
        return self._with_latest_analysis(self._row_to_job(row))

    def _with_latest_analysis(self, job: SavedJob) -> SavedJob:
        return job.model_copy(
            update={
                "latest_analysis": self.latest_analysis(
                    user_id=job.user_id,
                    saved_job_id=job.saved_job_id,
                )
            }
        )

    @staticmethod
    def _job_values(job: SavedJob) -> tuple[object, ...]:
        return (
            job.saved_job_id,
            job.user_id,
            job.source_provider,
            job.source_url,
            job.normalized_source_key,
            job.title,
            job.company,
            job.location,
            job.salary,
            job.employment_type,
            job.raw_jd_text,
            json.dumps(job.structured_jd),
            json.dumps(job.tags),
            job.status,
            job.notes,
            job.first_seen_at.isoformat(),
            job.saved_at.isoformat(),
            job.updated_at.isoformat(),
            job.archived_at.isoformat() if job.archived_at else None,
        )

    @staticmethod
    def _row_to_job(row: object) -> SavedJob:
        return SavedJob(
            saved_job_id=row["saved_job_id"],
            user_id=row["user_id"],
            source_provider=row["source_provider"],
            source_url=row["source_url"],
            normalized_source_key=row["normalized_source_key"],
            title=row["title"],
            company=row["company"],
            location=row["location"],
            salary=row["salary"],
            employment_type=row["employment_type"],
            raw_jd_text=row["raw_jd_text"],
            structured_jd=json.loads(row["structured_jd_json"]),
            tags=json.loads(row["tags_json"] or "[]"),
            status=row["status"],
            notes=row["notes"],
            first_seen_at=datetime.fromisoformat(row["first_seen_at"]),
            saved_at=datetime.fromisoformat(row["saved_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            archived_at=(
                datetime.fromisoformat(row["archived_at"])
                if row["archived_at"] is not None
                else None
            ),
        )

    @staticmethod
    def _row_to_analysis(row: object) -> SavedJobAnalysis:
        return SavedJobAnalysis(
            saved_job_analysis_id=row["saved_job_analysis_id"],
            saved_job_id=row["saved_job_id"],
            user_id=row["user_id"],
            resume_profile_id=row["resume_profile_id"],
            source_job_search_run_id=row["source_job_search_run_id"],
            source_job_result_id=row["source_job_result_id"],
            match_score=row["match_score"],
            confidence_label=row["confidence_label"],
            recommendation=row["recommendation"],
            matched_strengths=json.loads(row["matched_strengths_json"] or "[]"),
            critical_gaps=json.loads(row["critical_gaps_json"] or "[]"),
            resume_actions=json.loads(row["resume_actions_json"] or "[]"),
            interview_questions=json.loads(row["interview_questions_json"] or "[]"),
            analysis=json.loads(row["analysis_json"] or "{}"),
            analysis_mode=row["analysis_mode"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    @staticmethod
    def _row_to_origin(row: object) -> SavedJobOrigin:
        return SavedJobOrigin(
            saved_job_origin_id=row["saved_job_origin_id"],
            user_id=row["user_id"],
            saved_job_id=row["saved_job_id"],
            origin_type=row["origin_type"],
            resume_profile_id=row["resume_profile_id"],
            job_search_run_id=row["job_search_run_id"],
            job_search_result_id=row["job_search_result_id"],
            saved_job_analysis_id=row["saved_job_analysis_id"],
            profile_label=row["profile_label_snapshot"],
            search_query=row["search_query_snapshot"],
            source_provider=row["source_provider"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    @staticmethod
    def _row_to_status_event(row: object) -> SavedJobStatusEvent:
        return SavedJobStatusEvent(
            saved_job_status_event_id=row["saved_job_status_event_id"],
            saved_job_id=row["saved_job_id"],
            user_id=row["user_id"],
            from_status=row["from_status"],
            to_status=row["to_status"],
            reason=row["reason"],
            changed_at=datetime.fromisoformat(row["changed_at"]),
        )

    @staticmethod
    def _insert_status_event(
        connection: sqlite3.Connection,
        *,
        user_id: str,
        saved_job_id: str,
        from_status: str | None,
        to_status: str,
        reason: str,
        changed_at: datetime,
    ) -> None:
        connection.execute(
            """
            INSERT INTO saved_job_status_events (
                saved_job_status_event_id, saved_job_id, user_id,
                from_status, to_status, reason, changed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid4()),
                saved_job_id,
                user_id,
                from_status,
                to_status,
                reason,
                changed_at.isoformat(),
            ),
        )


def _normalized_source_key(
    *,
    title: str,
    company: str | None,
    location: str | None,
    source_provider: str | None,
) -> str:
    parts = [
        title,
        company or "",
        location or "",
        source_provider or "",
    ]
    return "|".join(" ".join(part.lower().strip().split()) for part in parts)


def _clean_optional_string(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _clean_list(values: list[object] | None) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values or []:
        item = str(value).strip()
        if not item:
            continue
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(item)
    return cleaned


def _merge_richer_values(
    existing: dict[str, object],
    incoming: dict[str, object],
) -> dict[str, object]:
    merged = dict(existing)
    for key, value in incoming.items():
        if _content_size(value) >= _content_size(merged.get(key)):
            merged[key] = value
    return merged


def _content_size(value: object) -> int:
    if value is None:
        return 0
    return len(json.dumps(value, ensure_ascii=False, sort_keys=True))


saved_job_repository = SavedJobRepository()
