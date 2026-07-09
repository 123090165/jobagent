from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.llm_service import LLMServiceError


class NoNetworkJSONLLM:
    def chat_completion_json(self, *, system_prompt: str, user_prompt: str) -> dict:
        raise LLMServiceError("Test LLM provider is disabled to avoid network calls.")


@pytest.fixture(autouse=True)
def disable_application_llm_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def resolve_for_switch(*, use_deepseek: bool) -> SimpleNamespace:
        return SimpleNamespace(
            provider="deepseek" if use_deepseek else "ollama",
            service=NoNetworkJSONLLM(),
        )

    def resolve_provider(provider: str | None = None) -> SimpleNamespace:
        return SimpleNamespace(
            provider=provider or "deepseek",
            service=NoNetworkJSONLLM(),
            configured=provider != "deepseek",
            model=None,
            base_url=None,
            reason="Test LLM provider is disabled to avoid network calls.",
        )

    monkeypatch.setattr(
        "app.application.resume_review_usecases.resolve_llm_provider_for_switch",
        resolve_for_switch,
    )
    monkeypatch.setattr(
        "app.application.job_search_usecases.resolve_llm_provider_for_switch",
        resolve_for_switch,
        raising=False,
    )
    monkeypatch.setattr(
        "app.application.job_search_usecases.resolve_llm_provider",
        resolve_provider,
    )
