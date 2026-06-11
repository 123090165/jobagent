from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, Field

AgentExecutionMode = Literal["mock", "llm", "fallback"]

T = TypeVar("T")


class AgentRunMetadata(BaseModel):
    agent_name: str
    mode: AgentExecutionMode
    fallback_reason: str | None = None
    guardrails: list[str] = Field(default_factory=list)
    quality_warnings: list[str] = Field(default_factory=list)
    llm_success_count: int | None = None
    fallback_count: int | None = None
    item_fallback_reasons: list[str] = Field(default_factory=list)
    prompt_version: str | None = None


@dataclass(frozen=True)
class AgentRunResult(Generic[T]):
    output: T
    metadata: AgentRunMetadata
