from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from app.repositories.rag_sync_repository import RAGSyncRepository, rag_sync_repository
from app.repositories.resume_profile_repository import (
    ResumeProfileRepository,
    resume_profile_repository,
)
from app.repositories.saved_job_repository import SavedJobRepository, saved_job_repository
from app.schemas.rag_sync import RAGIndexEvent

from .rag_management import RAGManagementClient, RAGManagementError
from .rag_resource_formatter import format_resume_profile, format_saved_job


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RAGSyncBatchResult:
    claimed: int
    completed: int
    failed: int


@dataclass(frozen=True)
class RAGSyncRunResult:
    batches: int
    claimed: int
    completed: int
    failed: int


class RAGSyncWorker:
    def __init__(
        self,
        client: RAGManagementClient,
        *,
        sync_repository: RAGSyncRepository = rag_sync_repository,
        profile_repository: ResumeProfileRepository = resume_profile_repository,
        job_repository: SavedJobRepository = saved_job_repository,
    ) -> None:
        self.client = client
        self.sync_repository = sync_repository
        self.profile_repository = profile_repository
        self.job_repository = job_repository

    async def run_once(self, *, limit: int = 10) -> RAGSyncBatchResult:
        events = self.sync_repository.claim_pending(limit=limit)
        completed = 0
        failed = 0
        for event in events:
            try:
                current = self.sync_repository.get_status(
                    user_id=event.user_id,
                    resource_type=event.resource_type,
                    resource_id=event.resource_id,
                )
                if current is not None and event.resource_version < current.desired_version:
                    self.sync_repository.mark_completed(
                        event_id=event.event_id,
                        document_id=None,
                    )
                    completed += 1
                    continue
                await self._process(event)
                completed += 1
            except Exception as exc:
                failed += 1
                self.sync_repository.mark_failed(
                    event_id=event.event_id,
                    error_code=_error_code(exc),
                    error_message=str(exc),
                    retry_delay_seconds=min(300, 5 * (2 ** min(event.attempt_count, 6))),
                )
        return RAGSyncBatchResult(
            claimed=len(events),
            completed=completed,
            failed=failed,
        )

    async def run_forever(
        self,
        *,
        limit: int = 10,
        poll_interval_seconds: float = 2.0,
        max_idle_interval_seconds: float = 30.0,
        stop_event: asyncio.Event | None = None,
        max_batches: int | None = None,
    ) -> RAGSyncRunResult:
        if limit < 1 or limit > 100:
            raise ValueError("limit must be between 1 and 100")
        if poll_interval_seconds <= 0:
            raise ValueError("poll_interval_seconds must be positive")
        if max_idle_interval_seconds < poll_interval_seconds:
            raise ValueError(
                "max_idle_interval_seconds must be at least poll_interval_seconds"
            )
        if max_batches is not None and max_batches < 1:
            raise ValueError("max_batches must be positive when provided")

        stop_event = stop_event or asyncio.Event()
        idle_interval = poll_interval_seconds
        totals = RAGSyncRunResult(0, 0, 0, 0)
        while not stop_event.is_set():
            batch = await self.run_once(limit=limit)
            totals = RAGSyncRunResult(
                batches=totals.batches + 1,
                claimed=totals.claimed + batch.claimed,
                completed=totals.completed + batch.completed,
                failed=totals.failed + batch.failed,
            )
            if batch.claimed or batch.failed:
                logger.info(
                    "RAG sync batch claimed=%d completed=%d failed=%d",
                    batch.claimed,
                    batch.completed,
                    batch.failed,
                )
            if max_batches is not None and totals.batches >= max_batches:
                break
            if batch.claimed:
                wait_interval = poll_interval_seconds
                idle_interval = poll_interval_seconds
            else:
                wait_interval = idle_interval
                idle_interval = min(
                    max_idle_interval_seconds,
                    max(poll_interval_seconds, idle_interval * 2),
                )
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=wait_interval)
            except TimeoutError:
                pass
        return totals

    async def _process(self, event: RAGIndexEvent) -> None:
        if event.operation == "delete":
            status = self.sync_repository.get_status(
                user_id=event.user_id,
                resource_type=event.resource_type,
                resource_id=event.resource_id,
            )
            document_id = status.indexed_document_id if status is not None else None
            if document_id:
                await self.client.delete(
                    event_id=event.event_id,
                    document_id=document_id,
                )
            self.sync_repository.mark_completed(
                event_id=event.event_id,
                document_id=None,
            )
            return

        if event.resource_type == "resume_profile":
            profile = self.profile_repository.get(
                user_id=event.user_id,
                resume_profile_id=event.resource_id,
            )
            if profile is None or profile.archived_at is not None:
                raise KeyError("resume profile is not available for RAG indexing")
            resource = format_resume_profile(
                profile,
                resource_version=event.resource_version,
            )
        elif event.resource_type == "saved_job":
            job = self.job_repository.get(
                user_id=event.user_id,
                saved_job_id=event.resource_id,
            )
            if job is None or job.archived_at is not None:
                raise KeyError("saved job is not available for RAG indexing")
            resource = format_saved_job(
                job,
                resource_version=event.resource_version,
            )
        else:
            raise ValueError(f"unsupported RAG resource type: {event.resource_type}")

        result = await self.client.upsert(
            event_id=event.event_id,
            user_id=event.user_id,
            resource=resource,
        )
        if result.resource_version != event.resource_version or result.status != "ready":
            raise RAGManagementError("RAG did not publish the requested resource version")
        self.sync_repository.mark_completed(
            event_id=event.event_id,
            document_id=result.document_id,
        )


def _error_code(error: Exception) -> str:
    if isinstance(error, RAGManagementError):
        return "RAG_UNAVAILABLE"
    if isinstance(error, KeyError):
        return "RESOURCE_NOT_FOUND"
    if isinstance(error, ValueError):
        return "CONTRACT_INVALID"
    return "SYNC_FAILED"
