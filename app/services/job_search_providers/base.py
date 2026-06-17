from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel


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


class JobSearchProvider(Protocol):
    provider_name: str

    def search_jobs(self, *, query: str, location: str | None, limit: int) -> list[RawJobCandidate]:
        ...
