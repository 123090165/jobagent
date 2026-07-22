from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


ChatDataAccessMode = Literal["auto", "always", "off"]
ChatSource = Literal["profile", "search_results", "saved_jobs", "chat_history"]
ChatTurnStatus = Literal["pending", "completed", "failed"]
ChatAnalysisMode = Literal["llm", "deterministic", "fallback", "refused"]
ChatMemoryResourceStatus = Literal["available", "unavailable"]
ChatFreshness = Literal["reuse_allowed", "refresh_required"]
ChatRetrievalStrategy = Literal["use_attachment", "use_pinned", "reuse_previous", "load_recent"]


class ChatSearchResultRef(BaseModel):
    job_search_run_id: str = Field(min_length=1, max_length=100)
    job_result_id: str = Field(min_length=1, max_length=100)


class ChatContextAttachment(ChatSearchResultRef):
    type: Literal["search_result"] = "search_result"


class ChatSavedJobAttachment(BaseModel):
    type: Literal["saved_job"] = "saved_job"
    saved_job_id: str = Field(min_length=1, max_length=100)


class ChatBrowserCaptureAttachment(BaseModel):
    type: Literal["browser_capture"] = "browser_capture"
    capture_id: str = Field(min_length=1, max_length=100)


ChatTurnAttachment = Annotated[
    ChatContextAttachment | ChatSavedJobAttachment | ChatBrowserCaptureAttachment,
    Field(discriminator="type"),
]


class ChatDataScope(BaseModel):
    allowed_sources: list[ChatSource] = Field(
        default_factory=lambda: ["profile", "search_results", "saved_jobs", "chat_history"],
        max_length=4,
    )
    resume_profile_id: str | None = None
    job_search_run_ids: list[str] = Field(default_factory=list, max_length=3)
    job_search_result_refs: list[ChatSearchResultRef] = Field(default_factory=list, max_length=20)
    saved_job_ids: list[str] = Field(default_factory=list, max_length=20)
    browser_capture_ids: list[str] = Field(default_factory=list, max_length=5)

    @field_validator("allowed_sources")
    @classmethod
    def _deduplicate_sources(cls, value: list[ChatSource]) -> list[ChatSource]:
        return list(dict.fromkeys(value))


class ChatConversationCreateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=120)
    data_access_mode: ChatDataAccessMode = "auto"
    data_scope: ChatDataScope = Field(default_factory=ChatDataScope)

    @field_validator("title")
    @classmethod
    def _clean_title(cls, value: str | None) -> str | None:
        cleaned = value.strip() if value else ""
        return cleaned or None


class ChatConversationUpdateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=120)
    data_access_mode: ChatDataAccessMode | None = None
    data_scope: ChatDataScope | None = None


class ChatConversation(BaseModel):
    conversation_id: str
    user_id: str
    title: str
    data_access_mode: ChatDataAccessMode
    data_scope: ChatDataScope
    summary: dict[str, object] = Field(default_factory=dict)
    summary_through_sequence: int = 0
    summary_version: int = 0
    last_retrieval_used: bool = False
    last_retrieval_sources: list[ChatSource] = Field(default_factory=list)
    last_completed_sequence: int = 0
    created_at: datetime
    updated_at: datetime


class ChatConversationListResponse(BaseModel):
    items: list[ChatConversation] = Field(default_factory=list)


class ChatProfileContextOption(BaseModel):
    resume_profile_id: str
    label: str
    summary: str
    is_default: bool


class ChatSearchRunContextOption(BaseModel):
    job_search_run_id: str
    label: str
    query: str
    result_count: int
    created_at: datetime


class ChatSavedJobContextOption(BaseModel):
    saved_job_id: str
    label: str
    title: str
    company: str | None = None
    status: str
    updated_at: datetime


class ChatContextCatalog(BaseModel):
    profiles: list[ChatProfileContextOption] = Field(default_factory=list)
    search_runs: list[ChatSearchRunContextOption] = Field(default_factory=list)
    saved_jobs: list[ChatSavedJobContextOption] = Field(default_factory=list)


class ChatMemoryResource(BaseModel):
    source_type: ChatSource
    resource_id: str
    label: str
    status: ChatMemoryResourceStatus


