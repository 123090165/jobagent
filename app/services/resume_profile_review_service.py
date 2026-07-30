"""生成画像审阅结果、缺失信息问题和用户可确认的修改建议。"""

from __future__ import annotations

from app.agents.resume_parse_agent import parse_resume
from app.schemas.profile_review import (
    ConfirmedResumeProfileResult,
    ResumeProfileConfirmationSummary,
    ResumeProfileReviewResult,
    ResumeProfileUserEdits,
)
from app.schemas.resume import ProjectExperience, ResumeProfile
from app.services.errors import JobAgentError
from app.services.llm_provider import JSONChatLLM
from app.services.resume_llm_review_service import build_llm_assisted_resume_review

EDITABLE_SECTIONS = [
    "target_roles",
    "skills",
    "projects",
    "work_experiences",
    "education",
    "constraints",
]

TARGET_ROLE_QUESTION = (
    "What target roles should this profile prioritize, such as AI Agent Engineer, "
    "Backend Engineer, or Embedded Software Engineer?"
)
PROJECT_EVIDENCE_QUESTION = (
    "Which project best demonstrates your target role fit? Please add project goal, "
    "technologies, your responsibilities, and outcomes."
)
THIN_PROJECT_QUESTION = (
    "For your strongest project, what exactly did you build, which technologies did "
    "you use, and what measurable result can you show?"
)
WORK_EXPERIENCE_QUESTION = (
    "Do you have internship, lab, research, or course project experience that should "
    "be treated as work-like evidence?"
)
OUTCOMES_QUESTION = (
    "Can you add measurable outcomes, such as number of APIs, tests passed, latency, "
    "users, dataset size, or accuracy?"
)

SUGGESTED_EDITS = [
    "Add target roles before job search.",
    "Add technologies and responsibilities to your strongest project.",
    "Add measurable outcomes to improve matching and resume rewrite quality.",
    "Clarify whether projects are course projects, personal projects, internships, or research.",
]


def build_resume_profile_review(
    resume_text: str,
    target_roles: list[str] | None = None,
    *,
    use_llm: bool = False,
    llm_service: JSONChatLLM | None = None,
    llm_provider: str | None = None,
) -> ResumeProfileReviewResult:
    normalized_resume = resume_text.strip()
    if not normalized_resume:
        raise JobAgentError(
            "resume_text is required",
            error_code="resume_text_required",
        )

    deterministic_profile = parse_resume(normalized_resume)
    analysis_mode = "deterministic"
    analysis_provider: str | None = None
    analysis_warnings: list[str] = []
    parsed_profile = deterministic_profile
    if use_llm:
        analysis_provider = llm_provider
        parsed_profile, analysis_warnings, analysis_mode = build_llm_assisted_resume_review(
            normalized_resume,
            deterministic_profile,
            llm_service=llm_service,
        )
    normalized_target_roles = _normalize_list(target_roles)
    profile_target_roles = _normalize_list(getattr(parsed_profile, "target_roles", []))
    quality_warnings = _build_quality_warnings(
        parsed_profile,
        _dedupe_list([*normalized_target_roles, *profile_target_roles]),
    )
    quality_warnings = _dedupe_list([*quality_warnings, *analysis_warnings])
    missing_info_questions = _build_missing_info_questions(parsed_profile, quality_warnings)
    confidence_label = _build_confidence_label(parsed_profile, quality_warnings)

    return ResumeProfileReviewResult(
        parsed_profile=parsed_profile,
        quality_warnings=quality_warnings,
        missing_info_questions=missing_info_questions,
        suggested_edits=SUGGESTED_EDITS.copy(),
        editable_sections=EDITABLE_SECTIONS.copy(),
        confidence_label=confidence_label,
        analysis_mode=analysis_mode,
        analysis_provider=analysis_provider,
        analysis_warnings=analysis_warnings,
    )


