"""基于收藏职位的 JD、搜索分析和画像快照生成版本化行动简报。"""

from __future__ import annotations

import json

from app.schemas.job_brief import JobBriefContent
from app.schemas.resume_profile import ResumeProfile
from app.schemas.saved_job import SavedJob, SavedJobAnalysis
from app.services.llm_provider import JSONChatLLM


def generate_job_brief_content(
    job: SavedJob,
    profile: ResumeProfile | None,
    analysis: SavedJobAnalysis | None,
    *,
    llm_service: JSONChatLLM | None = None,
) -> tuple[JobBriefContent, str, str | None]:
    fallback = _deterministic_brief(job, profile, analysis)
    if llm_service is None:
        return fallback, "deterministic", None
    try:
        response = llm_service.chat_completion_json(
            system_prompt=(
                "Create an evidence-grounded job application brief. Return JSON only with "
                "exactly these keys: decision_summary (string), fit_signals, evidence_gaps, "
                "resume_actions, interview_focus, next_actions (string arrays). Never invent "
                "resume evidence or job requirements. Keep each array to at most five concise items."
            ),
            user_prompt=json.dumps(
                {
                    "saved_job": job.model_dump(mode="json", exclude={"latest_analysis"}),
                    "resume_profile": profile.model_dump(mode="json") if profile else None,
                    "latest_analysis": analysis.model_dump(mode="json") if analysis else None,
                    "deterministic_baseline": fallback.model_dump(mode="json"),
                }
            ),
        )
        content = JobBriefContent.model_validate(response)
        return _bounded(content), "llm", None
    except Exception as exc:
        return fallback, "fallback", str(exc) or type(exc).__name__


def _deterministic_brief(
    job: SavedJob,
    profile: ResumeProfile | None,
    analysis: SavedJobAnalysis | None,
) -> JobBriefContent:
    strengths = list(analysis.matched_strengths[:5]) if analysis else []
    gaps = list(analysis.critical_gaps[:5]) if analysis else []
    resume_actions = list(analysis.resume_actions[:5]) if analysis else []
    interview_focus = list(analysis.interview_questions[:5]) if analysis else []
    if not strengths and profile is not None:
        jd_text = job.raw_jd_text.casefold()
        strengths = [skill for skill in profile.core_skills if skill.casefold() in jd_text][:5]
    if not gaps:
        gaps = ["Validate the JD's must-have requirements against concrete resume evidence."]
    if not resume_actions:
        resume_actions = ["Prioritize verified experience that directly matches this JD."]
    if not interview_focus:
        interview_focus = [f"Prepare evidence for your fit with the {job.title} role."]
    score = analysis.match_score if analysis else None
    recommendation = analysis.recommendation if analysis else None
    summary = recommendation or (
        f"Review this {job.title} opportunity"
        + (f" with the current match score of {score}." if score is not None else " before applying.")
    )
    return JobBriefContent(
        decision_summary=summary,
        fit_signals=strengths,
        evidence_gaps=gaps,
        resume_actions=resume_actions,
        interview_focus=interview_focus,
        next_actions=[
            "Verify that the listing is current and the role details are complete.",
            "Resolve critical evidence gaps before tailoring or applying.",
        ],
    )


def _bounded(content: JobBriefContent) -> JobBriefContent:
    return content.model_copy(
        update={
            field: getattr(content, field)[:5]
            for field in (
                "fit_signals",
                "evidence_gaps",
                "resume_actions",
                "interview_focus",
                "next_actions",
            )
        }
    )
