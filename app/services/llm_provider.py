from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal, Protocol

from app.services.llm_service import LLMConfig, LLMService, LLMServiceError


LLMProviderName = Literal["mock", "ollama", "deepseek"]
DEFAULT_LLM_PROVIDER: LLMProviderName = "ollama"
DEFAULT_OLLAMA_MODEL = "qwen2.5:1.5b"
DEFAULT_DEEPSEEK_MODEL = "deepseek-v4-flash"
DEFAULT_DEEPSEEK_BASE_URL = "https://api.deepseek.com"


class JSONChatLLM(Protocol):
    def chat_completion_json(self, *, system_prompt: str, user_prompt: str) -> dict:
        ...


@dataclass(frozen=True)
class LLMProviderResolution:
    provider: LLMProviderName
    service: JSONChatLLM | None
    configured: bool
    model: str | None = None
    base_url: str | None = None
    reason: str | None = None


class UnavailableLLMService:
    def __init__(self, reason: str) -> None:
        self.reason = reason

    def chat_completion_json(self, *, system_prompt: str, user_prompt: str) -> dict:
        raise LLMServiceError(self.reason)


def resolve_llm_provider(provider: str | None = None) -> LLMProviderResolution:
    normalized = normalize_llm_provider(provider or os.getenv("JOBAGENT_LLM_PROVIDER"))
    timeout_seconds = _get_float_env("JOBAGENT_LLM_TIMEOUT", 300.0)
    temperature = _get_float_env("JOBAGENT_LLM_TEMPERATURE", 0.0)

    if normalized == "mock":
        return LLMProviderResolution(
            provider="mock",
            service=None,
            configured=True,
            reason="mock provider uses the in-process fake evaluation service",
        )

    if normalized == "ollama":
        base_url = _normalize_ollama_base_url(
            os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        )
        model = os.getenv("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL)
        service = LLMService(
            LLMConfig(
                api_key=os.getenv("OLLAMA_API_KEY", "ollama"),
                base_url=base_url,
                model=model,
                timeout_seconds=timeout_seconds,
                temperature=temperature,
            )
        )
        return LLMProviderResolution(
            provider="ollama",
            service=service,
            configured=True,
            model=model,
            base_url=base_url,
        )

    api_key = os.getenv("DEEPSEEK_API_KEY")
    base_url = os.getenv("DEEPSEEK_BASE_URL", DEFAULT_DEEPSEEK_BASE_URL).rstrip("/")
    model = os.getenv("DEEPSEEK_MODEL", DEFAULT_DEEPSEEK_MODEL)
    if not api_key:
        return LLMProviderResolution(
            provider="deepseek",
            service=UnavailableLLMService(
                "DeepSeek provider is not configured. Set DEEPSEEK_API_KEY first."
            ),
            configured=False,
            model=model,
            base_url=base_url,
            reason="DEEPSEEK_API_KEY is empty",
        )

    service = LLMService(
        LLMConfig(
            api_key=api_key,
            base_url=base_url,
            model=model,
            timeout_seconds=timeout_seconds,
            temperature=temperature,
        )
    )
    return LLMProviderResolution(
        provider="deepseek",
        service=service,
        configured=True,
        model=model,
        base_url=base_url,
    )


def resolve_llm_provider_for_switch(*, use_deepseek: bool) -> LLMProviderResolution:
    return resolve_llm_provider("deepseek" if use_deepseek else "ollama")


def normalize_llm_provider(provider: str | None) -> LLMProviderName:
    normalized = (provider or DEFAULT_LLM_PROVIDER).strip().lower()
    if normalized not in {"mock", "ollama", "deepseek"}:
        raise ValueError(f"Unsupported LLM provider: {provider}")
    return normalized  # type: ignore[return-value]


def _normalize_ollama_base_url(base_url: str) -> str:
    normalized = base_url.rstrip("/")
    if normalized.endswith("/v1"):
        return normalized
    return f"{normalized}/v1"


def _get_float_env(name: str, default: float) -> float:
    value = os.getenv(name)
    if not value:
        return default
    try:
        return float(value)
    except ValueError:
        return default
