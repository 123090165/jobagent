from __future__ import annotations

from pydantic import BaseModel, Field


class JobSearchProviderStatusResponse(BaseModel):
    provider: str
    configured: bool
    available_providers: list[str] = Field(default_factory=list)
    reason: str | None = None
    allowlisted_domains: list[str] = Field(default_factory=list)
