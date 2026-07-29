from __future__ import annotations

from dataclasses import dataclass

from app.repositories.rag_sync_repository import RAGSyncRepository, rag_sync_repository
from app.repositories.resume_profile_repository import (
    ResumeProfileRepository,
    resume_profile_repository,
)
from app.repositories.saved_job_repository import SavedJobRepository, saved_job_repository
from app.repositories.user_repository import UserRepository, user_repository
from app.schemas.rag_sync import RAGResourceType, RAGSyncOverview


@dataclass(frozen=True)
class RAGBackfillResult:
    users_scanned: int
    resources_scanned: int
    events_enqueued: int
    resources_skipped: int


@dataclass(frozen=True)
class RAGReconcileResult:
    resources_scanned: int
    upserts_enqueued: int
    deletes_enqueued: int
    resources_skipped: int


class RAGAdminService:
    def __init__(
        self,
        *,
        sync_repository: RAGSyncRepository = rag_sync_repository,
        user_repository: UserRepository = user_repository,
        profile_repository: ResumeProfileRepository = resume_profile_repository,
        job_repository: SavedJobRepository = saved_job_repository,
    ) -> None:
        self.sync_repository = sync_repository
        self.user_repository = user_repository
        self.profile_repository = profile_repository
        self.job_repository = job_repository

    def backfill(
        self,
        *,
        user_id: str | None = None,
        resource_types: tuple[RAGResourceType, ...] = (
            "resume_profile",
            "saved_job",
        ),
        force: bool = False,
    ) -> RAGBackfillResult:
        normalized_types = tuple(dict.fromkeys(resource_types))
        if not normalized_types:
            raise ValueError("at least one resource type is required")
        if user_id is None:
            users = self.user_repository.list_all()
        else:
            user = self.user_repository.get(user_id)
            if user is None:
                raise KeyError(f"user not found: {user_id}")
            users = [user]

        scanned = 0
        enqueued = 0
        skipped = 0
        for user in users:
            resources: list[tuple[RAGResourceType, str]] = []
            if "resume_profile" in normalized_types:
                resources.extend(
                    ("resume_profile", profile.resume_profile_id)
                    for profile in self.profile_repository.list_by_user(user.user_id)
                )
            if "saved_job" in normalized_types:
                resources.extend(
                    ("saved_job", job.saved_job_id)
                    for job in self.job_repository.list_by_user(user.user_id)
                )
            for resource_type, resource_id in resources:
                scanned += 1
                status = self.sync_repository.get_status(
                    user_id=user.user_id,
                    resource_type=resource_type,
                    resource_id=resource_id,
                )
                should_enqueue = (
                    force
                    or status is None
                    or status.sync_status == "deleted"
                    or (
                        status.sync_status == "ready"
                        and status.indexed_version != status.desired_version
                    )
                )
                if not should_enqueue:
                    skipped += 1
                    continue
                self.sync_repository.enqueue(
                    user_id=user.user_id,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    operation="upsert",
                )
                enqueued += 1
        return RAGBackfillResult(
            users_scanned=len(users),
            resources_scanned=scanned,
            events_enqueued=enqueued,
            resources_skipped=skipped,
        )

    def reindex(
        self,
        *,
        user_id: str,
        resource_type: RAGResourceType,
        resource_id: str,
    ) -> str:
        if resource_type == "resume_profile":
            resource = self.profile_repository.get(
                user_id=user_id,
                resume_profile_id=resource_id,
            )
        else:
            resource = self.job_repository.get(
                user_id=user_id,
                saved_job_id=resource_id,
            )
        if resource is None or resource.archived_at is not None:
            raise KeyError("active RAG resource not found")
        event = self.sync_repository.enqueue(
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            operation="upsert",
        )
        return event.event_id

    def overview(self, *, user_id: str | None = None) -> RAGSyncOverview:
        return self.sync_repository.get_overview(user_id=user_id)

    def reconcile(self, *, user_id: str | None = None) -> RAGReconcileResult:
        statuses = self.sync_repository.list_statuses(user_id=user_id)
        upserts = 0
        deletes = 0
        skipped = 0
        for status in statuses:
            if status.resource_type == "resume_profile":
                resource = self.profile_repository.get(
                    user_id=status.user_id,
                    resume_profile_id=status.resource_id,
                )
            else:
                resource = self.job_repository.get(
                    user_id=status.user_id,
                    saved_job_id=status.resource_id,
                )
            active = resource is not None and resource.archived_at is None
            if active and status.sync_status == "deleted":
                operation = "upsert"
                upserts += 1
            elif (
                not active
                and status.indexed_document_id is not None
                and status.sync_status not in {"pending", "processing"}
            ):
                operation = "delete"
                deletes += 1
            else:
                skipped += 1
                continue
            self.sync_repository.enqueue(
                user_id=status.user_id,
                resource_type=status.resource_type,
                resource_id=status.resource_id,
                operation=operation,
            )
        return RAGReconcileResult(
            resources_scanned=len(statuses),
            upserts_enqueued=upserts,
            deletes_enqueued=deletes,
            resources_skipped=skipped,
        )

    def retry_failed(
        self,
        *,
        user_id: str | None = None,
        limit: int = 100,
    ) -> int:
        return self.sync_repository.retry_failed(user_id=user_id, limit=limit)


rag_admin_service = RAGAdminService()
