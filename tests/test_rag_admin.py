"""回归验证rag admin的正常链路、失败边界和兼容契约。"""

from __future__ import annotations

from pathlib import Path

from app.repositories.rag_sync_repository import RAGSyncRepository
from app.repositories.resume_profile_repository import ResumeProfileRepository
from app.repositories.saved_job_repository import SavedJobRepository
from app.repositories.user_repository import UserRepository
from app.schemas.saved_job import SavedJobCreateRequest
from app.services.rag_admin import RAGAdminService
from app.storage.database import LOCAL_USER_ID, get_connection, init_database
from scripts.rag_admin import parse_args


def _service(monkeypatch, tmp_path: Path) -> tuple[RAGAdminService, SavedJobRepository]:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / "rag-admin.sqlite3"))
    monkeypatch.delenv("JOBAGENT_RAG_SYNC_ENABLED", raising=False)
    with get_connection() as connection:
        init_database(connection)
    jobs = SavedJobRepository()
    return (
        RAGAdminService(
            sync_repository=RAGSyncRepository(),
            user_repository=UserRepository(),
            profile_repository=ResumeProfileRepository(),
            job_repository=jobs,
        ),
        jobs,
    )


def test_backfill_enqueues_missing_resources_and_is_idempotent(
    monkeypatch,
    tmp_path: Path,
) -> None:
    service, jobs = _service(monkeypatch, tmp_path)
    job = jobs.save(
        user_id=LOCAL_USER_ID,
        payload=SavedJobCreateRequest(
            title="Platform Engineer",
            company="Example",
            raw_jd_text="Build Kubernetes platforms.",
        ),
    )

    first = service.backfill(
        user_id=LOCAL_USER_ID,
        resource_types=("saved_job",),
    )
    second = service.backfill(
        user_id=LOCAL_USER_ID,
        resource_types=("saved_job",),
    )
    forced = service.backfill(
        user_id=LOCAL_USER_ID,
        resource_types=("saved_job",),
        force=True,
    )
    overview = service.overview(user_id=LOCAL_USER_ID)

    assert job.saved_job_id
    assert first.events_enqueued == 1
    assert second.events_enqueued == 0
    assert second.resources_skipped == 1
    assert forced.events_enqueued == 1
    assert overview.resource_count == 1
    assert overview.pending_resource_count == 1
    assert overview.pending_event_count == 2


def test_reindex_and_retry_failed_operate_only_on_current_event(
    monkeypatch,
    tmp_path: Path,
) -> None:
    service, jobs = _service(monkeypatch, tmp_path)
    job = jobs.save(
        user_id=LOCAL_USER_ID,
        payload=SavedJobCreateRequest(
            title="Backend Engineer",
            raw_jd_text="Build Python services.",
        ),
    )
    event_id = service.reindex(
        user_id=LOCAL_USER_ID,
        resource_type="saved_job",
        resource_id=job.saved_job_id,
    )
    claimed = service.sync_repository.claim_pending(limit=1)
    service.sync_repository.mark_failed(
        event_id=claimed[0].event_id,
        error_code="RAG_UNAVAILABLE",
        error_message="connection refused",
    )

    retried = service.retry_failed(user_id=LOCAL_USER_ID)
    event = service.sync_repository.get_event(event_id)
    overview = service.overview(user_id=LOCAL_USER_ID)

    assert retried == 1
    assert event.status == "pending"
    assert event.attempt_count == 0
    assert overview.pending_event_count == 1
    assert overview.failed_event_count == 0


def test_reconcile_enqueues_delete_for_archived_indexed_resource(
    monkeypatch,
    tmp_path: Path,
) -> None:
    service, jobs = _service(monkeypatch, tmp_path)
    job = jobs.save(
        user_id=LOCAL_USER_ID,
        payload=SavedJobCreateRequest(
            title="Archived Role",
            raw_jd_text="No longer active.",
        ),
    )
    event_id = service.reindex(
        user_id=LOCAL_USER_ID,
        resource_type="saved_job",
        resource_id=job.saved_job_id,
    )
    service.sync_repository.mark_completed(
        event_id=event_id,
        document_id="indexed-document",
    )
    jobs.archive(user_id=LOCAL_USER_ID, saved_job_id=job.saved_job_id)

    result = service.reconcile(user_id=LOCAL_USER_ID)
    status = service.sync_repository.get_status(
        user_id=LOCAL_USER_ID,
        resource_type="saved_job",
        resource_id=job.saved_job_id,
    )

    assert result.deletes_enqueued == 1
    assert status is not None
    assert status.sync_status == "pending"


def test_rag_admin_cli_parses_bounded_commands() -> None:
    backfill = parse_args([
        "backfill",
        "--user-id",
        "user-1",
        "--resource-type",
        "saved_job",
        "--force",
    ])
    status = parse_args(["status"])

    assert backfill.resource_types == ["saved_job"]
    assert backfill.force is True
    assert status.command == "status"
