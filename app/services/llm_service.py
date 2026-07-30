"""实现 OpenAI-compatible JSON 请求、响应解析、重试边界和错误归一。"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from app.services.llm_observability import (
    langfuse_generation,
    update_langfuse_generation,
)


class LLMServiceError(RuntimeError):
    """Raised when the LLM service cannot return a usable response."""


@dataclass(frozen=True)
class LLMConfig:
    api_key: str | None
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-4o-mini"
    timeout_seconds: float = 60.0
    temperature: float = 0.1

    @classmethod
    def from_env(cls) -> "LLMConfig":
        timeout = _get_float_env("JOBAGENT_LLM_TIMEOUT", 60.0)
        temperature = _get_float_env("JOBAGENT_LLM_TEMPERATURE", 0.1)
        return cls(
            api_key=os.getenv("JOBAGENT_LLM_API_KEY"),
            base_url=os.getenv("JOBAGENT_LLM_BASE_URL", "https://api.openai.com/v1"),
            model=os.getenv("JOBAGENT_LLM_MODEL", "gpt-4o-mini"),
            timeout_seconds=timeout,
            temperature=temperature,
        )

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key and self.model and self.base_url)


class LLMService:
    """Small OpenAI-compatible chat completions client.

    The project intentionally uses the standard library here so the MVP does not
    depend on a specific SDK. A later version can swap this for an official SDK.
    """

    def __init__(self, config: LLMConfig | None = None) -> None:
        self.config = config or LLMConfig.from_env()

    def chat_completion_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        expected_root_key: str | None = None,
    ) -> dict[str, Any]:
        """请求一次 JSON 对话补全，并校验根结构后返回解析结果。"""
        if not self.config.is_configured:
            raise LLMServiceError("LLM is not configured. Set JOBAGENT_LLM_API_KEY first.")

        payload = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": self.config.temperature,
            "response_format": {"type": "json_object"},
        }
        with langfuse_generation(
            model=self.config.model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        ) as generation:
            raw_response = self._post_chat_completions(payload)
            content = _extract_message_content(raw_response)
            parsed = parse_json_object(content, expected_root_key=expected_root_key)
            update_langfuse_generation(
                generation,
                output=parsed,
                usage=raw_response.get("usage"),
            )
            return parsed

    def _post_chat_completions(self, payload: dict[str, Any]) -> dict[str, Any]:
        endpoint = f"{self.config.base_url.rstrip('/')}/chat/completions"
        request = urllib.request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.config.timeout_seconds) as response:
                body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise LLMServiceError(f"LLM HTTP error {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise LLMServiceError(f"LLM request failed: {exc.reason}") from exc
        except TimeoutError as exc:
            raise LLMServiceError("LLM request timed out") from exc

        try:
            decoded = json.loads(body)
        except json.JSONDecodeError as exc:
            raise LLMServiceError("LLM response is not valid JSON") from exc
        if not isinstance(decoded, dict):
            raise LLMServiceError("LLM response must be a JSON object")
        return decoded


def is_llm_configured() -> bool:
    return LLMConfig.from_env().is_configured


def parse_json_object(
    text: str,
    *,
    expected_root_key: str | None = None,
) -> dict[str, Any]:
    cleaned = _strip_code_fence(text.strip())
    try:
        decoded = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise LLMServiceError("LLM message does not contain a JSON object")
        decoded = json.loads(cleaned[start : end + 1])

    if isinstance(decoded, list) and expected_root_key:
        return {expected_root_key: decoded}
    if not isinstance(decoded, dict):
        raise LLMServiceError("LLM JSON output must be an object")
    return decoded


def _extract_message_content(response: dict[str, Any]) -> str:
    try:
        content = response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMServiceError("LLM response does not contain message content") from exc

    if not isinstance(content, str) or not content.strip():
        raise LLMServiceError("LLM message content is empty")
    return content


def _strip_code_fence(text: str) -> str:
    if not text.startswith("```"):
        return text
    lines = text.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _get_float_env(name: str, default: float) -> float:
    value = os.getenv(name)
    if not value:
        return default
    try:
        return float(value)
    except ValueError:
        return default
