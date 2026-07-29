from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest

from app.repositories.rag_sync_repository import RAGSyncRepository
from app.repositories.saved_job_repository import SavedJobRepository
from app.schemas.saved_job import SavedJobCreateRequest
from app.services.chat_personal_knowledge import search_personal_knowledge
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
    jobs = SavedJobRepository()
    sync = RAGSyncRepository()
    worker = RAGSyncWorker(
        client,
        sync_repository=sync,
        job_repository=jobs,
    )
    job = jobs.save(
        user_id="local-user",
        payload=SavedJobCreateRequest(
            title="RAG Integration Test Engineer",
            company="JobAgent",
            raw_jd_text="Build a tenant-aware Python retrieval service.",
        ),
    )

    upserted = asyncio.run(worker.run_once())
    ready = sync.get_status(
        user_id="local-user",
        resource_type="saved_job",
        resource_id=job.saved_job_id,
    )
    assert upserted.completed == 1
    assert ready is not None
    assert ready.sync_status == "ready"
    assert ready.indexed_document_id
    rag_service = resolve_modular_rag_service()
    assert rag_service is not None
    matches = asyncio.run(rag_service.query_for_user(
        "tenant-aware Python retrieval service",
        user_id="local-user",
        resource_types=("saved_job",),
    ))
    assert matches.results
    assert matches.results[0].metadata["owner_user_id"] == "local-user"
    assert matches.results[0].metadata["resource_id"] == job.saved_job_id
    chat_knowledge = search_personal_knowledge(
        "which saved job mentions tenant-aware Python retrieval?",
        user_id="local-user",
        allowed_sources=["saved_jobs"],
        sync_repository=sync,
    )
    assert chat_knowledge.evidence
    assert chat_knowledge.evidence[0].citation.resource_id == job.saved_job_id
    assert chat_knowledge.evidence[0].content["retrieval_source"] == (
        "modular_rag_mcp"
    )

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
