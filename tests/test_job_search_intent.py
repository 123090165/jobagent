from __future__ import annotations

from app.schemas.confirmed_profile import ConfirmedProfile
from app.services.job_search_intent import build_search_intent
from app.services.llm_service import LLMServiceError


class FakeIntentLLM:
    def __init__(self) -> None:
        self.system_prompt = ""
        self.user_prompt = ""

    def chat_completion_json(self, *, system_prompt: str, user_prompt: str) -> dict:
        self.system_prompt = system_prompt
        self.user_prompt = user_prompt
        return {
            "role_titles": ["Risk Management Intern"],
            "role_families": ["finance"],
            "industry_domains": ["banking", "credit risk"],
            "evidence_skills": ["risk modeling", "financial analysis"],
            "generic_tools": ["Excel", "SQL"],
            "constraints": ["Shenzhen", "internship"],
            "negative_signals": ["sales-only"],
            "broad_queries": ["Risk Management Intern"],
            "domain_queries": ["Risk Management Intern banking"],
            "evidence_queries": ["Risk Management Intern risk modeling"],
            "tool_queries": ["Risk Management Intern Excel SQL"],
            "quality_warnings": [],
        }


class FailingIntentLLM:
    def chat_completion_json(self, *, system_prompt: str, user_prompt: str) -> dict:
        raise LLMServiceError("boom")


def _profile(**updates: object) -> ConfirmedProfile:
    payload = {
        "confirmed_profile_id": "confirmed-1",
        "session_id": "session-1",
        "resume_document_id": "resume-1",
        "parsed_review_id": "review-1",
        "profile_draft_id": "draft-1",
        "summary": "Candidate profile.",
        "target_roles": ["Backend Engineer"],
        "target_directions": ["Platform"],
        "core_skills": ["Python", "SQL"],
        "supporting_skills": [],
        "search_keywords": ["APIs"],
        "preferred_locations": ["Remote"],
        "work_arrangements": ["internship"],
        "strengths": [],
        "risks": [],
        "missing_info_questions": [],
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
    }
    payload.update(updates)
    return ConfirmedProfile.model_validate(payload)


def test_deterministic_intent_handles_finance_profile_without_domain_hardcoding() -> None:
    intent = build_search_intent(
        _profile(
            target_roles=["Risk Management Intern"],
            target_directions=["Banking", "Credit risk"],
            core_skills=["Excel", "SQL", "Python"],
            search_keywords=["Financial analysis", "Risk modeling"],
            preferred_locations=["Shenzhen"],
        ),
        use_llm=False,
    )

    assert "finance" in intent.role_families
    assert "Excel" in intent.generic_tools
    assert "SQL" in intent.generic_tools
    assert "Financial analysis" in intent.industry_domains
    assert "Risk modeling" in intent.evidence_skills
    assert any("Risk Management Intern" in query for query in intent.broad_queries)
    all_terms = " ".join(
        intent.industry_domains
        + intent.evidence_skills
        + intent.broad_queries
        + intent.domain_queries
        + intent.evidence_queries
    ).lower()
    assert "ppg" not in all_terms
    assert "ecg" not in all_terms
    assert "health algorithm" not in all_terms


def test_deterministic_intent_handles_marketing_profile_with_tool_as_weak_signal() -> None:
    intent = build_search_intent(
        _profile(
            target_roles=["Growth Marketing Intern"],
            target_directions=["Consumer products"],
            core_skills=["Excel", "Copywriting"],
            supporting_skills=["A/B testing"],
            search_keywords=["Brand campaign", "Social media"],
        ),
        use_llm=False,
    )

    assert "marketing" in intent.role_families
    assert "Excel" in intent.generic_tools
    assert "Copywriting" in intent.evidence_skills
    assert "A/B testing" in intent.evidence_skills
    assert "Python" not in intent.generic_tools
    assert intent.tool_queries
    assert intent.tool_queries[0].startswith("Growth Marketing Intern")


def test_llm_intent_success_is_schema_normalized() -> None:
    llm = FakeIntentLLM()

    intent = build_search_intent(_profile(), use_llm=True, llm_service=llm)

    assert intent.mode == "llm"
    assert intent.role_titles == ["Risk Management Intern"]
    assert intent.industry_domains == ["banking", "credit risk"]
    assert intent.tool_queries == ["Risk Management Intern Excel SQL"]
    assert "any field" in llm.system_prompt
    assert "Do not hard-code or prefer any example industry" in llm.system_prompt


def test_llm_intent_fallback_returns_deterministic_intent() -> None:
    intent = build_search_intent(_profile(), use_llm=True, llm_service=FailingIntentLLM())

    assert intent.mode == "fallback"
    assert intent.fallback_reason == "LLMServiceError"
    assert intent.role_titles == ["Backend Engineer"]
    assert intent.broad_queries
