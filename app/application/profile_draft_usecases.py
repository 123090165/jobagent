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

HEALTH_TARGET_ROLES = [
    "AI Health Algorithm Intern",
    "Physiological Signal Processing Intern",
    "Biomedical AI Intern",
]
HEALTH_FOCUS_TERMS = [
    "health",
    "physiological",
    "biosignal",
    "biomedical",
    "signal processing",
    "ppg",
    "ecg",
    "wearable",
    "blood oxygen",
    "heart rate",
]
HEALTH_SKILL_PRIORITY_TERMS = [
    "ppg",
    "ecg",
    "acc",
    "physiological signal",
    "biosignal",
    "wearable",
    "blood oxygen",
    "heart rate",
    "blood pressure",
    "time-series",
    "feature extraction",
    "signal segmentation",
    "denoising",
    "data cleaning",
    "pytorch",
    "tensorflow",
    "deep learning",
    "machine learning",
]


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
    raw_text = _raw_resume_text(parsed_review)
    explicit_roles = _extract_target_roles_from_raw_text(raw_text)
    role_matching_keywords = _extract_role_matching_keywords(raw_text)
    raw_skill_terms = _extract_skill_terms_from_raw_text(raw_text)
    target_signals = _clean_list(
        parsed_review.target_signals
        + explicit_roles
        + role_matching_keywords
    )
    highlights = _clean_list(parsed_review.basic_info.get("highlights", []))
    roles = _derive_target_roles(
        skill_items,
        target_signals,
        parsed_review.work_experience,
        explicit_roles=explicit_roles,
    )
    directions = _derive_target_directions(target_signals, roles)
    prioritized_skills = _prioritize_core_skills(
        _clean_list(skill_items + raw_skill_terms),
        target_signals,
    )
    core_skills = prioritized_skills[:8]
    supporting_skills = prioritized_skills[8:16]
    search_keywords = _clean_list(roles + role_matching_keywords + prioritized_skills + target_signals)[:20]
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
        "preferred_locations": _extract_locations_from_raw_text(raw_text),
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
    *,
    explicit_roles: list[str] | None = None,
) -> list[str]:
    roles: list[str] = _clean_list(explicit_roles or [])
    lowered_skills = " ".join(skill_items).lower()
    lowered_signals = " ".join(target_signals).lower()
    combined = f"{lowered_signals} {lowered_skills}"

    for signal in target_signals:
        if _looks_like_explicit_role(signal):
            roles.append(signal)
    if roles and any(token in " ".join(roles).lower() for token in ["ai agent", "llm", "ai application"]):
        roles.append("AI Application Engineer")
    if not roles and _has_health_focus(combined):
        roles.extend(HEALTH_TARGET_ROLES)
    if not roles and ("backend engineering signal" in lowered_signals or any(
        token in lowered_signals for token in ["backend engineer", "backend intern", "后端"]
    )):
        roles.append("Backend Engineer")
    if not roles and ("ai application signal" in lowered_signals or any(
        token in lowered_signals for token in ["ai agent", "agent engineer", "llm"]
    )):
        roles.append("AI Application Engineer")
    if not roles and ("embedded systems signal" in lowered_signals or any(
        token in lowered_signals for token in ["embedded engineer", "embedded intern", "嵌入式"]
    )):
        roles.append("Embedded Software Engineer")

    for item in work_experience:
        role = item.get("role")
        if not roles and isinstance(role, str) and role.strip():
            roles.append(role.strip())
            break

    return _clean_list(roles)[:5]


def _derive_target_directions(target_signals: list[str], roles: list[str] | None = None) -> list[str]:
    directions: list[str] = []
    lowered = " ".join(_clean_list((roles or []) + target_signals)).lower()
    if _has_health_focus(lowered):
        directions.append("AI health algorithms and physiological signal processing")
    if any(token in lowered for token in ["brand", "marketing", "campaign", "consumer", "content", "social media"]):
        directions.append("Brand marketing, content operations, and consumer insights")
    if any(token in lowered for token in ["museum", "cultural", "heritage", "exhibition", "public history"]):
        directions.append("Museum education, cultural research, and public history")
    if any(token in lowered for token in ["supply chain", "procurement", "logistics", "sourcing", "inventory", "trade"]):
        directions.append("Supply chain operations, procurement, and logistics")
    if any(token in lowered for token in ["finance", "financial", "investment", "risk", "banking", "quant"]):
        directions.append("Finance, risk, and investment analysis")
    if any(token in lowered for token in ["policy", "social research", "community", "governance"]):
        directions.append("Policy research and social research")
    if "backend" in lowered:
        directions.append("Backend platform and API delivery")
    explicit_ai_signal = any(
        token in lowered
        for token in ["ai agent", "llm", "artificial intelligence", "ai engineer", "ai application engineer"]
    )
    if ("ai application" in lowered or "ai agent" in lowered) and (not directions or explicit_ai_signal):
        directions.append("Applied AI tooling and workflow automation")
    if "embedded" in lowered:
        directions.append("Embedded systems and edge device software")
    if not directions:
        directions.append("Role-specific search based on confirmed profile evidence")
    return directions


