from __future__ import annotations

from app.agents.resume_parse_agent import parse_resume
from app.schemas.profile_review import ResumeProfileReviewResult
from app.schemas.resume import ProjectExperience, ResumeProfile
from app.services.errors import JobAgentError

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
) -> ResumeProfileReviewResult:
    normalized_resume = resume_text.strip()
    if not normalized_resume:
        raise JobAgentError(
            "resume_text is required",
            error_code="resume_text_required",
        )

    parsed_profile = parse_resume(normalized_resume)
    normalized_target_roles = _normalize_list(target_roles)
    quality_warnings = _build_quality_warnings(parsed_profile, normalized_target_roles)
    missing_info_questions = _build_missing_info_questions(parsed_profile, quality_warnings)
    confidence_label = _build_confidence_label(parsed_profile, quality_warnings)

    return ResumeProfileReviewResult(
        parsed_profile=parsed_profile,
        quality_warnings=quality_warnings,
        missing_info_questions=missing_info_questions,
        suggested_edits=SUGGESTED_EDITS.copy(),
        editable_sections=EDITABLE_SECTIONS.copy(),
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
