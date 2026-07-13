from __future__ import annotations

import asyncio
import json

from fastapi.testclient import TestClient

from app.main import app
from app.repositories.resume_profile_repository import resume_profile_repository
from app.repositories.saved_job_repository import saved_job_repository
from experiments.preparation_eval.agent import (
    PreparationEvaluationAgent,
    _candidate_context,
    _check_specific_fact_grounding,
    _normalize_persona_response,
)
from experiments.preparation_eval.schemas import CandidateSelfAssessment

client = TestClient(app)


def test_candidate_self_assessment_accepts_zero_scores() -> None:
    assessment = CandidateSelfAssessment(
        felt_understood=0,
        truthfulness=0,
        learning_value=0,
        interview_value=0,
        actionability=0,
        candidate_reflection="The preparation provided no useful support.",
    )

    assert assessment.actionability == 0


def test_persona_confidence_normalizes_compound_label() -> None:
    response = _normalize_persona_response({
        "skill_calibrations": [{"skill": "Python", "confidence": "medium-high"}]
    })

    assert response["skill_calibrations"][0]["confidence"] == "medium"


def test_candidate_context_excludes_private_notes_and_unrelated_profile_memory() -> None:
    state = {
        "evidence_memory": [
            {"evidence_id": "profile.core_skills.0", "content": "PPG signal processing"},
            {"evidence_id": "profile.supporting_skills.0", "content": "SQL"},
        ],
        "persona_memory": {
            "archetype": "calibrated",
            "confidence_style": "calibrated",
            "communication_style": "balanced",
            "disclosure_style": "honest",
            "skill_calibrations": [{
                "skill": "PPG signal processing",
                "actual_level": "project_experience",
                "confidence": "medium",
                "private_notes": ["Used an unsupported private dataset"],
                "evidence_refs": ["profile.core_skills.0"],
                "scenario_fact_refs": ["scenario.ppg.1"],
            }],
            "synthetic_scenario_memory": [{
                "fact_id": "scenario.ppg.1",
                "statement": "Offline PPG project only",
                "allowed_in_candidate_answer": True,
                "evidence_refs": ["profile.core_skills.0"],
            }],
        },
        "episodic_memory": [],
        "job_context": {"saved_job_id": "j1", "title": "Engineer", "raw_jd_text": "long"},
    }
    question = {"question_id": "q1", "skill": "PPG signal processing"}

    context = _candidate_context(state, question)  # type: ignore[arg-type]

    serialized = json.dumps(context)
    assert '"private_notes":' not in serialized
    assert "unsupported private dataset" not in serialized
    assert "profile.supporting_skills.0" not in serialized
    assert "scenario.ppg.1" in serialized


def test_grounding_checks_claims_against_direct_fact_content() -> None:
    state = {
        "evidence_memory": [{
            "evidence_id": "profile.core_skills.0",
            "content": "ECG signal processing",
        }],
        "persona_memory": {"synthetic_scenario_memory": []},
        "episodic_memory": [{
            "skill": "ECG signal processing",
            "detail": "I used MIT-BIH for QRS detection.",
            "fact_refs": ["profile.core_skills.0"],
            "claims": [{
                "claim": "Used MIT-BIH for QRS detection",
                "fact_refs": ["profile.core_skills.0"],
            }],
        }],
    }

    passed, detail = _check_specific_fact_grounding(state)  # type: ignore[arg-type]

    assert passed is False
    assert "mit-bih" in detail
    assert "qrs" in detail


