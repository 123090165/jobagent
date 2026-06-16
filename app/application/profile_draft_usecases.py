from __future__ import annotations

from app.application.profile_session_usecases import get_profile_session
from app.application.resume_review_usecases import get_parsed_resume_review
from app.repositories.parsed_resume_review_repository import (
    ParsedResumeReviewRepository,
    parsed_resume_review_repository,
)
from app.repositories.profile_draft_repository import (
    ProfileDraftRepository,
    profile_draft_repository,
)
from app.repositories.profile_session_repository import (
    ProfileSessionRepository,
    profile_session_repository,
)
from app.schemas.parsed_resume_review import ParsedResumeReview
from app.schemas.profile_draft import (
    ProfileDraft,
    ProfileDraftResponse,
    UpdateProfileDraftRequest,
)
from app.services.errors import JobAgentError


def create_profile_draft(
    session_id: str,
    *,
    regenerate: bool = False,
    session_repository: ProfileSessionRepository = profile_session_repository,
    parsed_review_repository: ParsedResumeReviewRepository = parsed_resume_review_repository,
    draft_repository: ProfileDraftRepository = profile_draft_repository,
) -> ProfileDraftResponse:
    session = get_profile_session(session_id, repository=session_repository)
    if session.parsed_review_id is None:
        raise JobAgentError(
            message="Profile draft requires an existing parsed resume review.",
            error_code="invalid_profile_session_state",
            status_code=409,
        )

    parsed_review_response = get_parsed_resume_review(
        session_id,
        session_repository=session_repository,
        parsed_review_repository=parsed_review_repository,
    )
    parsed_review = parsed_review_response.parsed_review

    if not regenerate:
        if session.profile_draft_id:
            existing = draft_repository.get(session.profile_draft_id)
            if existing is not None and existing.parsed_review_id == parsed_review.parsed_review_id:
                return ProfileDraftResponse(
                    profile_draft=existing,
                    profile_session=session,
                )
        existing_for_review = draft_repository.get_current_for_session(
            session_id=session.session_id,
            parsed_review_id=parsed_review.parsed_review_id,
        )
        if existing_for_review is not None:
            updated_session = session_repository.attach_profile_draft(
                session_id=session.session_id,
                profile_draft_id=existing_for_review.profile_draft_id,
            )
            return ProfileDraftResponse(
                profile_draft=existing_for_review,
                profile_session=updated_session or session,
            )

    draft_seed = _build_profile_draft_seed(parsed_review)
    profile_draft = draft_repository.create(
        session_id=session.session_id,
        parsed_review_id=parsed_review.parsed_review_id,
        summary=draft_seed["summary"],
        target_roles=draft_seed["target_roles"],
        target_directions=draft_seed["target_directions"],
        core_skills=draft_seed["core_skills"],
        supporting_skills=draft_seed["supporting_skills"],
        search_keywords=draft_seed["search_keywords"],
        preferred_locations=draft_seed["preferred_locations"],
        work_arrangements=draft_seed["work_arrangements"],
        strengths=draft_seed["strengths"],
        risks=draft_seed["risks"],
        missing_info_questions=draft_seed["missing_info_questions"],
    )
    updated_session = session_repository.attach_profile_draft(
        session_id=session.session_id,
        profile_draft_id=profile_draft.profile_draft_id,
    )
    return ProfileDraftResponse(
        profile_draft=profile_draft,
        profile_session=updated_session or session,
    )


def get_profile_draft(
    draft_id: str,
    *,
    session_repository: ProfileSessionRepository = profile_session_repository,
    draft_repository: ProfileDraftRepository = profile_draft_repository,
) -> ProfileDraftResponse:
    profile_draft = draft_repository.get(draft_id)
    if profile_draft is None:
        raise JobAgentError(
            message="Profile draft not found.",
            error_code="profile_draft_not_found",
            status_code=404,
        )
    session = get_profile_session(profile_draft.session_id, repository=session_repository)
    return ProfileDraftResponse(profile_draft=profile_draft, profile_session=session)


def update_profile_draft(
    draft_id: str,
    payload: UpdateProfileDraftRequest,
    *,
    session_repository: ProfileSessionRepository = profile_session_repository,
    draft_repository: ProfileDraftRepository = profile_draft_repository,
) -> ProfileDraftResponse:
    profile_draft = draft_repository.update(draft_id, _normalize_update_payload(payload))
    if profile_draft is None:
        raise JobAgentError(
            message="Profile draft not found.",
            error_code="profile_draft_not_found",
            status_code=404,
        )
    updated_session = session_repository.attach_profile_draft(
        session_id=profile_draft.session_id,
        profile_draft_id=profile_draft.profile_draft_id,
    )
    return ProfileDraftResponse(
        profile_draft=profile_draft,
        profile_session=updated_session or get_profile_session(profile_draft.session_id),
    )


