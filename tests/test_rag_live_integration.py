"""回归验证rag live integration的正常链路、失败边界和兼容契约。"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from uuid import uuid4

import pytest

from app.repositories.rag_sync_repository import RAGSyncRepository
from app.repositories.saved_job_repository import SavedJobRepository
from app.schemas.saved_job import SavedJobCreateRequest
from app.services.chat_personal_knowledge import search_personal_knowledge
from app.services.rag_management import RAGManagementClient
from app.services.rag_management import resolve_rag_management_client
from app.services.mcp.modular_rag import resolve_modular_rag_service
from app.services.rag_sync_worker import RAGSyncWorker
from app.storage.database import get_connection, init_database


@pytest.mark.skipif(
    os.getenv("JOBAGENT_RAG_LIVE_TEST", "").strip() != "1",
    reason="set JOBAGENT_RAG_LIVE_TEST=1 to exercise the live RAG management service",
)
def test_jobagent_outbox_to_live_rag_upsert_and_delete(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / "jobagent.sqlite3"))
    monkeypatch.setenv("JOBAGENT_RAG_SYNC_ENABLED", "true")
    with get_connection() as connection:
        init_database(connection)

    client = resolve_rag_management_client()
    assert client is not None
    rag_service = resolve_modular_rag_service()
    assert rag_service is not None, (
        "JOBAGENT_RAG_MCP_URL is required for the live RAG test"
    )
    jobs = SavedJobRepository()
    sync = RAGSyncRepository()
    worker = RAGSyncWorker(
        client,
        sync_repository=sync,
        job_repository=jobs,
    )
    run_marker = f"rag-live-{uuid4().hex}"
    job = jobs.save(
        user_id="local-user",
        payload=SavedJobCreateRequest(
            title="RAG Integration Test Engineer",
            company="JobAgent",
            raw_jd_text=(
                "Build a tenant-aware Python retrieval service. "
                f"Verification marker: {run_marker}."
            ),
        ),
    )
    try:
        upserted = asyncio.run(worker.run_once())
        ready = sync.get_status(
            user_id="local-user",
            resource_type="saved_job",
            resource_id=job.saved_job_id,
        )
        failed_event = (
            sync.get_event(ready.last_event_id) if ready is not None else None
        )
        assert upserted.completed == 1, (
            failed_event.last_error_message if failed_event is not None else upserted
        )
        assert ready is not None
        assert ready.sync_status == "ready"
        assert ready.indexed_document_id
        matches = asyncio.run(rag_service.query_for_user(
            run_marker,
            user_id="local-user",
            resource_types=("saved_job",),
        ))
        assert matches.results
        assert matches.results[0].metadata["owner_user_id"] == "local-user"
        assert matches.results[0].metadata["resource_id"] == job.saved_job_id
        chat_knowledge = search_personal_knowledge(
            f"which saved job contains verification marker {run_marker}?",
            user_id="local-user",
            allowed_sources=["saved_jobs"],
            sync_repository=sync,
        )
        assert chat_knowledge.evidence
        assert chat_knowledge.evidence[0].citation.resource_id == job.saved_job_id
        assert chat_knowledge.evidence[0].content["retrieval_source"] == (
            "modular_rag_mcp"
        )
    finally:
        current = sync.get_status(
            user_id="local-user",
            resource_type="saved_job",
            resource_id=job.saved_job_id,
        )
        if current is not None and current.indexed_document_id:
            jobs.archive(user_id="local-user", saved_job_id=job.saved_job_id)
            deleted = asyncio.run(worker.run_once())
            status = sync.get_status(
                user_id="local-user",
                resource_type="saved_job",
                resource_id=job.saved_job_id,
            )
            assert deleted.completed == 1
            assert status is not None
            assert status.sync_status == "deleted"
            assert status.indexed_document_id is None


@pytest.mark.skipif(
    os.getenv("JOBAGENT_RAG_LIVE_TEST", "").strip() != "1",
    reason="set JOBAGENT_RAG_LIVE_TEST=1 to exercise live RAG recovery",
)
def test_jobagent_write_survives_rag_outage_and_recovers(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / "jobagent.sqlite3"))
    monkeypatch.setenv("JOBAGENT_RAG_SYNC_ENABLED", "true")
    with get_connection() as connection:
        init_database(connection)

    live_client = resolve_rag_management_client()
    assert live_client is not None
    rag_service = resolve_modular_rag_service()
    assert rag_service is not None

    jobs = SavedJobRepository()
    sync = RAGSyncRepository()
    unavailable_worker = RAGSyncWorker(
        RAGManagementClient(
            "http://127.0.0.1:1",
            service_token="outage-simulation-only",
            timeout_seconds=1,
        ),
        sync_repository=sync,
        job_repository=jobs,
    )
    recovery_worker = RAGSyncWorker(
        live_client,
        sync_repository=sync,
        job_repository=jobs,
    )
    run_marker = f"rag-recovery-{uuid4().hex}"
    job = jobs.save(
        user_id="local-user",
        payload=SavedJobCreateRequest(
            title="RAG Recovery Test Engineer",
            company="JobAgent",
            raw_jd_text=f"Recovery verification marker: {run_marker}.",
        ),
    )

    try:
        unavailable = asyncio.run(unavailable_worker.run_once())
        failed_status = sync.get_status(
            user_id="local-user",
            resource_type="saved_job",
            resource_id=job.saved_job_id,
        )
        assert unavailable.failed == 1
        assert jobs.get(
            user_id="local-user",
            saved_job_id=job.saved_job_id,
        ) is not None
        assert failed_status is not None
        assert failed_status.sync_status == "failed"

        assert sync.retry_failed(user_id="local-user") == 1
        recovered = asyncio.run(recovery_worker.run_once())
        recovered_status = sync.get_status(
            user_id="local-user",
            resource_type="saved_job",
            resource_id=job.saved_job_id,
        )
        assert recovered.completed == 1
        assert recovered_status is not None
        assert recovered_status.sync_status == "ready"

        matches = asyncio.run(rag_service.query_for_user(
            run_marker,
            user_id="local-user",
            resource_types=("saved_job",),
        ))
        assert matches.results
        assert matches.results[0].metadata["resource_id"] == job.saved_job_id
    finally:
        current = sync.get_status(
            user_id="local-user",
            resource_type="saved_job",
            resource_id=job.saved_job_id,
        )
        if current is not None and current.indexed_document_id:
            jobs.archive(user_id="local-user", saved_job_id=job.saved_job_id)
            deleted = asyncio.run(recovery_worker.run_once())
            assert deleted.completed == 1
