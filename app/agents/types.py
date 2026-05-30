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


@dataclass(frozen=True)
class AgentRunResult(Generic[T]):
    output: T
    metadata: AgentRunMetadata
