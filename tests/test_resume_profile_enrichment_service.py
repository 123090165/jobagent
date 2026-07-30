"""回归验证可复用简历画像的正常链路、失败边界和兼容契约。"""

from __future__ import annotations

from typing import Any

from app.services.llm_service import LLMServiceError
from app.services.resume_profile_enrichment_service import (
    UNAVAILABLE_WARNING,
    build_resume_profile_enrichment,
)

RESUME_TEXT = """
Technical Skills: Python, FastAPI, PyTorch
Education:
B.S. in Computer Science, CUHKSZ
Experience:
Research Assistant, CUHKSZ AI Lab
- Built a PyTorch audio classification baseline with 95% validation accuracy.
Projects:
JobAgent - built FastAPI APIs and passed 300 tests.
"""


class FakeLLMService:
    """为当前测试场景提供 FakeLLMService 夹具或替身。"""
    def __init__(self, payloads: list[dict[str, Any] | Exception]) -> None:
        self.payloads = list(payloads)
        self.calls: list[dict[str, str]] = []

    def chat_completion_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
    ) -> dict[str, Any]:
        """提供 FakeLLMService.chat_completion_json 所需的测试行为。"""
        self.calls.append({"system_prompt": system_prompt, "user_prompt": user_prompt})
        if not self.payloads:
            raise LLMServiceError("no fake payload left")
        payload = self.payloads.pop(0)
        if isinstance(payload, Exception):
            raise payload
        return payload


def _grounded_project_payload() -> dict[str, Any]:
    return {
        "section": "project",
        "item_index": 0,
        "suggestions": [
            {
                "section": "project",
                "item_index": 0,
                "field": "description",
                "suggested_value": "Built FastAPI APIs and passed 300 tests",
                "source_quote": "built FastAPI APIs and passed 300 tests",
                "confidence_label": "medium",
                "warnings": [],
            }
        ],
        "clarifying_questions": ["What user workflow did JobAgent support?"],
    }


def _hallucinated_metric_payload() -> dict[str, Any]:
    return {
        "section": "project",
        "item_index": 0,
        "suggestions": [
            {
                "section": "project",
                "item_index": 0,
                "field": "description",
                "suggested_value": "Reduced latency by 50ms",
                "source_quote": "built FastAPI APIs",
                "confidence_label": "medium",
                "warnings": [],
            }
        ],
        "clarifying_questions": [],
    }


def test_use_llm_false_returns_baseline_review_only() -> None:
    result = build_resume_profile_enrichment(
        resume_text=RESUME_TEXT,
        target_roles=["Backend Engineer"],
        use_llm=False,
    )

    assert result.baseline_review.parsed_profile.raw_text
    assert result.enrichment_suggestions == []
    assert result.llm_success_count == 0
    assert result.fallback_count == 0


def test_grounded_project_enrichment_succeeds() -> None:
    service = FakeLLMService([_grounded_project_payload()])

    result = build_resume_profile_enrichment(
        resume_text="Projects:\nJobAgent - built FastAPI APIs and passed 300 tests.",
        target_roles=["Backend Engineer"],
        use_llm=True,
        llm_service=service,  # type: ignore[arg-type]
    )

    assert result.llm_success_count == 1
    assert result.enrichment_suggestions
    assert result.enrichment_suggestions[0].source_quote == (
        "built FastAPI APIs and passed 300 tests"
    )


def test_hallucinated_metric_is_discarded() -> None:
    service = FakeLLMService([_hallucinated_metric_payload()])

    result = build_resume_profile_enrichment(
        resume_text="Projects:\nJobAgent - built FastAPI APIs.",
        use_llm=True,
        llm_service=service,  # type: ignore[arg-type]
    )

    assert result.llm_success_count == 1
    assert result.discarded_suggestion_count == 1
    assert result.enrichment_suggestions == []


def test_one_item_llm_failure_increments_fallback_but_overall_returns() -> None:
    service = FakeLLMService(
        [
            _grounded_project_payload(),
            LLMServiceError("fake work failure"),
            LLMServiceError("fake education failure"),
        ]
    )

    result = build_resume_profile_enrichment(
        resume_text=RESUME_TEXT,
        use_llm=True,
        llm_service=service,  # type: ignore[arg-type]
    )

    assert result.baseline_review.parsed_profile.raw_text
    assert result.llm_success_count == 1
    assert result.fallback_count >= 1
    assert result.enrichment_suggestions


def test_all_llm_failures_still_return_baseline_review() -> None:
    service = FakeLLMService([LLMServiceError("boom")] * 4)

    result = build_resume_profile_enrichment(
        resume_text=RESUME_TEXT,
        use_llm=True,
        llm_service=service,  # type: ignore[arg-type]
    )

    assert result.baseline_review.parsed_profile.raw_text
    assert result.enrichment_suggestions == []
    assert result.llm_success_count == 0
    assert result.fallback_count >= 1
    assert UNAVAILABLE_WARNING in result.quality_warnings


def test_missing_info_questions_include_baseline_questions() -> None:
    result = build_resume_profile_enrichment(
        resume_text="Skills: Python, FastAPI",
        use_llm=False,
    )

    assert result.baseline_review.missing_info_questions
    for question in result.baseline_review.missing_info_questions:
        assert question in result.missing_info_questions
