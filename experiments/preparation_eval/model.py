from __future__ import annotations

import os
from typing import Protocol

from app.services.llm_service import LLMConfig, LLMService


class EvaluationModel(Protocol):
    model_name: str

    def generate_json(self, *, system_prompt: str, user_prompt: str) -> dict[str, object]: ...


class OpenAICompatibleEvaluationModel:
    def __init__(self) -> None:
        api_key = os.getenv("JOBAGENT_EVAL_API_KEY", "").strip()
        base_url = os.getenv("JOBAGENT_EVAL_BASE_URL", "https://api.openai.com/v1").strip()
        model = os.getenv("JOBAGENT_EVAL_MODEL", "").strip()
        if not api_key or not model:
            raise RuntimeError(
                "Evaluation model is not configured. Set JOBAGENT_EVAL_API_KEY and JOBAGENT_EVAL_MODEL."
            )
        self.model_name = model
        self._service = LLMService(LLMConfig(
            api_key=api_key,
            base_url=base_url,
            model=model,
            timeout_seconds=_float_env("JOBAGENT_EVAL_TIMEOUT", 180.0),
            temperature=_float_env("JOBAGENT_EVAL_TEMPERATURE", 0.2),
        ))

    def generate_json(self, *, system_prompt: str, user_prompt: str) -> dict[str, object]:
        return self._service.chat_completion_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )


def _float_env(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default