def _prioritize_core_skills(skill_items: list[str], target_signals: list[str]) -> list[str]:
    if not _has_health_focus(" ".join([*skill_items, *target_signals]).lower()):
        return skill_items

    prioritized: list[str] = []
    for term in HEALTH_SKILL_PRIORITY_TERMS:
        for skill in skill_items:
            if term in skill.lower():
                prioritized.append(skill)
    prioritized.extend(skill_items)
    return _clean_list(prioritized)


def _has_health_focus(text: str) -> bool:
    lowered = text.lower()
    return any(term in lowered for term in HEALTH_FOCUS_TERMS)


def _looks_like_explicit_role(signal: str) -> bool:
    lowered = signal.strip().lower()
    if not lowered or lowered.endswith(" signal"):
        return False
    english_role_terms = {
        "engineer",
        "intern",
        "analyst",
        "assistant",
        "developer",
        "scientist",
        "researcher",
        "manager",
        "coordinator",
        "specialist",
    }
    normalized = lowered
    for separator in ["/", "-", "_", ",", ";", "|", "(", ")"]:
        normalized = normalized.replace(separator, " ")
    tokens = set(normalized.split())
    chinese_role_terms = ["岗位", "实习", "工程师", "分析师"]
    return bool(tokens & english_role_terms) or any(term in lowered for term in chinese_role_terms)
    role_terms = [
        "engineer",
        "intern",
        "analyst",
        "assistant",
        "developer",
        "scientist",
        "researcher",
        "岗位",
        "实习",
        "工程师",
        "分析师",
    ]
    return any(term in lowered for term in role_terms)


def _derive_strengths(parsed_review: ParsedResumeReview) -> list[str]:
    strengths: list[str] = []
    if parsed_review.work_experience:
        strengths.append("Resume includes work experience history to anchor role matching.")
    if parsed_review.projects:
        strengths.append("Project evidence is available for interview and keyword tailoring.")
    if parsed_review.skills.get("count", 0):
        strengths.append("Skill inventory is explicit enough to seed search keywords.")
    return strengths


def _raw_resume_text(parsed_review: ParsedResumeReview) -> str:
    raw_output = parsed_review.raw_parser_output
    if isinstance(raw_output, dict):
        raw_text = raw_output.get("raw_text")
        if isinstance(raw_text, str):
            return raw_text
    return ""


def _extract_target_roles_from_raw_text(raw_text: str) -> list[str]:
    for line in raw_text.splitlines():
        label, value = _split_label_line(line)
        if label in {"target role", "target roles", "desired role", "desired roles"}:
            return _split_role_values(value)
    return []


def _extract_locations_from_raw_text(raw_text: str) -> list[str]:
    for line in raw_text.splitlines():
        label, value = _split_label_line(line)
        if label in {"location", "preferred location", "preferred locations"}:
            return _clean_list([value])
    return []


def _extract_role_matching_keywords(raw_text: str) -> list[str]:
    return _extract_simple_section_items(raw_text, "role matching keywords", max_items=24)


def _extract_skill_terms_from_raw_text(raw_text: str) -> list[str]:
    terms: list[str] = []
    for section_name in ["core skills", "skills"]:
        terms.extend(_extract_simple_section_items(raw_text, section_name, max_items=32))
    return _clean_list(terms)


def _extract_simple_section_items(raw_text: str, section_name: str, *, max_items: int) -> list[str]:
    lines = raw_text.splitlines()
    in_section = False
    items: list[str] = []
    target = section_name.lower()
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if in_section and items:
                break
            continue
        if set(stripped) <= {"="}:
            continue
        lowered = stripped.lower().rstrip(":")
        if not in_section and lowered == target:
            in_section = True
            continue
        if in_section and stripped.isupper() and " " in stripped and items:
            break
        if in_section:
            item = stripped.lstrip("-•* ").strip()
            if ":" in item and len(item.split(":", 1)[0]) < 40:
                continue
            items.append(item)
            if len(items) >= max_items:
                break
    return _clean_list(items)


def _split_label_line(line: str) -> tuple[str, str]:
    if ":" not in line:
        return "", ""
    label, value = line.split(":", 1)
    return label.strip().lower(), value.strip()


def _split_role_values(value: str) -> list[str]:
    separators = [" / ", "/", ";", "|", ","]
    values = [value]
    for separator in separators:
        split_values: list[str] = []
        for item in values:
            split_values.extend(item.split(separator))
        values = split_values
    return _clean_list(values)


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