def confirm_resume_profile(
    parsed_profile: ResumeProfile,
    user_edits: ResumeProfileUserEdits,
) -> ConfirmedResumeProfileResult:
    normalized_edits = _normalize_user_edits(user_edits)
    confirmed_profile = parsed_profile.model_copy(deep=True)
    if normalized_edits.additional_skills:
        confirmed_profile.skills = _merge_skills(
            confirmed_profile.skills,
            normalized_edits.additional_skills,
        )

    confirmation_summary = _build_confirmation_summary(normalized_edits)
    remaining_warnings = _build_remaining_warnings(confirmed_profile, normalized_edits)
    confidence_label = _build_confirmed_confidence_label(
        confirmed_profile,
        normalized_edits,
        remaining_warnings,
    )

    return ConfirmedResumeProfileResult(
        confirmed_profile=confirmed_profile,
        user_confirmed_data=normalized_edits,
        confirmation_summary=confirmation_summary,
        remaining_warnings=remaining_warnings,
        confidence_label=confidence_label,
    )


def _build_quality_warnings(
    profile: ResumeProfile,
    target_roles: list[str] | None = None,
) -> list[str]:
    warnings: list[str] = []
    has_project_evidence = _has_project_evidence(profile)
    normalized_target_roles = _normalize_list(target_roles)

    if not profile.skills:
        warnings.append("resume profile has no clear skills")
    if not has_project_evidence:
        warnings.append("resume profile has no project evidence")
    if not profile.work_experiences:
        warnings.append("resume profile has no work experience evidence")
    if has_project_evidence and any(_is_project_too_thin(project) for project in profile.projects):
        warnings.append("project evidence may be too thin for matching")

    if not normalized_target_roles:
        warnings.append("target role is not explicit")

    if not profile.highlights:
        warnings.append("resume profile has no highlights or measurable outcomes")

    return warnings


def _build_confirmation_summary(
    user_edits: ResumeProfileUserEdits,
) -> ResumeProfileConfirmationSummary:
    confirmed_sections: list[str] = []
    if user_edits.target_roles:
        confirmed_sections.append("target_roles")
    if user_edits.preferred_locations:
        confirmed_sections.append("preferred_locations")
    if user_edits.additional_skills:
        confirmed_sections.append("skills")
    if user_edits.project_clarifications:
        confirmed_sections.append("projects")
    if user_edits.work_experience_clarifications:
        confirmed_sections.append("work_experiences")
    if user_edits.constraints:
        confirmed_sections.append("constraints")
    if user_edits.notes:
        confirmed_sections.append("notes")

    return ResumeProfileConfirmationSummary(
        confirmed_sections=confirmed_sections,
        added_target_roles=user_edits.target_roles.copy(),
        added_skills=user_edits.additional_skills.copy(),
        added_project_clarifications_count=len(user_edits.project_clarifications),
        added_work_experience_clarifications_count=len(
            user_edits.work_experience_clarifications
        ),
        constraints_count=len(user_edits.constraints),
    )


def _build_remaining_warnings(
    profile: ResumeProfile,
    user_edits: ResumeProfileUserEdits,
) -> list[str]:
    warnings = _build_quality_warnings(profile, user_edits.target_roles)

    if user_edits.additional_skills:
        warnings = [
            warning
            for warning in warnings
            if warning != "resume profile has no clear skills"
        ]

    if user_edits.project_clarifications:
        warnings = [
            warning
            for warning in warnings
            if warning != "resume profile has no project evidence"
        ]
        if not _has_project_evidence(profile):
            warnings.append(
                "project evidence comes from user clarification and should be "
                "verified before resume rewrite"
            )

    if user_edits.work_experience_clarifications:
        warnings = [
            warning
            for warning in warnings
            if warning != "resume profile has no work experience evidence"
        ]
        if not profile.work_experiences:
            warnings.append(
                "work-like evidence comes from user clarification and should be verified"
            )

    if user_edits.project_clarifications or user_edits.work_experience_clarifications:
        warnings = [
            warning
            for warning in warnings
            if warning != "resume profile has no highlights or measurable outcomes"
        ]

    return warnings


def _build_confirmed_confidence_label(
    profile: ResumeProfile,
    user_edits: ResumeProfileUserEdits,
    remaining_warnings: list[str],
) -> str:
    has_target_roles = bool(user_edits.target_roles)
    has_skills = bool(profile.skills or user_edits.additional_skills)
    has_project_or_work_evidence = (
        _has_project_evidence(profile)
        or bool(profile.work_experiences)
        or bool(user_edits.project_clarifications)
        or bool(user_edits.work_experience_clarifications)
    )
    has_any_user_edits = bool(
        user_edits.target_roles
        or user_edits.preferred_locations
        or user_edits.additional_skills
        or user_edits.project_clarifications
        or user_edits.work_experience_clarifications
        or user_edits.constraints
        or user_edits.notes
    )

    if (
        has_target_roles
        and has_skills
        and has_project_or_work_evidence
        and len(remaining_warnings) <= 1
    ):
        return "strong"
    if (
        has_target_roles
        and has_skills
        and has_project_or_work_evidence
        and len(remaining_warnings) <= 3
    ):
        return "medium"
    if has_any_user_edits:
        return "limited"
    if profile.skills or _has_project_evidence(profile) or profile.work_experiences:
        return "medium"
    return "weak"


