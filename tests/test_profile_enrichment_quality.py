"""回归验证profile enrichment quality的正常链路、失败边界和兼容契约。"""

from __future__ import annotations

from app.schemas.profile_enrichment import EvidenceBoundSuggestion
from app.services.profile_enrichment_quality import validate_evidence_bound_suggestion

SOURCE_TEXT = "JobAgent project built FastAPI APIs and passed 300 tests."
FULL_RESUME_TEXT = f"Skills: Python, FastAPI\nProjects:\n{SOURCE_TEXT}"


def _suggestion(**overrides) -> EvidenceBoundSuggestion:
    payload = {
        "section": "project",
        "item_index": 0,
        "field": "description",
        "suggested_value": "Built FastAPI APIs",
        "source_quote": "built FastAPI APIs",
        "confidence_label": "medium",
    }
    payload.update(overrides)
    return EvidenceBoundSuggestion(**payload)


def test_source_quote_not_in_source_text_is_rejected() -> None:
    result = validate_evidence_bound_suggestion(
        suggestion=_suggestion(source_quote="invented quote"),
        source_text=SOURCE_TEXT,
        full_resume_text=FULL_RESUME_TEXT,
    )

    assert result is None


def test_unsupported_percentage_or_number_is_rejected() -> None:
    result = validate_evidence_bound_suggestion(
        suggestion=_suggestion(
            suggested_value="Improved latency by 50ms",
            source_quote="built FastAPI APIs",
        ),
        source_text=SOURCE_TEXT,
        full_resume_text=FULL_RESUME_TEXT,
    )

    assert result is None


def test_unsupported_skill_injection_is_rejected() -> None:
    result = validate_evidence_bound_suggestion(
        suggestion=_suggestion(
            field="technical_stack",
            suggested_value=["FastAPI", "Kubernetes"],
            source_quote="built FastAPI APIs",
        ),
        source_text=SOURCE_TEXT,
        full_resume_text=FULL_RESUME_TEXT,
        known_skills=["FastAPI"],
    )

    assert result is None


def test_grounded_suggestion_with_exact_quote_is_accepted() -> None:
    result = validate_evidence_bound_suggestion(
        suggestion=_suggestion(
            suggested_value="Passed 300 tests",
            source_quote="passed 300 tests",
        ),
        source_text=SOURCE_TEXT,
        full_resume_text=FULL_RESUME_TEXT,
    )

    assert result is not None
    assert result.source_quote == "passed 300 tests"


def test_empty_suggestion_is_rejected() -> None:
    result = validate_evidence_bound_suggestion(
        suggestion=_suggestion(suggested_value="", source_quote="built FastAPI APIs"),
        source_text=SOURCE_TEXT,
        full_resume_text=FULL_RESUME_TEXT,
    )

    assert result is None
