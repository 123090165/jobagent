"""定义knowledge在 API、领域服务和 JSON 快照之间共用的 Pydantic 契约。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator


class KnowledgeQueryRequest(BaseModel):
    """描述knowledge查询的输入结构。"""
    query: str = Field(min_length=1, max_length=2_000)
    top_k: int = Field(default=5, ge=1, le=20)
    collection: str | None = Field(default=None, min_length=1, max_length=100)

    @field_validator("query", "collection")
    @classmethod
    def _strip_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("field cannot be empty")
        return cleaned


class KnowledgeMatch(BaseModel):
    chunk_id: str = Field(min_length=1, max_length=500)
    score: float
    text: str = Field(max_length=20_000)
    metadata: dict[str, Any] = Field(default_factory=dict)


class KnowledgeQueryResult(BaseModel):
    results: list[KnowledgeMatch] = Field(default_factory=list, max_length=20)


class KnowledgeCollections(BaseModel):
    collections: list[str] = Field(default_factory=list, max_length=100)


class KnowledgeDocumentSummary(BaseModel):
    doc_id: str = Field(min_length=1, max_length=1_000)
    source_path: str = Field(default="", max_length=2_000)
    chunk_count: int = Field(ge=0)
    title: str = Field(default="", max_length=500)
    summary: str = Field(default="", max_length=20_000)
    metadata: dict[str, Any] = Field(default_factory=dict)
