from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, Field


class JobSearchProviderError(RuntimeError):
    """Raised when a job search provider cannot produce usable results."""


class RawJobCandidate(BaseModel):
    title: str | None
    company: str | None
    location: str | None
    source_url: str | None
    source_provider: str
    snippet: str
    raw_description: str | None = None
    discovery_query: str | None = None
    discovery_rank: int | None = None
    detail_status: str | None = None
    provider_warnings: list[str] = Field(default_factory=list)


class JobSearchProvider(Protocol):
    provider_name: str
    provider_kind: str

    def search_jobs(self, *, query: str, location: str | None, limit: int) -> list[RawJobCandidate]:
        ...
