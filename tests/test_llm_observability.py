from __future__ import annotations

from contextlib import contextmanager

import langfuse

from app.services.llm_observability import llm_observation_context
from app.services.llm_service import LLMConfig, LLMService


class FakeGeneration:
    def __init__(self) -> None:
        self.update_payload: dict[str, object] = {}

    def update(self, **kwargs) -> None:
        self.update_payload = kwargs


class FakeLangfuse:
    def __init__(self) -> None:
        self.start_payload: dict[str, object] = {}
        self.generation = FakeGeneration()

    @contextmanager
    def start_as_current_observation(self, **kwargs):
        self.start_payload = kwargs
        yield self.generation


def test_llm_service_records_redacted_usage_and_context_sizes(monkeypatch) -> None:
    fake = FakeLangfuse()
    monkeypatch.setenv("JOBAGENT_LANGFUSE_ENABLED", "true")
    monkeypatch.delenv("JOBAGENT_LANGFUSE_CAPTURE_CONTENT", raising=False)
    monkeypatch.setattr(langfuse, "get_client", lambda: fake)
    service = LLMService(LLMConfig(api_key="test", model="test-model"))
    monkeypatch.setattr(service, "_post_chat_completions", lambda payload: {
        "choices": [{"message": {"content": '{"result": "ok"}'}}],
        "usage": {"prompt_tokens": 12, "completion_tokens": 4, "total_tokens": 16},
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
