"""定义 RAG 离线评估语料、测试用例、单例结果和汇总报告。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.rag_sync import RAGResourceType


class RAGFixtureDocument(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    document_key: str = Field(min_length=1)
    resource_type: RAGResourceType
    owner: Literal["primary", "other"] = "primary"
    payload: dict[str, object]
    searchable_text: str = Field(min_length=1)


class RAGQualityCase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: str = Field(min_length=1)
    query: str = Field(min_length=1)
    resource_types: tuple[RAGResourceType, ...]
    expected_document_keys: frozenset[str] = Field(min_length=1)
    forbidden_document_keys: frozenset[str] = frozenset()
    top_k: int = Field(default=5, ge=1, le=10)


class RAGQualityCorpus(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    fixture_version: str = Field(min_length=1)
    documents: tuple[RAGFixtureDocument, ...] = Field(min_length=1)
    cases: tuple[RAGQualityCase, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_references(self) -> "RAGQualityCorpus":
        keys = [document.document_key for document in self.documents]
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate RAG fixture document keys")
        known = set(keys)
        for case in self.cases:
            referenced = case.expected_document_keys | case.forbidden_document_keys
            if unknown := referenced - known:
                raise ValueError(
                    f"case {case.case_id} references unknown documents: {sorted(unknown)}"
                )
        return self


class RAGQualityCaseResult(BaseModel):
    case_id: str
    returned_document_keys: list[str]
    hit: bool
    recall_at_k: float
    precision_at_k: float
    reciprocal_rank: float
    forbidden_hits: list[str] = Field(default_factory=list)
    latency_ms: float = 0.0


class RAGQualityReport(BaseModel):
    fixture_version: str
    mode: str
    case_count: int
    hit_rate: float
    mean_recall_at_k: float
    mean_precision_at_k: float
    mean_reciprocal_rank: float
    forbidden_hit_count: int
    mean_latency_ms: float
    cases: list[RAGQualityCaseResult]