class FakeEvaluationModel:
    model_name = "fake-evaluator"

    def generate_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        observation_name: str = "evaluation.generate",
        observation_metadata: dict[str, object] | None = None,
        context_parts: dict[str, object] | None = None,
    ) -> dict[str, object]:
        context = json.loads(user_prompt.split("\n", 1)[1])
        if "stable hidden persona" in system_prompt:
            return {
                "archetype": "underconfident but honest",
                "internal_summary": "A cautious analyst whose resume lists tools more strongly than daily usage supports.",
                "confidence_style": "underconfident",
                "communication_style": "terse",
                "disclosure_style": "honest",
                "concerns": ["Overstating technical depth"],
                "goals": ["Find concrete preparation priorities"],
                "skill_calibrations": [
                    {
                        "skill": "Linux",
                        "resume_signal": "Linux appears in supporting skills.",
                        "actual_level": "conceptual_only",
                        "confidence": "low",
                        "private_notes": ["No production administration experience"],
                    }
                ],
            }
        if "acting as the same imperfect candidate" in system_prompt:
            question = context["current_question"]
            skill = question["skill"]
            level = "conceptual_only" if skill in {"Linux", "SQL"} else "project_experience"
            return {
                "question_id": question["question_id"],
                "skill": skill,
                "experience_level": level,
                "detail": None,
                "private_reason": f"I am cautious about my actual {skill} depth.",
                "candidate_reaction": "The fixed options make the question easy to answer honestly.",
            }
        return {
            "felt_understood": 4,
            "truthfulness": 5,
            "learning_value": 4,
            "interview_value": 3,
            "actionability": 4,
            "helpful_items": ["The plan separated learning from experience evidence."],
            "unhelpful_items": [],
            "misunderstandings": [],
            "missing_support": ["A concrete practice exercise would help."],
            "candidate_reflection": "The result respected my uncertainty and gave me a truthful next step.",
        }


def test_persona_agent_uses_profile_memory_and_self_reflects(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("JOBAGENT_DB_PATH", str(tmp_path / "persona-eval.sqlite3"))
    monkeypatch.setenv("JOBAGENT_LANGGRAPH_DB_PATH", str(tmp_path / "persona-eval-graph.sqlite3"))
    auth = client.post(
        "/api/v1/auth/register",
        json={"username": "persona-eval", "password": "password-123"},
    ).json()
    headers = {"Authorization": f"Bearer {auth['access_token']}"}
    session = client.post("/api/v1/profile-sessions", headers=headers).json()
    client.post(
        f"/api/v1/profile-sessions/{session['session_id']}/resume-text",
        headers=headers,
        json={"text": "Name: Sam\nRole: Analyst\nSkills: SQL, Linux\nProject: Built a reporting dashboard."},
    )
    client.post(f"/api/v1/profile-sessions/{session['session_id']}/parse-resume", headers=headers)
    draft = client.post(
        f"/api/v1/profile-sessions/{session['session_id']}/profile-draft",
        headers=headers,
    ).json()["profile_draft"]
    client.post(f"/api/v1/profile-drafts/{draft['profile_draft_id']}/confirm", headers=headers)
    profile = client.get("/api/v1/resume-profiles", headers=headers).json()["items"][0]
    job = client.post(
        "/api/v1/saved-jobs",
        headers=headers,
        json={
            "title": "Operations Analyst",
            "raw_jd_text": "Use SQL and Linux to analyze operational reports and communicate findings.",
        },
    ).json()

    report = asyncio.run(PreparationEvaluationAgent(
        FakeEvaluationModel(),
        preparation_provider="mock",
        persona_archetype="underconfident but honest",
        pause_after=1,
    ).run(
        user_id=profile["user_id"],
        profile_id=profile["resume_profile_id"],
        saved_job_id=job["saved_job_id"],
        profile_memory=resume_profile_repository.get(
            user_id=profile["user_id"], resume_profile_id=profile["resume_profile_id"]
        ).model_dump(mode="json", exclude={"raw_resume_text"}),
        job_context=saved_job_repository.get(
            user_id=profile["user_id"], saved_job_id=job["saved_job_id"]
        ).model_dump(mode="json", exclude={"latest_analysis"}),
    ))

    assert report.persona_memory.confidence_style == "underconfident"
    assert report.episodic_memory
    assert report.preparation_result["status"] == "completed"
    assert report.self_assessment.truthfulness == 5
    assert report.passed is True, report.rule_checks
