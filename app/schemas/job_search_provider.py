"""定义职位搜索 run、结果与 trace在 API、领域服务和 JSON 快照之间共用的 Pydantic 契约。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class JobSearchProviderStatusResponse(BaseModel):
    provider: str
    configured: bool
    available_providers: list[str] = Field(default_factory=list)
    reason: str | None = None
    base_url: str | None = None
    search_url: str | None = None
    allowlisted_domains: list[str] = Field(default_factory=list)
    source_kind: str = "native_job_board"
    detail_strategy: str = "native_list_and_detail_crawl"