def _build_missing_info_questions(
    profile: ResumeProfile,
    quality_warnings: list[str],
) -> list[str]:
    questions: list[str] = []

    if "target role is not explicit" in quality_warnings:
        questions.append(TARGET_ROLE_QUESTION)
    if "resume profile has no project evidence" in quality_warnings:
        questions.append(PROJECT_EVIDENCE_QUESTION)
    if "project evidence may be too thin for matching" in quality_warnings:
        questions.append(THIN_PROJECT_QUESTION)
    if not profile.work_experiences:
        questions.append(WORK_EXPERIENCE_QUESTION)
    if not profile.highlights:
        questions.append(OUTCOMES_QUESTION)

    return questions


def _build_confidence_label(profile: ResumeProfile, quality_warnings: list[str]) -> str:
    has_skills = bool(profile.skills)
    has_project_or_work = _has_project_evidence(profile) or bool(profile.work_experiences)
    evidence_is_sparse = not _has_project_evidence(profile) and not profile.work_experiences

    if not has_skills and evidence_is_sparse:
        return "weak"
    if has_skills and has_project_or_work and len(quality_warnings) <= 1:
        return "strong"
    if has_skills and has_project_or_work and len(quality_warnings) <= 2:
        return "medium"
    if has_skills and evidence_is_sparse:
        return "limited"
    if len(quality_warnings) >= 4:
        return "limited"
    return "medium"


def _is_project_too_thin(project: ProjectExperience) -> bool:
    text = " ".join(
        item
        for item in [project.description, project.raw_text, *project.highlights]
        if item
    )
    return len(text.split()) < 12 and len(text) < 80


def _has_project_evidence(profile: ResumeProfile) -> bool:
    if not profile.projects:
        return False

    if _looks_like_fallback_project(profile):
        return _fallback_project_has_clear_project_signal(profile.projects[0])

    return True


def _looks_like_fallback_project(profile: ResumeProfile) -> bool:
    if len(profile.projects) != 1:
        return False

    project = profile.projects[0]
    raw_prefix = profile.raw_text.strip()[:240]
    project_raw_text = project.raw_text.strip()
    return project_raw_text == raw_prefix


def _fallback_project_has_clear_project_signal(project: ProjectExperience) -> bool:
    project_text = " ".join(
        item
        for item in [project.name, project.description, project.raw_text, *project.highlights]
        if item
    ).lower()
    project_keywords = [
        "project",
        "system",
        "platform",
        "application",
        "agent",
        "demo",
        "implemented",
        "built",
        "developed",
        "designed",
    ]
    return any(keyword in project_text for keyword in project_keywords)


def _normalize_list(items: list[str] | None) -> list[str]:
    return [item.strip() for item in items or [] if item.strip()]


def _dedupe_list(items: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = str(item).strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(text)
    return result


def _normalize_user_edits(user_edits: ResumeProfileUserEdits) -> ResumeProfileUserEdits:
    return ResumeProfileUserEdits(
        target_roles=_normalize_list(user_edits.target_roles),
        preferred_locations=_normalize_list(user_edits.preferred_locations),
        additional_skills=_normalize_list(user_edits.additional_skills),
        project_clarifications=_normalize_list(user_edits.project_clarifications),
        work_experience_clarifications=_normalize_list(
            user_edits.work_experience_clarifications
        ),
        constraints=_normalize_list(user_edits.constraints),
        notes=(
            user_edits.notes.strip()
            if user_edits.notes and user_edits.notes.strip()
            else None
        ),
    )


def _merge_skills(existing_skills: list[str], additional_skills: list[str]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for skill in [*existing_skills, *additional_skills]:
        normalized_skill = skill.strip()
        if not normalized_skill:
            continue
        key = normalized_skill.lower()
        if key in seen:
            continue
        seen.add(key)
        merged.append(normalized_skill)
    return merged
