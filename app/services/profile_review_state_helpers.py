"""维护旧版画像审阅流程的 session state 字段和草稿/确认结果转换。"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.schemas.profile_draft import ProfileDraft
from app.schemas.profile_review import ResumeProfileUserEdits

PROFILE_FLOW_STEP_KEY = "profile_flow_step"
PROFILE_FLOW_PROVIDER_KEY = "profile_flow_selected_provider"
PROFILE_FLOW_PROVIDER_META_KEY = "profile_flow_selected_provider_metadata"
PROFILE_FLOW_STEPS = {
    "resume_input",
    "parsed_review",
    "profile_draft",
    "profile_saved",
}

LIST_FIELD_ALIASES = {
    "skill": "skills",
    "skills": "skills",
    "technical_stack": "technologies",
    "technology": "technologies",
    "technologies": "technologies",
    "highlight": "highlights",
    "highlights": "highlights",
    "certificate": "certificates",
    "certificates": "certificates",
}


def build_profile_draft_from_baseline(
    baseline_review: dict[str, Any],
    *,
    target_roles: list[str] | None = None,
) -> dict[str, Any]:
    parsed_profile = dict(baseline_review.get("parsed_profile") or {})
    return {
        "name": parsed_profile.get("name") or "",
        "skills": dedupe_skills(_as_list(parsed_profile.get("skills"))),
        "projects": deepcopy(_as_list(parsed_profile.get("projects"))),
        "work_experiences": deepcopy(_as_list(parsed_profile.get("work_experiences"))),
        "education": deepcopy(_as_list(parsed_profile.get("education"))),
        "certificates": _as_list(parsed_profile.get("certificates")),
        "highlights": _as_list(parsed_profile.get("highlights")),
        "target_roles": dedupe_strings(target_roles or []),
        "preferred_locations": [],
        "constraints": [],
        "notes": "",
    }


def set_profile_draft_state(
    session_state: dict[str, Any],
    draft: ProfileDraft,
) -> None:
    session_state["profile_flow_profile_draft"] = draft
    session_state["profile_draft"] = draft
    session_state["profile_draft_confirmed_payload"] = None


def set_confirmed_profile_draft_payload(
    session_state: dict[str, Any],
    payload: dict[str, Any],
) -> None:
    session_state["profile_draft_confirmed_payload"] = payload


def get_profile_flow_step(session_state: dict[str, Any]) -> str:
    step = str(session_state.get(PROFILE_FLOW_STEP_KEY) or "resume_input")
    if step not in PROFILE_FLOW_STEPS:
        return "resume_input"
    return step


def set_profile_flow_step(session_state: dict[str, Any], step: str) -> None:
    session_state[PROFILE_FLOW_STEP_KEY] = (
        step if step in PROFILE_FLOW_STEPS else "resume_input"
    )


def get_selected_provider(session_state: dict[str, Any]) -> str:
    return str(session_state.get(PROFILE_FLOW_PROVIDER_KEY) or "ollama")


def set_selected_provider(
    session_state: dict[str, Any],
    provider: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    session_state[PROFILE_FLOW_PROVIDER_KEY] = provider or "ollama"
    session_state[PROFILE_FLOW_PROVIDER_META_KEY] = metadata or {}


def dedupe_skills(skills: list[str]) -> list[str]:
    return dedupe_strings(skills, case_insensitive=True)


def dedupe_strings(
    items: list[str],
    *,
    case_insensitive: bool = True,
) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        normalized = str(item).strip()
        if not normalized:
            continue
        key = normalized.lower() if case_insensitive else normalized
        if key in seen:
            continue
        seen.add(key)
        result.append(normalized)
    return result


def apply_suggestion_to_profile_draft(
    profile_draft: dict[str, Any],
    suggestion: dict[str, Any],
    edited_value: str | list[str] | None = None,
) -> dict[str, Any]:
    draft = deepcopy(profile_draft)
    section = str(suggestion.get("section") or "").strip().lower()
    field = str(suggestion.get("field") or "").strip()
    value = edited_value if edited_value is not None else suggestion.get("suggested_value")
    if not section or not field or value in (None, "", []):
        return draft

    if section in {"skill", "skills"}:
        _append_values(draft, "skills", value, dedupe_as_skills=True)
        return draft

    if section == "project":
        _apply_item_suggestion(draft, "projects", suggestion, field, value)
        return draft

    if section in {"work", "work_experience", "work_experiences", "experience"}:
        _apply_item_suggestion(draft, "work_experiences", suggestion, field, value)
        return draft

    if section == "education":
        _apply_item_suggestion(draft, "education", suggestion, field, value)
        return draft

    if section in {"certificate", "certificates", "highlight", "highlights"}:
        target_field = LIST_FIELD_ALIASES.get(section, section)
        _append_values(draft, target_field, value)
        return draft

    warnings = _as_list(draft.get("_warnings"))
    warnings.append(f"ignored unknown suggestion section: {section}")
    draft["_warnings"] = warnings
    return draft


def build_confirm_user_edits_from_profile_draft(
    profile_draft: dict[str, Any],
) -> ResumeProfileUserEdits:
    project_clarifications = [
        _project_to_clarification(project)
        for project in _as_list(profile_draft.get("projects"))
    ]
    work_clarifications = [
        _work_to_clarification(work)
        for work in _as_list(profile_draft.get("work_experiences"))
    ]
    return ResumeProfileUserEdits(
        target_roles=dedupe_strings(_as_list(profile_draft.get("target_roles"))),
        preferred_locations=dedupe_strings(
            _as_list(profile_draft.get("preferred_locations"))
        ),
        additional_skills=dedupe_skills(_as_list(profile_draft.get("skills"))),
        project_clarifications=[
            item for item in project_clarifications if item.strip()
        ],
        work_experience_clarifications=[
            item for item in work_clarifications if item.strip()
        ],
        constraints=dedupe_strings(_as_list(profile_draft.get("constraints"))),
        notes=str(profile_draft.get("notes") or "").strip() or None,
    )


def append_missing_info_answer(
    profile_draft: dict[str, Any],
    *,
    question: str,
    answer: str,
) -> dict[str, Any]:
    draft = deepcopy(profile_draft)
    normalized_answer = answer.strip()
    if not normalized_answer:
        return draft
    notes = str(draft.get("notes") or "").strip()
    entry = f"{question.strip()}: {normalized_answer}"
    draft["notes"] = f"{notes}\n{entry}".strip() if notes else entry
    return draft


def build_confirmed_profile_save_payload(
    *,
    resume_text: str,
    baseline_review: dict[str, Any] | None,
    confirmed_profile_result: dict[str, Any] | None,
    accepted_suggestions: dict[str, dict[str, Any]] | list[dict[str, Any]],
    edited_suggestions: dict[str, dict[str, Any]] | list[dict[str, Any]],
    rejected_suggestions: dict[str, dict[str, Any]] | list[dict[str, Any]],
    missing_info_answers: dict[str, str] | list[dict[str, Any]],
    notes: str | None = None,
) -> dict[str, Any] | None:
    if not baseline_review or not confirmed_profile_result:
        return None
    baseline_profile = baseline_review.get("parsed_profile")
    if not baseline_profile:
        return None

    return {
        "raw_resume_text": resume_text,
        "baseline_profile": baseline_profile,
        "confirmed_result": confirmed_profile_result,
        "suggestion_decisions": build_suggestion_decisions_payload(
            accepted_suggestions=accepted_suggestions,
            edited_suggestions=edited_suggestions,
            rejected_suggestions=rejected_suggestions,
        ),
        "missing_info_answers": build_missing_info_answers_payload(
            missing_info_answers
        ),
        "notes": notes,
    }


def build_suggestion_decisions_payload(
    *,
    accepted_suggestions: dict[str, dict[str, Any]] | list[dict[str, Any]],
    edited_suggestions: dict[str, dict[str, Any]] | list[dict[str, Any]],
    rejected_suggestions: dict[str, dict[str, Any]] | list[dict[str, Any]],
) -> list[dict[str, Any]]:
    decisions: list[dict[str, Any]] = []
    decisions.extend(
        _suggestions_with_status(accepted_suggestions, decision_status="accepted")
    )
    decisions.extend(_suggestions_with_status(edited_suggestions, decision_status="edited"))
    decisions.extend(
        _suggestions_with_status(rejected_suggestions, decision_status="rejected")
    )
    return decisions


def build_missing_info_answers_payload(
    missing_info_answers: dict[str, str] | list[dict[str, Any]],
) -> list[dict[str, str]]:
    if isinstance(missing_info_answers, dict):
        raw_answers = [
            {"question": question, "answer": answer}
            for question, answer in missing_info_answers.items()
        ]
    else:
        raw_answers = missing_info_answers

    answers: list[dict[str, str]] = []
    for item in raw_answers:
        question = str(item.get("question") or "").strip()
        answer = str(item.get("answer") or "").strip()
        if not question or not answer:
            continue
        answers.append({"question": question, "answer": answer})
    return answers


def _apply_item_suggestion(
    draft: dict[str, Any],
    collection_name: str,
    suggestion: dict[str, Any],
    field: str,
    value: str | list[str],
) -> None:
    items = _as_list(draft.get(collection_name))
    index = suggestion.get("item_index")
    if not isinstance(index, int) or index < 0 or index >= len(items):
        warnings = _as_list(draft.get("_warnings"))
        warnings.append(f"ignored suggestion with invalid {collection_name} index")
        draft["_warnings"] = warnings
        return

    item = dict(items[index])
    target_field = LIST_FIELD_ALIASES.get(field.lower(), field)
    if target_field in {"skills", "technologies", "highlights", "certificates"}:
        _append_values(item, target_field, value)
    else:
        item[target_field] = _stringify_value(value)
    items[index] = item
    draft[collection_name] = items


def _append_values(
    target: dict[str, Any],
    field: str,
    value: str | list[str],
    *,
    dedupe_as_skills: bool = False,
) -> None:
    existing = _as_list(target.get(field))
    additions = _value_to_list(value)
    merged = [*existing, *additions]
    target[field] = dedupe_skills(merged) if dedupe_as_skills else dedupe_strings(merged)


def _project_to_clarification(project: dict[str, Any]) -> str:
    parts = [
        str(project.get("name") or "").strip(),
        str(project.get("description") or "").strip(),
        ", ".join(_as_list(project.get("technologies"))),
        "; ".join(_as_list(project.get("highlights"))),
    ]
    return " | ".join(part for part in parts if part)


def _work_to_clarification(work: dict[str, Any]) -> str:
    parts = [
        str(work.get("company") or "").strip(),
        str(work.get("role") or "").strip(),
        str(work.get("description") or "").strip(),
        ", ".join(_as_list(work.get("technologies"))),
    ]
    return " | ".join(part for part in parts if part)


def _value_to_list(value: str | list[str]) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    normalized = str(value).replace(";", ",").replace("/", ",")
    return [item.strip() for item in normalized.split(",") if item.strip()]


def _stringify_value(value: str | list[str]) -> str:
    if isinstance(value, list):
        return ", ".join(str(item).strip() for item in value if str(item).strip())
    return str(value).strip()


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _suggestions_with_status(
    suggestions: dict[str, dict[str, Any]] | list[dict[str, Any]],
    *,
    decision_status: str,
) -> list[dict[str, Any]]:
    normalized = suggestions.values() if isinstance(suggestions, dict) else suggestions
    decisions: list[dict[str, Any]] = []
    for suggestion in normalized:
        decision = {
            "section": str(suggestion.get("section") or ""),
            "item_index": suggestion.get("item_index"),
            "field": str(suggestion.get("field") or ""),
            "suggested_value": suggestion.get("suggested_value"),
            "source_quote": suggestion.get("source_quote"),
            "decision_status": decision_status,
            "confidence_label": suggestion.get("confidence_label"),
            "warnings": _as_list(suggestion.get("warnings")),
        }
        if decision_status == "edited" and suggestion.get("edited_value") is not None:
            decision["edited_value"] = suggestion.get("edited_value")
        decisions.append(decision)
    return decisions
