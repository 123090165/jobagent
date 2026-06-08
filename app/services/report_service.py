from __future__ import annotations

from app.schemas.job import JobAnalysis
from app.schemas.match import (
    ChallengeQuestion,
    GroundedChallengeQuestion,
    MatchReport,
    ProjectChallengeReport,
    RequirementMatch,
    ResumeOptimizationResult,
    RewriteSuggestion,
)
from app.schemas.resume import ResumeProfile


def _bullet_list(items: list[str]) -> str:
    if not items:
        return "- None"
    return "\n".join(f"- {item}" for item in items)


def _question_list(items: list[ChallengeQuestion]) -> str:
    if not items:
        return "- None"
    lines: list[str] = []
    for item in items:
        lines.append(f"- **Question**: {item.question}")
        lines.append(f"  - Evaluates: {item.evaluates}")
        lines.append(f"  - Answer framework: {item.answer_framework}")
    return "\n".join(lines)


def _normalize_requirement(value: str) -> str:
    return value.strip().lower()


def _index_rewrite_suggestions(items: list[RewriteSuggestion]) -> dict[str, RewriteSuggestion]:
    indexed: dict[str, RewriteSuggestion] = {}
    for item in items:
        key = _normalize_requirement(item.linked_requirement)
        if key and key not in indexed:
            indexed[key] = item
    return indexed


def _index_grounded_questions(
    items: list[GroundedChallengeQuestion],
) -> dict[str, GroundedChallengeQuestion]:
    indexed: dict[str, GroundedChallengeQuestion] = {}
    for item in items:
        key = _normalize_requirement(item.linked_requirement)
        if key and key not in indexed:
            indexed[key] = item
    return indexed


def _render_evidence_list(evidence: list[str]) -> str:
    if not evidence:
        return "  - Not found"
    return "\n".join(f"  - {item}" for item in evidence[:3])


def _render_gap_hint(match: RequirementMatch) -> str:
    parts = [part for part in (match.gap_reason, match.improvement_hint) if part]
    if not parts:
        return "No additional gap or improvement note."
    return " | ".join(parts)


def _render_requirement_chain(
    *,
    match: RequirementMatch,
    rewrite: RewriteSuggestion | None,
    challenge: GroundedChallengeQuestion | None,
) -> str:
    rewrite_text = "No linked rewrite suggestion."
    if rewrite is not None:
        rewrite_text = rewrite.suggested_bullet or rewrite.suggestion or rewrite.reason

    challenge_text = "No linked interview challenge."
    if challenge is not None:
        challenge_text = challenge.question

    return "\n".join(
        [
            f"### Requirement: {match.requirement}",
            f"- Match level: {match.match_level}",
            "- Resume evidence:",
            _render_evidence_list(match.resume_evidence),
            f"- Gap / hint: {_render_gap_hint(match)}",
            f"- Rewrite suggestion: {rewrite_text}",
            f"- Interview challenge: {challenge_text}",
        ]
    )


def _render_evidence_chain_section(
    *,
    match_report: MatchReport,
    optimization_result: ResumeOptimizationResult,
    project_challenge_report: ProjectChallengeReport,
) -> str:
    requirement_matches = match_report.requirement_matches[:5]
    if not requirement_matches:
        return "- No requirement-level evidence is available."

    rewrite_by_requirement = _index_rewrite_suggestions(optimization_result.rewrite_suggestions)
    challenge_by_requirement = _index_grounded_questions(project_challenge_report.grounded_questions)

    lines: list[str] = []
    for match in requirement_matches:
        requirement_key = _normalize_requirement(match.requirement)
        lines.append(
            _render_requirement_chain(
                match=match,
                rewrite=rewrite_by_requirement.get(requirement_key),
                challenge=challenge_by_requirement.get(requirement_key),
            )
        )
    return "\n\n".join(lines)


def generate_markdown_report(
    *,
    resume_profile: ResumeProfile,
    job_analysis: JobAnalysis,
    match_report: MatchReport,
    optimization_result: ResumeOptimizationResult,
    project_challenge_report: ProjectChallengeReport,
) -> str:
    """Generate a readable Markdown report from structured analysis objects."""
    job_title = job_analysis.job_title or "Target Role"
    job_category = job_analysis.job_category or "Unknown"
    skills = ", ".join(resume_profile.skills) if resume_profile.skills else "Not detected"
    required_skills = ", ".join(job_analysis.required_skills) if job_analysis.required_skills else "Not detected"
    preferred_skills = ", ".join(job_analysis.preferred_skills) if job_analysis.preferred_skills else "None"
    missing_info = ", ".join(resume_profile.missing_info) if resume_profile.missing_info else "None"

    return f"""# JobAgent Analysis Report

## 1. Resume Summary

- Detected skills: {skills}
- Project count: {len(resume_profile.projects)}
- Work experience count: {len(resume_profile.work_experiences)}
- Missing information: {missing_info}

## 2. Job Summary

- Job title: {job_title}
- Job category: {job_category}
- Required skills: {required_skills}
- Preferred skills: {preferred_skills}

## 3. Match Overview

- Overall score: {match_report.overall_score:.1f} / 100
- Skill score: {match_report.skill_score:.1f} / 100
- Project score: {match_report.project_score:.1f} / 100
- Experience score: {match_report.experience_score:.1f} / 100
- Keyword coverage: {match_report.keyword_coverage:.1f}%
- Apply recommendation: {match_report.apply_recommendation}

## 4. Strengths

{_bullet_list(match_report.matched_points)}

## 5. Gaps and Risks

### Missing points

{_bullet_list(match_report.missing_points)}

### Risks

{_bullet_list(match_report.risks)}

## 6. Resume Optimization

### Overall issues

{_bullet_list(optimization_result.overall_issues)}

### Keywords to add

{_bullet_list(optimization_result.keywords_to_add)}

### Skills section suggestions

{_bullet_list(optimization_result.skills_section_suggestions)}

### JD-targeted bullets

{_bullet_list(optimization_result.jd_targeted_bullets)}

### Do not exaggerate

{_bullet_list(optimization_result.do_not_exaggerate)}

## 7. JD-Resume Evidence Chain

{_render_evidence_chain_section(
    match_report=match_report,
    optimization_result=optimization_result,
    project_challenge_report=project_challenge_report,
)}

## 8. Project Challenge Questions

### Basic questions

{_question_list(project_challenge_report.basic_questions)}

### Technical deep dive questions

{_question_list(project_challenge_report.technical_deep_dive_questions)}

### Architecture and tradeoff questions

{_question_list(project_challenge_report.architecture_questions + project_challenge_report.tradeoff_questions)}

## 9. One-Week Action Plan

- Day 1: fill in missing project context, ownership, and result signals.
- Day 2: reorder the skills section around the JD's must-have skills.
- Day 3: rewrite the most relevant project bullets as problem -> approach -> tech -> result.
- Day 4: rehearse the challenge questions in this report and mark weak answers.
- Day 5: add one real demo, test artifact, or document that supports project credibility.
- Day 6: tailor one resume version directly against the JD keywords.
- Day 7: review the match gaps and decide whether to apply now or close the gap first.

## 10. Evidence

{_bullet_list(match_report.evidence)}
"""
