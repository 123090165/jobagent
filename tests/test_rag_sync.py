"""回归验证RAG 同步事件与资源状态的正常链路、失败边界和兼容契约。"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.repositories.rag_sync_repository import RAGSyncRepository
from app.repositories.saved_job_repository import SavedJobRepository
from app.schemas.resume_profile import ResumeProfile
from app.schemas.saved_job import SavedJob, SavedJobCreateRequest
from app.services.rag_management import RAGUpsertResult
from app.services.rag_resource_formatter import format_resume_profile, format_saved_job
from app.services.rag_sync_worker import RAGSyncWorker
from app.storage.database import get_connection, init_database


def _use_database(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / "jobagent.sqlite3"))
    with get_connection() as connection:
        init_database(connection)


def test_rag_outbox_versions_claims_and_tracks_published_document(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _use_database(monkeypatch, tmp_path)
    repository = RAGSyncRepository()
    first = repository.enqueue(
        user_id="local-user",
        resource_type="saved_job",
        resource_id="job-1",
        operation="upsert",
    )
    second = repository.enqueue(
        user_id="local-user",
        resource_type="saved_job",
        resource_id="job-1",
        operation="upsert",
    )

    claimed = repository.claim_pending(limit=10)
    repository.mark_completed(event_id=second.event_id, document_id="document-v2")
    status = repository.get_status(
        user_id="local-user",
        resource_type="saved_job",
        resource_id="job-1",
    )

    assert first.resource_version == 1
    assert second.resource_version == 2
    assert {event.event_id for event in claimed} == {first.event_id, second.event_id}
    assert status is not None
    assert status.desired_version == 2
    assert status.indexed_version == 2
    assert status.indexed_document_id == "document-v2"
    assert status.sync_status == "ready"
    assert status.last_event_id == second.event_id


def test_rag_formatters_are_readable_and_omit_raw_resume_and_contact_fields() -> None:
    now = datetime.now(timezone.utc)
    profile = ResumeProfile(
        resume_profile_id="profile-1",
        user_id="user-a",
        name="Backend profile",
        summary="Python backend engineer",
        target_roles=["Backend Engineer"],
        core_skills=["Python", "FastAPI"],
        profile={
            "projects": [{"name": "JobAgent", "result": "Reduced latency"}],
            "email": "private@example.com",
        },
        raw_resume_text="raw private resume",
        created_at=now,
        updated_at=now,
    )
    job = SavedJob(
        saved_job_id="job-1",
        user_id="user-a",
        title="Backend Engineer",
        company="Example",
        raw_jd_text="Build Python APIs",
        structured_jd={"requirements": ["Python", "SQL"]},
        first_seen_at=now,
        saved_at=now,
        updated_at=now,
    )

    profile_text = format_resume_profile(profile, resource_version=1).text
    job_text = format_saved_job(job, resource_version=1).text

    assert "JobAgent" in profile_text
    assert "raw private resume" not in profile_text
    assert "private@example.com" not in profile_text
    assert "[职位描述]" in job_text
    assert "requirements[0]: Python" in job_text


class _FakeManagementClient:
    def __init__(self) -> None:
        self.upserts: list[tuple[str, str]] = []
        self.deletes: list[tuple[str, str]] = []

    async def upsert(self, *, event_id, user_id, resource):
        self.upserts.append((event_id, resource.resource_id))
        return RAGUpsertResult(
            document_id=f"doc-{resource.resource_version}",
            resource_version=resource.resource_version,
            status="ready",
            chunk_count=1,
            replayed=False,
        )

    async def delete(self, *, event_id, document_id):
        self.deletes.append((event_id, document_id))


def test_saved_job_write_and_archive_drive_worker_upsert_and_delete(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _use_database(monkeypatch, tmp_path)
    monkeypatch.setenv("JOBAGENT_RAG_SYNC_ENABLED", "true")
    jobs = SavedJobRepository()
    sync = RAGSyncRepository()
    client = _FakeManagementClient()
    worker = RAGSyncWorker(
        client,  # type: ignore[arg-type]
        sync_repository=sync,
        job_repository=jobs,
    )
    job = jobs.save(
        user_id="local-user",
        payload=SavedJobCreateRequest(
            title="Backend Engineer",
            company="Example",
            raw_jd_text="Build Python APIs",
        ),
    )

    first = asyncio.run(worker.run_once())
    status = sync.get_status(
        user_id="local-user",
        resource_type="saved_job",
        resource_id=job.saved_job_id,
    )
    jobs.archive(user_id="local-user", saved_job_id=job.saved_job_id)
    second = asyncio.run(worker.run_once())

    assert first.completed == 1
    assert status is not None
    assert status.indexed_document_id == "doc-1"
    assert second.completed == 1
    assert client.deletes[0][1] == "doc-1"


def test_expired_processing_lease_is_reclaimed(monkeypatch, tmp_path: Path) -> None:
    _use_database(monkeypatch, tmp_path)
    repository = RAGSyncRepository()
    event = repository.enqueue(
        user_id="local-user",
        resource_type="saved_job",
        resource_id="job-lease",
        operation="upsert",
    )

    first = repository.claim_pending(limit=1, lease_seconds=60)
    assert [item.event_id for item in first] == [event.event_id]
    assert repository.claim_pending(limit=1) == []

    with get_connection() as connection:
        connection.execute(
            "UPDATE rag_index_outbox SET available_at = ? WHERE event_id = ?",
            (
                (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat(),
                event.event_id,
            ),
        )
        connection.commit()

    reclaimed = repository.claim_pending(limit=1)
    assert [item.event_id for item in reclaimed] == [event.event_id]
    assert reclaimed[0].attempt_count == 2


def test_expired_final_processing_lease_becomes_terminal_failure(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _use_database(monkeypatch, tmp_path)
    repository = RAGSyncRepository()
    event = repository.enqueue(
        user_id="local-user",
        resource_type="saved_job",
        resource_id="job-terminal-lease",
        operation="upsert",
    )
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE rag_index_outbox
            SET status = 'processing', attempt_count = 8, available_at = ?
            WHERE event_id = ?
            """,
            (
                (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat(),
                event.event_id,
            ),
        )
        connection.commit()

    assert repository.claim_pending(limit=1, max_attempts=8) == []
    failed = repository.get_event(event.event_id)
    status = repository.get_status(
        user_id="local-user",
        resource_type="saved_job",
        resource_id="job-terminal-lease",
    )

    assert failed.status == "failed"
    assert failed.last_error_code == "WORKER_LEASE_EXPIRED"
    assert status is not None
    assert status.sync_status == "failed"
    assert status.last_error_code == "WORKER_LEASE_EXPIRED"


def test_continuous_worker_supports_bounded_supervisor_runs(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _use_database(monkeypatch, tmp_path)
    worker = RAGSyncWorker(
        _FakeManagementClient(),  # type: ignore[arg-type]
        sync_repository=RAGSyncRepository(),
    )

    result = asyncio.run(worker.run_forever(max_batches=1))

    assert result.batches == 1
    assert result.claimed == 0
    assert result.failed == 0
