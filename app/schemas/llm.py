"""定义llm在 API、领域服务和 JSON 快照之间共用的 Pydantic 契约。"""

from __future__ import annotations

from pydantic import BaseModel


class LLMStatusResponse(BaseModel):
    provider: str
    configured: bool
    model: str | None = None
    base_url: str | None = None
    reason: str | None = None