class ChatMemoryStatus(BaseModel):
    conversation_id: str
    total_turn_count: int
    recent_turn_count: int
    summary: dict[str, object] = Field(default_factory=dict)
    summary_version: int
    summary_through_sequence: int
    pinned_context: list[ChatMemoryResource] = Field(default_factory=list)
    previous_references: list[ChatMemoryResource] = Field(default_factory=list)
    updated_at: datetime


class ChatCitation(BaseModel):
    citation_id: str
    source_type: ChatSource
    resource_id: str
    label: str
    excerpt: str | None = None
    href: str | None = None


class ChatRouteDecision(BaseModel):
    domain: Literal["in_scope", "out_of_scope", "unclear"] = "unclear"
    retrieval: list[ChatSource] = Field(default_factory=list, max_length=4)
    relation_to_previous: Literal["follow_up", "new_topic", "unclear"] = "unclear"
    freshness: ChatFreshness = "reuse_allowed"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    reason: str | None = Field(default=None, max_length=400)

    @field_validator("retrieval")
    @classmethod
    def _deduplicate_retrieval(cls, value: list[ChatSource]) -> list[ChatSource]:
        return list(dict.fromkeys(value))


class ChatRetrievalRequest(BaseModel):
    source: ChatSource
    strategy: ChatRetrievalStrategy
    policy_reason: str = Field(max_length=120)


class ChatRetrievalPlan(BaseModel):
    agent_sources: list[ChatSource] = Field(default_factory=list, max_length=4)
    requests: list[ChatRetrievalRequest] = Field(default_factory=list, max_length=4)
    freshness: ChatFreshness = "reuse_allowed"
    policy_reasons: list[str] = Field(default_factory=list, max_length=8)


class ChatTurnCreateRequest(BaseModel):
    client_turn_id: str = Field(min_length=1, max_length=100)
    question: str = Field(min_length=1, max_length=2000)
    llm_provider: Literal["mock", "ollama", "deepseek"] | None = None
    context_attachments: list[ChatTurnAttachment] = Field(default_factory=list, max_length=5)
    retry_of_turn_id: str | None = Field(default=None, min_length=1, max_length=100)

    @field_validator("client_turn_id", "question")
    @classmethod
    def _clean_required_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("field cannot be empty")
        return cleaned

    @field_validator("context_attachments")
    @classmethod
    def _deduplicate_attachments(
        cls,
        value: list[ChatTurnAttachment],
    ) -> list[ChatTurnAttachment]:
        unique: dict[tuple[str, ...], ChatTurnAttachment] = {}
        for item in value:
            if isinstance(item, ChatContextAttachment):
                key = (item.type, item.job_search_run_id, item.job_result_id)
            elif isinstance(item, ChatSavedJobAttachment):
                key = (item.type, item.saved_job_id)
            else:
                key = (item.type, item.capture_id)
            unique[key] = item
        return list(unique.values())

    @model_validator(mode="after")
    def _retry_uses_original_attachments(self) -> "ChatTurnCreateRequest":
        if self.retry_of_turn_id and self.context_attachments:
            raise ValueError("retry cannot override the original turn attachments")
        return self


class ChatTurn(BaseModel):
    turn_id: str
    conversation_id: str
    user_id: str
    sequence: int
    client_turn_id: str
    question: str
    answer: str | None = None
    status: ChatTurnStatus
    route: ChatRouteDecision | None = None
    retrieval_plan: ChatRetrievalPlan | None = None
    retrieval_used: bool = False
    retrieved_refs: list[str] = Field(default_factory=list)
    citations: list[ChatCitation] = Field(default_factory=list)
    analysis_mode: ChatAnalysisMode | None = None
    analysis_provider: str | None = None
    fallback_reason: str | None = None
    quality_warnings: list[str] = Field(default_factory=list)
    context_attachments: list[ChatTurnAttachment] = Field(default_factory=list)
    retry_of_turn_id: str | None = None
    created_at: datetime
    updated_at: datetime


class ChatTurnListResponse(BaseModel):
    items: list[ChatTurn] = Field(default_factory=list)
