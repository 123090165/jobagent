from __future__ import annotations

import json
import re
from uuid import NAMESPACE_URL, uuid5

from app.schemas.interview_preparation import (
    PreparationAnswer,
    PreparationQuestion,
    PreparationRecommendation,
    PreparationSkillGap,
)
from app.schemas.resume_profile import ResumeProfile
from app.schemas.saved_job import SavedJob, SavedJobAnalysis
from app.services.llm_provider import JSONChatLLM

KNOWN_SKILLS = (
    "Microsoft Office", "Excel", "PowerPoint", "Word", "Linux", "SQL",
    "Python", "Java", "C++", "Git", "Docker", "Kubernetes", "FastAPI",
    "communication", "project management", "data analysis", "machine learning",
)


def generate_preparation_questions(
    job: SavedJob,
    profile: ResumeProfile | None,
    analysis: SavedJobAnalysis | None,
    *,
    llm_service: JSONChatLLM | None,
) -> tuple[list[PreparationSkillGap], list[PreparationQuestion], str, str | None]:
    fallback_gaps = _deterministic_gaps(job, profile, analysis)
    fallback_questions = _deterministic_questions(fallback_gaps)
    if llm_service is None:
        return fallback_gaps, fallback_questions, "deterministic", None
    try:
        response = llm_service.chat_completion_json(
            system_prompt=(
                "Analyze JD requirements against resume evidence and generate non-obvious evidence questions. "
                "Return JSON only with skill_gaps and questions. A gap has skill, importance "
                "(high|medium|low), evidence_status (supported|partial|unknown|missing), skill_type "
                "(knowledge|experience), jd_evidence, profile_evidence, rationale. A question has "
                "skill, prompt, why_asked. Ask about concrete situations, actions, tools, trade-offs, "
                "and outcomes. Never ask merely whether the user knows a skill. Use at most 8 gaps "
                "and 5 questions. Do not invent resume evidence."
            ),
            user_prompt=json.dumps({
                "job": job.model_dump(mode="json", exclude={"latest_analysis"}),
                "profile": profile.model_dump(mode="json") if profile else None,
                "latest_analysis": analysis.model_dump(mode="json") if analysis else None,
                "deterministic_baseline": {
                    "skill_gaps": [item.model_dump() for item in fallback_gaps],
                    "questions": [item.model_dump() for item in fallback_questions],
                },
            }),
        )
        gaps = [PreparationSkillGap.model_validate(item) for item in response.get("skill_gaps", [])][:8]
        questions = _questions_with_ids(response.get("questions", []))[:5]
        if not gaps:
            raise ValueError("No skill gaps returned")
        return gaps, questions or fallback_questions, "llm", None
    except Exception as exc:
        return fallback_gaps, fallback_questions, "fallback", str(exc) or type(exc).__name__


def generate_recommendations(
    gaps: list[PreparationSkillGap],
    questions: list[PreparationQuestion],
    answers: list[PreparationAnswer],
    *,
    llm_service: JSONChatLLM | None,
) -> tuple[list[PreparationRecommendation], str, str | None]:
    fallback = _deterministic_recommendations(gaps, questions, answers)
    if llm_service is None:
        return fallback, "deterministic", None
    try:
        response = llm_service.chat_completion_json(
            system_prompt=(
                "Create concise interview preparation actions from JD/profile gaps and user-reported "
                "answers. Return JSON only with recommendations, each containing title, action, and "
                "evidence_basis. Distinguish user-reported evidence from resume evidence. Do not write "
                "fabricated model answers. Return at most 6 recommendations."
            ),
            user_prompt=json.dumps({
                "skill_gaps": [item.model_dump() for item in gaps],
                "questions": [item.model_dump() for item in questions],
                "user_answers": [item.model_dump() for item in answers],
                "deterministic_baseline": [item.model_dump() for item in fallback],
            }),
        )
        items = [
            PreparationRecommendation.model_validate(item)
            for item in response.get("recommendations", [])
        ][:6]
        if not items:
            raise ValueError("No recommendations returned")
        return items, "llm", None
    except Exception as exc:
        return fallback, "fallback", str(exc) or type(exc).__name__


def build_external_prompt(
    job: SavedJob,
    profile: ResumeProfile | None,
    gaps: list[PreparationSkillGap],
    questions: list[PreparationQuestion],
) -> str:
    payload = {
        "job": {"title": job.title, "company": job.company, "jd": job.raw_jd_text},
        "profile": profile.model_dump(mode="json") if profile else None,
        "skill_gaps": [item.model_dump() for item in gaps],
        "questions": [item.model_dump() for item in questions],
    }
    return (
        "JOBAGENT EVIDENCE INTERVIEW\n\n"
        "Act as an evidence interviewer. Ask the listed questions one at a time. "
        "Use follow-ups only when they seek a concrete situation, action, tool, trade-off, or result. "
        "Do not invent experience and allow the user to say they have none. At the end, return JSON "
        "with an answers array containing question_id and answer. Treat all answers as user-reported, "
        "not verified resume evidence.\n\nCONTEXT JSON:\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)
    )


