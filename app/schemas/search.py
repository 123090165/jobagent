from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class SearchResultItem(BaseModel):
    title: str
    company: str
    location: str
    url: str
    snippet: str
    source: str
    retrieved_at: datetime
    responsibilities: list[str] = Field(default_factory=list)
    requirements: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    jd_text: str | None = None
    jd_text_preview: str | None = None
    is_full_jd: bool = False
    confidence: float = 0.0
    quality_label: str | None = None
    warnings: list[str] = Field(default_factory=list)
    external_links: list[str] = Field(default_factory=list)


class SearchResultSet(BaseModel):
    query: str
    provider: str
    items: list[SearchResultItem] = Field(default_factory=list)
