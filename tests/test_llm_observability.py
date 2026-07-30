"""回归验证llm observability的正常链路、失败边界和兼容契约。"""

from __future__ import annotations

from contextlib import contextmanager

import langfuse

from app.services.llm_observability import (
    anonymous_trace_id,
    langfuse_agent_trace,
    llm_observation_context,
)
from app.services.llm_service import LLMConfig, LLMService


class FakeGeneration:
    """为当前测试场景提供 FakeGeneration 夹具或替身。"""
    def __init__(self) -> None:
        self.update_payload: dict[str, object] = {}

    def update(self, **kwargs) -> None:
        """提供 FakeGeneration.update 所需的测试行为。"""
        self.update_payload = kwargs


class FakeLangfuse:
    """为当前测试场景提供 FakeLangfuse 夹具或替身。"""
    def __init__(self) -> None:
        self.start_payload: dict[str, object] = {}
        self.generation = FakeGeneration()
        self.flushed = False

    @contextmanager
    def start_as_current_observation(self, **kwargs):
        """提供 FakeLangfuse.start_as_current_observation 所需的测试行为。"""
        self.start_payload = kwargs
        yield self.generation

    def flush(self) -> None:
        """提供 FakeLangfuse.flush 所需的测试行为。"""
        self.flushed = True


def test_llm_service_records_redacted_usage_and_context_sizes(monkeypatch) -> None:
    fake = FakeLangfuse()
    monkeypatch.setenv("JOBAGENT_LANGFUSE_ENABLED", "true")
    monkeypatch.delenv("JOBAGENT_LANGFUSE_CAPTURE_CONTENT", raising=False)
    monkeypatch.setattr(langfuse, "get_client", lambda: fake)
    service = LLMService(LLMConfig(api_key="test", model="test-model"))
    monkeypatch.setattr(service, "_post_chat_completions", lambda payload: {
        "choices": [{"message": {"content": '{"result": "ok"}'}}],
        "usage": {
            "prompt_tokens": 12,
            "completion_tokens": 4,
            "total_tokens": 16,
            "cost": 0.02,
        },
    })

    with llm_observation_context(
        "evaluation.answer_question",
        metadata={"question_id": "q1"},
        context_parts={"profile": {"skill": "PPG"}, "question": "Current level?"},
    ):
        result = service.chat_completion_json(system_prompt="system", user_prompt="user")

    assert result == {"result": "ok"}
    assert fake.start_payload["name"] == "evaluation.answer_question"
    assert fake.start_payload["input"]["content_redacted"] is True
    sizes = fake.start_payload["metadata"]["context_sizes"]
    assert sizes["profile"]["chars"] > 0
    assert fake.generation.update_payload["usage_details"]["total_tokens"] == 16
    assert fake.generation.update_payload["output"] == {
        "content_redacted": True,
        "keys": ["result"],
    }
    assert "cost" not in fake.generation.update_payload["usage_details"]


def test_anonymous_trace_id_is_stable_and_namespaced() -> None:
    first = anonymous_trace_id("user", "private-user-id")

    assert first == anonymous_trace_id("user", "private-user-id")
    assert first != anonymous_trace_id("profile", "private-user-id")
    assert "private-user-id" not in first


def test_observation_can_force_redaction_when_global_capture_is_enabled(monkeypatch) -> None:
    fake = FakeLangfuse()
    monkeypatch.setenv("JOBAGENT_LANGFUSE_ENABLED", "true")
    monkeypatch.setenv("JOBAGENT_LANGFUSE_CAPTURE_CONTENT", "true")
    monkeypatch.setattr(langfuse, "get_client", lambda: fake)
    service = LLMService(LLMConfig(api_key="test", model="test-model"))
    monkeypatch.setattr(service, "_post_chat_completions", lambda payload: {
        "choices": [{"message": {"content": '{"answer": "private"}'}}],
        "usage": {},
    })

    with llm_observation_context(
        "chat.answer",
        metadata={"force_content_redacted": True},
    ):
        service.chat_completion_json(system_prompt="private system", user_prompt="private user")

    assert fake.start_payload["input"]["content_redacted"] is True
    assert fake.generation.update_payload["output"]["content_redacted"] is True


def test_agent_trace_propagates_queryable_attributes_and_flushes(monkeypatch) -> None:
    fake = FakeLangfuse()
    propagated: dict[str, object] = {}

    @contextmanager
    def fake_propagate_attributes(**kwargs):
        propagated.update(kwargs)
        yield

    monkeypatch.setenv("JOBAGENT_LANGFUSE_ENABLED", "true")
    monkeypatch.setattr(langfuse, "get_client", lambda: fake)
    monkeypatch.setattr(langfuse, "propagate_attributes", fake_propagate_attributes)

    with langfuse_agent_trace(
        "preparation-evaluation",
        metadata={"profile_ref": "profile-safe", "attempt": 1},
        user_id="private-user-id",
        session_id="evaluation-id",
        tags=["preparation", "evaluation"],
        version="preparation-eval-v1",
    ) as trace:
        trace.update(output={"passed": True})

    assert propagated == {
        "trace_name": "preparation-evaluation",
        "user_id": anonymous_trace_id("user", "private-user-id"),
        "session_id": "evaluation-id",
        "tags": ["preparation", "evaluation"],
        "version": "preparation-eval-v1",
        "metadata": {"profile_ref": "profile-safe", "attempt": "1"},
    }
    assert fake.start_payload["as_type"] == "agent"
    assert fake.flushed is True
