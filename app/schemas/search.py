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


class SearchResultSet(BaseModel):
    query: str
    provider: str
    items: list[SearchResultItem] = Field(default_factory=list)
