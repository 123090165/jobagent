from __future__ import annotations

import json
import os
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any, Iterator


@dataclass(frozen=True)
class LLMObservationContext:
    name: str = "llm.chat_completion"
    metadata: dict[str, object] = field(default_factory=dict)
    context_parts: dict[str, object] = field(default_factory=dict)


_current_observation: ContextVar[LLMObservationContext] = ContextVar(
    "jobagent_llm_observation",
    default=LLMObservationContext(),
)


@contextmanager
def llm_observation_context(
    name: str,
    *,
    metadata: dict[str, object] | None = None,
    context_parts: dict[str, object] | None = None,
) -> Iterator[None]:
    token = _current_observation.set(LLMObservationContext(
        name=name,
        metadata=metadata or {},
        context_parts=context_parts or {},
    ))
    try:
        yield
    finally:
        _current_observation.reset(token)


def current_llm_observation() -> LLMObservationContext:
    return _current_observation.get()


@contextmanager
def langfuse_generation(
    *,
    model: str,
    system_prompt: str,
    user_prompt: str,
) -> Iterator[Any | None]:
    if not _enabled():
        yield None
        return
    try:
        from langfuse import get_client
    except ImportError:
        yield None
        return

    context = current_llm_observation()
    capture_content = _truthy("JOBAGENT_LANGFUSE_CAPTURE_CONTENT")
    input_payload: object = (
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        if capture_content
        else {
            "content_redacted": True,
            "system_chars": len(system_prompt),
            "user_chars": len(user_prompt),
        }
    )
    metadata = {
        **context.metadata,
        "context_sizes": _context_sizes(context.context_parts),
        "system_chars": len(system_prompt),
        "user_chars": len(user_prompt),
    }
    client = get_client()
    with client.start_as_current_observation(
        as_type="generation",
        name=context.name,
        model=model,
        input=input_payload,
        metadata=metadata,
    ) as generation:
        yield generation


def update_langfuse_generation(
    generation: Any | None,
    *,
    output: object,
    usage: object,
) -> None:
    if generation is None:
        return
    capture_content = _truthy("JOBAGENT_LANGFUSE_CAPTURE_CONTENT")
    update: dict[str, object] = {
        "output": output if capture_content else _output_summary(output),
    }
    if isinstance(usage, dict):
        update["usage_details"] = usage
    generation.update(**update)


@contextmanager
def langfuse_agent_trace(
    name: str,
    *,
    metadata: dict[str, object],
) -> Iterator[None]:
    if not _enabled():
        yield
        return
    try:
        from langfuse import get_client
    except ImportError:
        yield
        return
    client = get_client()
    try:
        with client.start_as_current_observation(
            as_type="agent",
            name=name,
            input={"content_redacted": True},
            metadata=metadata,
        ):
            yield
    finally:
        client.flush()


@contextmanager
def langfuse_span(
    name: str,
    *,
    as_type: str = "span",
    metadata: dict[str, object] | None = None,
) -> Iterator[Any | None]:
    if not _enabled():
        yield None
        return
    try:
        from langfuse import get_client
    except ImportError:
        yield None
        return
    client = get_client()
    with client.start_as_current_observation(
        as_type=as_type,
        name=name,
        input={"content_redacted": True},
        metadata=metadata or {},
    ) as span:
        yield span


def _context_sizes(parts: dict[str, object]) -> dict[str, dict[str, int]]:
    result = {}
    for name, value in parts.items():
        serialized = json.dumps(value, ensure_ascii=False, default=str)
        result[name] = {
            "chars": len(serialized),
            "estimated_tokens": max(1, (len(serialized) + 3) // 4),
        }
    return result


def _output_summary(output: object) -> dict[str, object]:
    if isinstance(output, dict):
        return {"content_redacted": True, "keys": sorted(map(str, output.keys()))}
    return {"content_redacted": True, "type": type(output).__name__}


def _enabled() -> bool:
    return _truthy("JOBAGENT_LANGFUSE_ENABLED")


def _truthy(name: str) -> bool:
    return os.getenv(name, "").strip().casefold() in {"1", "true", "yes", "on"}
