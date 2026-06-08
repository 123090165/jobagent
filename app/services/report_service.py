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
from app.schemas.report import AnalysisQualityReport
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


def build_analysis_quality_report(
    resume_profile: ResumeProfile,
    job_analysis: JobAnalysis,
    match_report: MatchReport,
) -> AnalysisQualityReport:
    missing_resume_sections: list[str] = []
    warnings: list[str] = []
    confidence_notes: list[str] = []

    has_project_evidence = _has_explicit_project_evidence(resume_profile)
    has_work_evidence = _has_explicit_work_evidence(resume_profile)

    if not resume_profile.skills:
        missing_resume_sections.append("skills")
        warnings.append("resume has no skills evidence")
    if not has_project_evidence:
        missing_resume_sections.append("projects")
        warnings.append("resume has no project evidence")
    if not has_work_evidence:
        missing_resume_sections.append("work_experiences")
        warnings.append("resume has no work experience evidence")
    if not resume_profile.highlights:
        missing_resume_sections.append("highlights")
        warnings.append("resume has no quantified or highlight evidence")
    if len(resume_profile.missing_info) >= 3:
        warnings.append("resume is missing multiple core details")

    resume_quality_label = _derive_resume_quality_label(
        resume_profile,
        missing_resume_sections,
        has_project_evidence=has_project_evidence,
        has_work_evidence=has_work_evidence,
    )

    missing_jd_sections: list[str] = []
    raw_jd_length = len(job_analysis.raw_jd.strip())
    if not (job_analysis.job_title or "").strip():
        missing_jd_sections.append("job_title")
        warnings.append("JD has no job title")
    if not job_analysis.required_skills:
        missing_jd_sections.append("required_skills")
        warnings.append("JD has no required skills")
    if not job_analysis.responsibilities:
        missing_jd_sections.append("responsibilities")
        warnings.append("JD has no clear responsibilities")
    if not job_analysis.experience_requirements:
        missing_jd_sections.append("experience_requirements")
        warnings.append("JD has no clear experience requirements")
    if raw_jd_length < 80:
        warnings.append("JD is very short")
        if "raw_jd" not in missing_jd_sections:
            missing_jd_sections.append("raw_jd")

    jd_quality_label = _derive_jd_quality_label(job_analysis, missing_jd_sections, raw_jd_length)

    requirement_matches = match_report.requirement_matches
    evidence_backed_matches = [item for item in requirement_matches if item.resume_evidence]
    if not requirement_matches or len(evidence_backed_matches) <= max(1, len(requirement_matches) // 3):
        warnings.append("requirement-level match evidence is sparse")
        confidence_notes.append("Match score may be less reliable because requirement-level evidence is sparse.")

    if match_report.keyword_coverage < 35:
        confidence_notes.append("Keyword coverage is low, so the match score may underrepresent true fit.")

    if resume_quality_label in {"limited", "weak"}:
        confidence_notes.append("Resume evidence is incomplete, so downstream optimization and interview prep may be partial.")
    if jd_quality_label in {"limited", "weak"}:
        confidence_notes.append("JD detail is incomplete, so requirement interpretation may be less precise.")

    overall_quality_label = _derive_overall_quality_label(
        resume_quality_label=resume_quality_label,
        jd_quality_label=jd_quality_label,
        warnings=warnings,
        requirement_matches=requirement_matches,
        evidence_backed_matches=evidence_backed_matches,
    )

    return AnalysisQualityReport(
        resume_quality_label=resume_quality_label,
        jd_quality_label=jd_quality_label,
        overall_quality_label=overall_quality_label,
        warnings=warnings,
        missing_resume_sections=missing_resume_sections,
        missing_jd_sections=missing_jd_sections,
        confidence_notes=confidence_notes,
    )


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


def _render_analysis_quality_section(analysis_quality: AnalysisQualityReport) -> str:
    warning_lines = _bullet_list(analysis_quality.warnings)
    confidence_lines = _bullet_list(analysis_quality.confidence_notes)
    return "\n".join(
        [
            "## Analysis Quality",
            "",
            f"- Overall quality: {analysis_quality.overall_quality_label}",
            f"- Resume quality: {analysis_quality.resume_quality_label}",
            f"- JD quality: {analysis_quality.jd_quality_label}",
            "- Warnings:",
            warning_lines,
            "- Confidence notes:",
            confidence_lines,
        ]
    )


def _derive_resume_quality_label(
    resume_profile: ResumeProfile,
    missing_resume_sections: list[str],
    *,
    has_project_evidence: bool,
    has_work_evidence: bool,
) -> str:
    has_experience_evidence = has_project_evidence or has_work_evidence
    missing_info_count = len(resume_profile.missing_info)
    if not resume_profile.skills and not has_experience_evidence:
        return "weak"
    if resume_profile.skills and has_experience_evidence and missing_info_count <= 1 and resume_profile.highlights:
        return "strong"
    if resume_profile.skills and has_experience_evidence and len(missing_resume_sections) <= 2:
        return "medium"
    if resume_profile.skills:
        return "limited"
    return "weak"


def _has_explicit_project_evidence(resume_profile: ResumeProfile) -> bool:
    raw_text = resume_profile.raw_text.lower()
    if any(marker in raw_text for marker in ["project", "projects", "项目"]):
        return True
    if (
        len(resume_profile.projects) == 1
        and resume_profile.projects[0].description.strip() == resume_profile.raw_text.strip()
        and not resume_profile.projects[0].highlights
    ):
        return False
    return any(
        (project.name and project.name.strip() and project.description.strip() != resume_profile.raw_text.strip())
        or project.highlights
        for project in resume_profile.projects
    )


def _has_explicit_work_evidence(resume_profile: ResumeProfile) -> bool:
    raw_text = resume_profile.raw_text.lower()
    if any(marker in raw_text for marker in ["experience", "work", "intern", "实习", "工作"]):
        return True
    return any(
        (experience.company and experience.company.strip())
        or (experience.role and experience.role.strip())
        or len(experience.technologies) >= 2
        for experience in resume_profile.work_experiences
    )


def _derive_jd_quality_label(
    job_analysis: JobAnalysis,
    missing_jd_sections: list[str],
    raw_jd_length: int,
) -> str:
    has_core_detail = bool(job_analysis.required_skills or job_analysis.responsibilities)
    has_full_detail = bool(
        (job_analysis.job_title or "").strip()
        and job_analysis.required_skills
        and job_analysis.responsibilities
        and job_analysis.experience_requirements
        and raw_jd_length >= 120
    )
    if raw_jd_length < 30 and not has_core_detail:
        return "weak"
    if has_full_detail:
        return "strong"
    if has_core_detail and len(missing_jd_sections) <= 2 and raw_jd_length >= 80:
        return "medium"
    if has_core_detail or raw_jd_length >= 30:
        return "limited"
    return "weak"


def _derive_overall_quality_label(
    *,
    resume_quality_label: str,
    jd_quality_label: str,
    warnings: list[str],
    requirement_matches: list[RequirementMatch],
    evidence_backed_matches: list[RequirementMatch],
) -> str:
    label_order = {"weak": 0, "limited": 1, "medium": 2, "strong": 3}
    reverse_order = {value: key for key, value in label_order.items()}
    score = min(label_order.get(resume_quality_label, 1), label_order.get(jd_quality_label, 1))

    if not requirement_matches or len(evidence_backed_matches) <= max(1, len(requirement_matches) // 3):
        score = min(score, label_order["limited"])
    if len(warnings) >= 4:
        score = min(score, label_order["limited"])
    if len(warnings) >= 6:
        score = min(score, label_order["weak"])

    return reverse_order[score]


def generate_markdown_report(
    *,
    resume_profile: ResumeProfile,
    job_analysis: JobAnalysis,
    match_report: MatchReport,
    optimization_result: ResumeOptimizationResult,
    project_challenge_report: ProjectChallengeReport,
) -> str:
    """Generate a readable Markdown report from structured analysis objects."""
    analysis_quality = build_analysis_quality_report(
        resume_profile=resume_profile,
        job_analysis=job_analysis,
        match_report=match_report,
    )
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

{_render_analysis_quality_section(analysis_quality)}

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
