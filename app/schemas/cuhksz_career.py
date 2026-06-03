from __future__ import annotations

from pydantic import BaseModel, Field


class CUHKSZJobListItem(BaseModel):
    external_id: str
    title: str
    company: str | None = None
    location: str | None = None
    job_type: str | None = None
    education: str | None = None
    published_at: str | None = None
    deadline: str | None = None
    detail_url: str
    source: str = "cuhksz_career"


class CUHKSZJobDetail(BaseModel):
    list_item: CUHKSZJobListItem
    jd_text: str
    snippet: str
    is_full_jd: bool
    confidence: float
    quality_label: str = "invalid"
    extraction_method: str = "cuhksz_html"
    warnings: list[str] = Field(default_factory=list)
    external_links: list[str] = Field(default_factory=list)


class CUHKSZCollectSummary(BaseModel):
    list_url: str
    fetched_count: int
    detail_success_count: int
    detail_failed_count: int
    saved_count: int
    skipped_count: int
    errors: list[str] = Field(default_factory=list)
