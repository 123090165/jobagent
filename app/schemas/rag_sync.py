from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


RAGResourceType = Literal["resume_profile", "saved_job"]
RAGSyncOperation = Literal["upsert", "delete"]
RAGSyncStatus = Literal["pending", "processing", "completed", "failed"]


class RAGIndexEvent(BaseModel):
    event_id: str
    user_id: str
    resource_type: RAGResourceType
    resource_id: str
    resource_version: int
    operation: RAGSyncOperation
    status: RAGSyncStatus
    attempt_count: int
    available_at: datetime
    last_error_code: str | None = None
    last_error_message: str | None = None
    created_at: datetime
    completed_at: datetime | None = None


class RAGResourceStatus(BaseModel):
    user_id: str
    resource_type: RAGResourceType
    resource_id: str
    desired_version: int
    indexed_version: int | None = None
    indexed_document_id: str | None = None
    sync_status: str
    last_event_id: str
    last_synced_at: datetime | None = None
    last_error_code: str | None = None
    updated_at: datetime


class RAGSyncOverview(BaseModel):
    resource_count: int = 0
    ready_count: int = 0
    pending_resource_count: int = 0
    failed_resource_count: int = 0
    deleted_count: int = 0
    pending_event_count: int = 0
    processing_event_count: int = 0
    failed_event_count: int = 0
    oldest_pending_at: datetime | None = None
    last_synced_at: datetime | None = None
    recent_failures: list[RAGIndexEvent] = Field(default_factory=list)


class RAGServiceStatus(BaseModel):
    sync_enabled: bool
    mcp_configured: bool
    reachable: bool
    server_name: str | None = None
    server_version: str | None = None
    reason: str | None = None
    overview: RAGSyncOverview


class FormattedRAGResource(BaseModel):
    resource_type: RAGResourceType
    resource_id: str
    resource_version: int
    title: str
    text: str
    source_updated_at: datetime
