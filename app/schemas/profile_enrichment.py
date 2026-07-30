"""定义profile enrichment在 API、领域服务和 JSON 快照之间共用的 Pydantic 契约。"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.profile_review import ResumeProfileReviewResult


class EvidenceBoundSuggestion(BaseModel):
    section: str
    item_index: int | None = None
    field: str
    suggested_value: str | list[str]
    source_quote: str
    confidence_label: str = "medium"
    warnings: list[str] = Field(default_factory=list)


class SectionEnrichmentDraft(BaseModel):
    section: str
    item_index: int | None = None
    suggestions: list[EvidenceBoundSuggestion] = Field(default_factory=list)
    clarifying_questions: list[str] = Field(default_factory=list)


class ResumeProfileEnrichmentRequest(BaseModel):
    """描述画像enrichment的输入结构。"""
    resume_text: str
    target_roles: list[str] = Field(default_factory=list)
    use_llm: bool = False


class ResumeProfileEnrichmentResult(BaseModel):
    baseline_review: ResumeProfileReviewResult
    enrichment_suggestions: list[EvidenceBoundSuggestion] = Field(default_factory=list)
    quality_warnings: list[str] = Field(default_factory=list)
    missing_info_questions: list[str] = Field(default_factory=list)
    llm_success_count: int = 0
    fallback_count: int = 0
    discarded_suggestion_count: int = 0
    confidence_label: str = "medium"