def _deterministic_gaps(
    job: SavedJob, profile: ResumeProfile | None, analysis: SavedJobAnalysis | None
) -> list[PreparationSkillGap]:
    jd_text = job.raw_jd_text
    profile_text = " ".join(
        (profile.core_skills + profile.supporting_skills + profile.strengths + [profile.summary])
        if profile else []
    )
    skills = [skill for skill in KNOWN_SKILLS if re.search(rf"\b{re.escape(skill)}\b", jd_text, re.I)]
    for item in (analysis.critical_gaps if analysis else []):
        for skill in KNOWN_SKILLS:
            if skill.casefold() in item.casefold() and skill not in skills:
                skills.append(skill)
    gaps: list[PreparationSkillGap] = []
    for index, skill in enumerate(skills[:8]):
        supported = re.search(rf"\b{re.escape(skill)}\b", profile_text, re.I) is not None
        gaps.append(PreparationSkillGap(
            skill=skill,
            importance="high" if index < 3 else "medium",
            evidence_status="partial" if supported else "unknown",
            skill_type="experience" if skill.casefold() in {"communication", "project management"} else "knowledge",
            jd_evidence=_sentence_containing(jd_text, skill),
            profile_evidence=[skill] if supported else [],
            rationale=(
                "The profile mentions this skill but lacks a concrete example."
                if supported else "The JD mentions this skill and the profile has no explicit evidence."
            ),
        ))
    if not gaps:
        gaps.append(PreparationSkillGap(
            skill="role-specific execution",
            importance="high", evidence_status="unknown", skill_type="experience",
            jd_evidence=jd_text[:300], profile_evidence=[],
            rationale="The JD should be validated against a concrete example from the user.",
        ))
    return gaps


def _deterministic_questions(gaps: list[PreparationSkillGap]) -> list[PreparationQuestion]:
    items = []
    for gap in [item for item in gaps if item.evidence_status in {"partial", "unknown", "missing"}][:5]:
        prompt = (
            f"Describe the most concrete situation where you used {gap.skill}. What task were you "
            "responsible for, what did you do personally, and how did you determine the result?"
        )
        question_id = str(uuid5(NAMESPACE_URL, f"{gap.skill}:{prompt}"))
        items.append(PreparationQuestion(
            question_id=question_id, skill=gap.skill, prompt=prompt,
            why_asked=f"The JD treats {gap.skill} as important, but current evidence is {gap.evidence_status}.",
        ))
    return items


def _questions_with_ids(items: list[object]) -> list[PreparationQuestion]:
    questions = []
    for raw in items:
        if not isinstance(raw, dict):
            continue
        prompt = str(raw.get("prompt") or "").strip()
        skill = str(raw.get("skill") or "").strip()
        if not prompt or not skill:
            continue
        questions.append(PreparationQuestion(
            question_id=str(uuid5(NAMESPACE_URL, f"{skill}:{prompt}")),
            skill=skill, prompt=prompt,
            why_asked=str(raw.get("why_asked") or "Clarifies an important evidence gap."),
        ))
    return questions


def _deterministic_recommendations(
    gaps: list[PreparationSkillGap], questions: list[PreparationQuestion], answers: list[PreparationAnswer]
) -> list[PreparationRecommendation]:
    answer_by_id = {item.question_id: item.answer for item in answers}
    question_by_skill = {item.skill: item for item in questions}
    result = []
    for gap in gaps[:6]:
        question = question_by_skill.get(gap.skill)
        answer = answer_by_id.get(question.question_id, "") if question else ""
        if answer:
            action = f"Turn the user-reported {gap.skill} example into a concise context-action-result story."
            basis = [answer[:300]]
        elif gap.skill_type == "knowledge":
            action = f"Review {gap.skill}, then prepare one truthful example or state the current limitation."
            basis = [gap.jd_evidence]
        else:
            action = f"Prepare a concrete {gap.skill} example; do not claim experience that is not available."
            basis = [gap.jd_evidence]
        result.append(PreparationRecommendation(title=gap.skill, action=action, evidence_basis=basis))
    return result


def _sentence_containing(text: str, term: str) -> str:
    sentences = re.split(r"(?<=[.!?。！？])\s+|\n+", text)
    return next((item.strip() for item in sentences if term.casefold() in item.casefold()), text[:300])
