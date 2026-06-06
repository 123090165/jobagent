from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, Field


class RawJobListItem(BaseModel):
    source: str
    external_id: str
    title: str
    company: str | None = None
    location: str | None = None
    job_type: str | None = None
    education: str | None = None
    published_at: str | None = None
    deadline: str | None = None
    detail_url: str


class RawJobDetail(BaseModel):
    list_item: RawJobListItem
    jd_text: str
    snippet: str
    is_full_jd: bool = False
    confidence: float = 0.0
    quality_label: str | None = None
    warnings: list[str] = Field(default_factory=list)
    external_links: list[str] = Field(default_factory=list)
    extraction_method: str | None = None


class JobSiteParser(Protocol):
    source: str

    def parse_list(self, html: str, base_url: str) -> list[RawJobListItem]:
        ...

    def parse_detail(self, html: str, item: RawJobListItem) -> RawJobDetail:
        ...
