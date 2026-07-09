from __future__ import annotations

from app.services.llm_provider import (
    DEFAULT_LLM_PROVIDER,
    DEFAULT_DEEPSEEK_BASE_URL,
    DEFAULT_DEEPSEEK_MODEL,
    DEFAULT_OLLAMA_MODEL,
    normalize_llm_provider,
    resolve_llm_provider_for_switch,
    resolve_llm_provider,
)
from app.services.llm_service import LLMService


def test_normalize_llm_provider_accepts_supported_values() -> None:
    assert normalize_llm_provider("mock") == "mock"
    assert normalize_llm_provider("ollama") == "ollama"
    assert normalize_llm_provider("deepseek") == "deepseek"


def test_default_provider_is_deepseek() -> None:
    assert DEFAULT_LLM_PROVIDER == "deepseek"


def test_resolve_mock_provider_returns_fake_marker() -> None:
    resolution = resolve_llm_provider("mock")

    assert resolution.provider == "mock"
    assert resolution.configured is True
    assert resolution.service is None


def test_resolve_ollama_provider_uses_v1_base_url(monkeypatch) -> None:
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")
    monkeypatch.setenv("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL)
    monkeypatch.setenv("JOBAGENT_LLM_TIMEOUT", "300")
    monkeypatch.setenv("JOBAGENT_LLM_TEMPERATURE", "0")

    resolution = resolve_llm_provider("ollama")

    assert resolution.provider == "ollama"
    assert resolution.configured is True
    assert resolution.base_url == "http://localhost:11434/v1"
    assert resolution.model == DEFAULT_OLLAMA_MODEL
    assert isinstance(resolution.service, LLMService)


def test_resolve_deepseek_provider_requires_env_key(monkeypatch) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setenv("DEEPSEEK_BASE_URL", DEFAULT_DEEPSEEK_BASE_URL)
    monkeypatch.setenv("DEEPSEEK_MODEL", DEFAULT_DEEPSEEK_MODEL)

    resolution = resolve_llm_provider("deepseek")

    assert resolution.provider == "deepseek"
    assert resolution.configured is False
    assert resolution.base_url == DEFAULT_DEEPSEEK_BASE_URL
    assert resolution.model == DEFAULT_DEEPSEEK_MODEL
    assert resolution.service is not None


def test_resolve_deepseek_provider_uses_default_model(monkeypatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.delenv("DEEPSEEK_MODEL", raising=False)
    monkeypatch.delenv("DEEPSEEK_BASE_URL", raising=False)

    resolution = resolve_llm_provider("deepseek")

    assert resolution.provider == "deepseek"
    assert resolution.configured is True
    assert resolution.model == DEFAULT_DEEPSEEK_MODEL
    assert resolution.base_url == DEFAULT_DEEPSEEK_BASE_URL
    assert isinstance(resolution.service, LLMService)


def test_resolve_llm_provider_for_switch_maps_false_to_ollama(monkeypatch) -> None:
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")

    resolution = resolve_llm_provider_for_switch(use_deepseek=False)

    assert resolution.provider == "ollama"
    assert resolution.model == DEFAULT_OLLAMA_MODEL


def test_resolve_llm_provider_for_switch_maps_true_to_deepseek(monkeypatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")

    resolution = resolve_llm_provider_for_switch(use_deepseek=True)

    assert resolution.provider == "deepseek"
    assert resolution.model == DEFAULT_DEEPSEEK_MODEL
