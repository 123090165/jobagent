"""定义jd quality在 API、领域服务和 JSON 快照之间共用的 Pydantic 契约。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class JDQualityReport(BaseModel):
    quality_label: str
    quality_score: float
    is_valid_jd: bool
    is_full_jd: bool
    warnings: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    text_length: int
    external_links: list[str] = Field(default_factory=list)
