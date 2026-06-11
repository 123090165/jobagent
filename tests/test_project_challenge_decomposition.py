from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from app.agents.project_challenge_agent import run_project_challenge_agent
from app.agents.schemas import GeneratedGroundedQuestionDraft
from app.schemas.job import JobAnalysis
from app.schemas.match import MatchReport, ProjectChallengeReport, RequirementMatch
from app.schemas.resume import ProjectExperience, ResumeProfile
from app.services.llm_service import LLMServiceError
from app.services.project_challenge_planner import (
    ChallengeRequirement,
    bind_resume_evidence_for_requirement,
    select_challenge_requirements,
)
from app.services.project_question_generation import generate_grounded_question_with_llm


class SequenceLLMService:
    def __init__(self, payloads: list[dict[str, Any] | Exception]) -> None:
        self.payloads = payloads
        self.calls: list[dict[str, str]] = []

    def chat_completion_json(self, *, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        self.calls.append({"system_prompt": system_prompt, "user_prompt": user_prompt})
        payload = self.payloads.pop(0)
        if isinstance(payload, Exception):
            raise payload
        return payload


def _resume_profile() -> ResumeProfile:
    return ResumeProfile(
        raw_text="Python FastAPI SQL backend project",
        skills=["Python", "FastAPI", "SQL"],
        projects=[
            ProjectExperience(
                name="JobAgent",
                description="Built FastAPI endpoints for resume and JD analysis workflow.",
                technologies=["FastAPI", "Pydantic", "SQL"],
                highlights=["Designed structured analysis workflow."],
                raw_text="Built FastAPI endpoints for resume and JD analysis workflow.",
            )
        ],
    )


def _job_analysis() -> JobAnalysis:
    return JobAnalysis(
        raw_jd="Need FastAPI, SQL, Docker, and architecture tradeoff experience.",
        job_title="Backend Engineer",
        required_skills=["FastAPI", "SQL", "Docker"],
        responsibilities=["Design backend workflow architecture"],
        keywords=["FastAPI", "SQL", "Docker", "architecture"],
        job_category="Software Engineering",
    )


def _match_report() -> MatchReport:
    return MatchReport(
        overall_score=70,
        skill_score=70,
        project_score=70,
        experience_score=70,
        keyword_coverage=70,
        apply_recommendation="Apply with preparation.",
        requirement_matches=[
            RequirementMatch(
                requirement="FastAPI",
                category="skill",
                importance="must",
                match_level="matched",
                resume_evidence=["Skill: FastAPI", "JobAgent | Built FastAPI endpoints"],
            ),
            RequirementMatch(
                requirement="SQL",
                category="skill",
                importance="must",
                match_level="partial",
                resume_evidence=["Skill: SQL"],
            ),
            RequirementMatch(
                requirement="Docker",
                category="skill",
                importance="must",
                match_level="missing",
            ),
        ],
    )


def _valid_question(question_type: str = "technical") -> dict[str, Any]:
    return {
        "question": "How did you use FastAPI in the JobAgent project?",
        "why_asked": "It validates whether the resume evidence is real.",
        "expected_answer_points": ["module ownership", "implementation detail"],
        "risk_level": "medium",
        "question_type": question_type,
    }


def test_select_challenge_requirements_prioritizes_partial_and_limits_items() -> None:
    selected = select_challenge_requirements(
        resume_profile=_resume_profile(),
        job_analysis=_job_analysis(),
        match_report=_match_report(),
        max_items=2,
    )

    assert len(selected) == 2
    assert selected[0].match_level == "partial"
    assert selected[0].requirement == "SQL"
    assert "Skill: SQL" in selected[0].related_resume_evidence
    assert all("SQL" in item or "JobAgent" in item for item in selected[0].related_resume_evidence)


def test_bind_resume_evidence_uses_existing_sources_without_fabrication() -> None:
    evidence = bind_resume_evidence_for_requirement(
        requirement="Docker",
        resume_profile=_resume_profile(),
        match_report=_match_report(),
    )

    assert evidence == []


def test_generate_grounded_question_with_llm_validates_small_json() -> None:
    service = SequenceLLMService([_valid_question("architecture")])

    result = generate_grounded_question_with_llm(
        llm_service=service,  # type: ignore[arg-type]
        requirement=ChallengeRequirement(
            requirement="FastAPI",
            match_level="matched",
            related_resume_evidence=["Skill: FastAPI"],
        ),
        job_title="Backend Engineer",
        job_category="Software Engineering",
    )

    assert isinstance(result, GeneratedGroundedQuestionDraft)
    assert result.question_type == "architecture"
    assert "ResumeProfile" not in service.calls[0]["user_prompt"]


def test_generate_grounded_question_with_llm_propagates_service_errors() -> None:
    service = SequenceLLMService([LLMServiceError("bad json")])

    with pytest.raises(LLMServiceError):
        generate_grounded_question_with_llm(
            llm_service=service,  # type: ignore[arg-type]
            requirement=ChallengeRequirement(requirement="FastAPI", match_level="matched"),
            job_title=None,
            job_category=None,
        )


def test_generate_grounded_question_with_llm_rejects_invalid_enum() -> None:
    payload = _valid_question()
    payload["risk_level"] = "critical"
    service = SequenceLLMService([payload])

    with pytest.raises(ValidationError):
        generate_grounded_question_with_llm(
            llm_service=service,  # type: ignore[arg-type]
            requirement=ChallengeRequirement(requirement="FastAPI", match_level="matched"),
            job_title=None,
            job_category=None,
        )


def test_project_challenge_agent_assembles_all_valid_llm_questions() -> None:
    service = SequenceLLMService([
        _valid_question("basic"),
        _valid_question("technical"),
        _valid_question("tradeoff"),
    ])

    result = run_project_challenge_agent(
        _resume_profile(),
        _job_analysis(),
        match_report=_match_report(),
        use_llm=True,
        service=service,  # type: ignore[arg-type]
    )

    assert result.metadata.mode == "llm"
    assert result.metadata.llm_success_count == 3
    assert result.metadata.fallback_count == 0
    assert len(result.output.grounded_questions) == 3
    assert isinstance(result.output, ProjectChallengeReport)


def test_project_challenge_agent_falls_back_only_for_invalid_item() -> None:
    invalid = _valid_question()
    invalid["question_type"] = "essay"
    service = SequenceLLMService([
        invalid,
        _valid_question("technical"),
        _valid_question("tradeoff"),
    ])

    result = run_project_challenge_agent(
        _resume_profile(),
        _job_analysis(),
        match_report=_match_report(),
        use_llm=True,
        service=service,  # type: ignore[arg-type]
    )

    assert result.metadata.mode == "llm"
    assert result.metadata.llm_success_count == 2
    assert result.metadata.fallback_count == 1
    assert result.metadata.item_fallback_reasons
    assert len(result.output.grounded_questions) == 3
    assert any("actually implemented" in item.question for item in result.output.grounded_questions)


def test_project_challenge_agent_all_invalid_uses_whole_report_fallback() -> None:
    service = SequenceLLMService([
        LLMServiceError("unconfigured"),
        LLMServiceError("unconfigured"),
        LLMServiceError("unconfigured"),
    ])

    result = run_project_challenge_agent(
        _resume_profile(),
        _job_analysis(),
        match_report=_match_report(),
        use_llm=True,
        service=service,  # type: ignore[arg-type]
    )

    assert result.metadata.mode == "fallback"
    assert result.metadata.llm_success_count == 0
    assert result.metadata.fallback_count == 3
    assert result.output.technical_deep_dive_questions
    assert result.output.grounded_questions


def test_project_challenge_agent_mock_mode_is_unchanged() -> None:
    result = run_project_challenge_agent(
        _resume_profile(),
        _job_analysis(),
        match_report=_match_report(),
        use_llm=False,
    )

    assert result.metadata.mode == "mock"
    assert result.metadata.llm_success_count is None
    assert result.output.technical_deep_dive_questions


def test_project_challenge_report_external_schema_is_unchanged() -> None:
    fields = set(ProjectChallengeReport.model_fields)

    assert fields == {
        "basic_questions",
        "technical_deep_dive_questions",
        "architecture_questions",
        "tradeoff_questions",
        "grounded_questions",
        "interviewer_concerns",
        "improvement_suggestions",
    }
