from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.schemas.profile_draft import ProfileDraft
from app.schemas.resume import ResumeProfile
from app.services.llm_provider import DEFAULT_LLM_PROVIDER, resolve_llm_provider
from app.services.search_ready_profile_builder import build_search_ready_profile

EDITABLE_LIST_FIELDS = {
    "target_directions",
    "core_skills",
    "auxiliary_skills",
    "search_keywords",
    "preferred_locations",
    "work_arrangements",
    "company_preferences",
    "profile_notes",
}


def create_profile_draft(
    parsed_profile: ResumeProfile,
    target_roles: list[str] | None = None,
    *,
    quality_warnings: list[str] | None = None,
    missing_info_questions: list[str] | None = None,
    llm_provider: str | None = None,
) -> ProfileDraft:
    now = datetime.now(timezone.utc)
    provider_resolution = resolve_llm_provider(llm_provider or DEFAULT_LLM_PROVIDER)
    search_ready_profile = build_search_ready_profile(
        parsed_profile,
        target_roles,
        quality_warnings=quality_warnings,
        missing_info_questions=missing_info_questions,
        source_profile_snapshot=parsed_profile.model_dump(mode="json"),
    )
    return ProfileDraft(
        draft_id=str(uuid4()),
        status="draft",
        search_ready_profile=search_ready_profile,
        llm_provider=provider_resolution.provider,
        llm_model=provider_resolution.model,
        llm_base_url=provider_resolution.base_url,
        llm_configured=provider_resolution.configured,
        llm_provider_reason=provider_resolution.reason,
        user_answers={},
        user_edit_snapshot={},
        source_profile_snapshot=parsed_profile.model_dump(mode="json"),
        created_at=now,
        updated_at=now,
    )


def update_profile_draft(draft: ProfileDraft, updates: dict[str, Any]) -> ProfileDraft:
    profile_updates: dict[str, Any] = {}
    edit_snapshot = dict(draft.user_edit_snapshot)

    for field, value in updates.items():
        if field == "summary":
            normalized = str(value or "").strip()
            profile_updates[field] = normalized
            edit_snapshot[field] = normalized
            continue
        if field in EDITABLE_LIST_FIELDS:
            normalized_list = _dedupe_list(value)
            profile_updates[field] = normalized_list
            edit_snapshot[field] = normalized_list

    if not profile_updates:
        return draft

    updated_profile = draft.search_ready_profile.model_copy(update=profile_updates)
    return draft.model_copy(
        update={
            "search_ready_profile": updated_profile,
            "user_edit_snapshot": edit_snapshot,
            "updated_at": datetime.now(timezone.utc),
        }
    )


def answer_missing_info_question(
    draft: ProfileDraft,
    question: str,
    answer: str,
) -> ProfileDraft:
    normalized_question = str(question or "").strip()
    normalized_answer = str(answer or "").strip()
    if not normalized_question or not normalized_answer:
        return draft

    user_answers = dict(draft.user_answers)
    user_answers[normalized_question] = normalized_answer
    notes = list(draft.search_ready_profile.profile_notes)
    note_entry = f"Missing info answer - {normalized_question}: {normalized_answer}"
    if note_entry not in notes:
        notes.append(note_entry)

    return draft.model_copy(
        update={
            "user_answers": user_answers,
            "search_ready_profile": draft.search_ready_profile.model_copy(
                update={"profile_notes": _dedupe_list(notes)}
            ),
            "updated_at": datetime.now(timezone.utc),
        }
    )


def confirm_profile_draft(draft: ProfileDraft) -> dict[str, Any]:
    confirmed_at = datetime.now(timezone.utc)
    confirmed_profile = draft.search_ready_profile.model_dump(mode="json")
    return {
        "draft_id": draft.draft_id,
        "status": "confirmed",
        "confirmed_search_ready_profile": confirmed_profile,
        "source_profile_snapshot": draft.source_profile_snapshot,
        "user_edit_snapshot": draft.user_edit_snapshot,
        "missing_info_answers": dict(draft.user_answers),
        "llm_provider_metadata": {
            "provider": draft.llm_provider,
            "model": draft.llm_model,
            "base_url": draft.llm_base_url,
            "configured": draft.llm_configured,
            "reason": draft.llm_provider_reason,
        },
        "confirmed_at": confirmed_at.isoformat(),
        "save_payload_ready": True,
    }


def _dedupe_list(value: Any) -> list[str]:
    if isinstance(value, list):
        raw_items = value
    else:
        raw_items = [part for part in str(value or "").replace("\n", ",").split(",")]

    result: list[str] = []
    seen: set[str] = set()
    for item in raw_items:
        normalized = str(item).strip()
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(normalized)
    return result