def _normalize_update_payload(payload: UpdateProfileDraftRequest) -> UpdateProfileDraftRequest:
    normalized: dict[str, object] = {}
    for field_name, value in payload.model_dump(exclude_unset=True).items():
        if isinstance(value, str):
            normalized[field_name] = value.strip()
        elif isinstance(value, list):
            normalized[field_name] = _clean_list(value)
        else:
            normalized[field_name] = value
    return UpdateProfileDraftRequest(**normalized)


def _build_profile_draft_seed(parsed_review: ParsedResumeReview) -> dict[str, object]:
    skill_items = _clean_list(parsed_review.skills.get("items", []))
    target_signals = _clean_list(parsed_review.target_signals)
    highlights = _clean_list(parsed_review.basic_info.get("highlights", []))
    roles = _derive_target_roles(skill_items, target_signals, parsed_review.work_experience)
    directions = _derive_target_directions(target_signals)
    core_skills = skill_items[:8]
    supporting_skills = skill_items[8:16]
    search_keywords = _clean_list(roles + core_skills + target_signals)[:16]
    strengths = _clean_list(highlights + _derive_strengths(parsed_review))
    risks = _clean_list(parsed_review.quality_warnings)
    missing_questions = _clean_list(parsed_review.missing_info_questions)

    return {
        "summary": _build_summary(parsed_review, roles, core_skills),
        "target_roles": roles,
        "target_directions": directions,
        "core_skills": core_skills,
        "supporting_skills": supporting_skills,
        "search_keywords": search_keywords,
        "preferred_locations": [],
        "work_arrangements": [],
        "strengths": strengths,
        "risks": risks,
        "missing_info_questions": missing_questions,
    }


def _build_summary(
    parsed_review: ParsedResumeReview,
    roles: list[str],
    core_skills: list[str],
) -> str:
    name = str(parsed_review.basic_info.get("name") or "This candidate")
    role_text = ", ".join(roles[:2]) if roles else "technical roles"
    skill_text = ", ".join(core_skills[:4]) if core_skills else "transferable technical skills"
    return f"{name} appears aligned with {role_text}, with strongest signals in {skill_text}."


def _derive_target_roles(
    skill_items: list[str],
    target_signals: list[str],
    work_experience: list[dict[str, object]],
) -> list[str]:
    roles: list[str] = []
    lowered_skills = " ".join(skill_items).lower()
    lowered_signals = " ".join(target_signals).lower()

    if "backend" in lowered_signals or any(
        token in lowered_skills for token in ["python", "fastapi", "sql", "api"]
    ):
        roles.append("Backend Engineer")
    if "ai" in lowered_signals or any(
        token in lowered_skills for token in ["llm", "langgraph", "langchain", "rag"]
    ):
        roles.append("AI Application Engineer")
    if "embedded" in lowered_signals or any(
        token in lowered_skills for token in ["stm32", "rtos", "embedded", "c++"]
    ):
        roles.append("Embedded Software Engineer")

    for item in work_experience:
        role = item.get("role")
        if isinstance(role, str) and role.strip():
            roles.append(role.strip())
            break

    return _clean_list(roles)[:5]


def _derive_target_directions(target_signals: list[str]) -> list[str]:
    directions: list[str] = []
    lowered = " ".join(target_signals).lower()
    if "backend" in lowered:
        directions.append("Backend platform and API delivery")
    if "ai" in lowered:
        directions.append("Applied AI tooling and workflow automation")
    if "embedded" in lowered:
        directions.append("Embedded systems and edge device software")
    if not directions:
        directions.append("General software engineering")
    return directions


def _derive_strengths(parsed_review: ParsedResumeReview) -> list[str]:
    strengths: list[str] = []
    if parsed_review.work_experience:
        strengths.append("Resume includes work experience history to anchor role matching.")
    if parsed_review.projects:
        strengths.append("Project evidence is available for interview and keyword tailoring.")
    if parsed_review.skills.get("count", 0):
        strengths.append("Skill inventory is explicit enough to seed search keywords.")
    return strengths


def _clean_list(values: list[object]) -> list[str]:
    seen: set[str] = set()
    cleaned: list[str] = []
    for value in values:
        if not isinstance(value, str):
            continue
        item = value.strip()
        if not item:
            continue
        lowered = item.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        cleaned.append(item)
    return cleaned
