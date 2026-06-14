from __future__ import annotations

import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import streamlit as st

from app.schemas.brief import JobBriefReport
from app.schemas.profile_draft import ProfileDraft
from app.schemas.resume import ResumeProfile
from app.services.errors import JobAgentError
from app.services.profile_draft_service import (
    answer_missing_info_question,
    confirm_profile_draft,
    create_profile_draft,
    update_profile_draft,
)
from frontend.profile_review_state import (
    dedupe_strings,
    set_confirmed_profile_draft_payload,
    set_profile_draft_state,
)

DEFAULT_API_BASE_URL = os.getenv("JOBAGENT_API_BASE_URL", "http://127.0.0.1:8000")
DEFAULT_API_TIMEOUT_SECONDS = 30
SCORING_QUALITY_LABELS = {
    "full_jd": "complete JD",
    "partial_jd": "partial JD",
    "external_link_only": "external detail",
    "snippet_only": "snippet only",
    "invalid": "invalid JD",
}
FLOW_KEYS = [
    "profile_flow_baseline_review",
    "profile_flow_profile_draft",
    "profile_draft_confirmed_payload",
]


def request_job_brief_from_api(
    *,
    resume_text: str,
    query: str,
    provider: str,
    limit: int,
    use_llm_jd: bool,
    profile_context: dict[str, object] | None = None,
    api_base_url: str = DEFAULT_API_BASE_URL,
    timeout_seconds: int = DEFAULT_API_TIMEOUT_SECONDS,
) -> JobBriefReport:
    payload = json.dumps(
        {
            "resume_text": resume_text,
            "query": query,
            "provider": provider,
            "limit": limit,
            "use_llm_jd": use_llm_jd,
            "profile_context": profile_context,
        }
    ).encode("utf-8")
    request = Request(
        f"{api_base_url.rstrip('/')}/brief/from-search",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            response_body = response.read().decode("utf-8")
    except HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        error_payload = _load_json_payload(error_body)
        raise JobAgentError(
            str(error_payload.get("detail", f"/brief/from-search failed with status {exc.code}")),
            str(error_payload.get("error_code", "brief_api_request_failed")),
        ) from exc
    except URLError as exc:
        raise JobAgentError(
            "Cannot connect to FastAPI backend. Start it with: "
            ".venv\\Scripts\\python.exe -m uvicorn app.main:app --reload",
            "brief_api_unavailable",
        ) from exc

    return JobBriefReport.model_validate(_load_json_payload(response_body))


def render_profile_review_flow_tab(*, sample_resume: str) -> None:
    st.subheader("Profile Review")
    st.caption(
        "确认后，这份画像将用于后续岗位搜索和匹配。"
    )
    _ensure_initial_state(sample_resume)

    st.markdown("### 01 Resume Input")
    resume_text = st.text_area(
        "resume_text",
        key="profile_flow_resume_text",
        height=220,
    )
    target_roles_text = st.text_input(
        "target_roles",
        key="profile_flow_initial_target_roles",
        placeholder="AI Agent Engineer, Backend Engineer",
    )
    target_roles = _split_comma_list(target_roles_text)
    if st.button("Parse Resume Profile", key="profile_flow_parse", use_container_width=True):
        _parse_resume_profile(resume_text=resume_text, target_roles=target_roles)

    baseline_review = st.session_state.get("profile_flow_baseline_review")
    profile_draft = st.session_state.get("profile_flow_profile_draft")

    if baseline_review and profile_draft:
        st.markdown("### 02 Search-Ready Profile Draft")
        _render_profile_draft_editor(baseline_review, profile_draft)
    else:
        st.info("Parse a resume to start profile review.")

    _render_raw_debug()
    _render_reset_button()


def request_resume_profile_review_from_api(
    *,
    resume_text: str,
    target_roles: list[str],
    api_base_url: str = DEFAULT_API_BASE_URL,
    timeout_seconds: int = DEFAULT_API_TIMEOUT_SECONDS,
) -> dict[str, object]:
    return _call_api(
        "/resume/profile-review",
        {
            "resume_text": resume_text,
            "target_roles": target_roles,
        },
        api_base_url=api_base_url,
        timeout_seconds=timeout_seconds,
        unavailable_error_code="profile_review_api_unavailable",
        failure_error_code="profile_review_api_request_failed",
    )


def request_resume_profile_enrichment_from_api(
    *,
    resume_text: str,
    target_roles: list[str],
    use_llm: bool,
    api_base_url: str = DEFAULT_API_BASE_URL,
    timeout_seconds: int = DEFAULT_API_TIMEOUT_SECONDS,
) -> dict[str, object]:
    return _call_api(
        "/resume/profile-enrichment",
        {
            "resume_text": resume_text,
            "target_roles": target_roles,
            "use_llm": use_llm,
        },
        api_base_url=api_base_url,
        timeout_seconds=timeout_seconds,
        unavailable_error_code="profile_enrichment_api_unavailable",
        failure_error_code="profile_enrichment_api_request_failed",
    )


def request_confirm_resume_profile_from_api(
    *,
    parsed_profile: dict[str, object],
    user_edits: dict[str, object],
    api_base_url: str = DEFAULT_API_BASE_URL,
    timeout_seconds: int = DEFAULT_API_TIMEOUT_SECONDS,
) -> dict[str, object]:
    return _call_api(
        "/resume/profile-review/confirm",
        {
            "parsed_profile": parsed_profile,
            "user_edits": user_edits,
        },
        api_base_url=api_base_url,
        timeout_seconds=timeout_seconds,
        unavailable_error_code="profile_confirm_api_unavailable",
        failure_error_code="profile_confirm_api_request_failed",
    )


def request_save_confirmed_profile_from_api(
    *,
    payload: dict[str, object],
    api_base_url: str = DEFAULT_API_BASE_URL,
    timeout_seconds: int = DEFAULT_API_TIMEOUT_SECONDS,
) -> dict[str, object]:
    return _call_api(
        "/profile/confirmed",
        payload,
        api_base_url=api_base_url,
        timeout_seconds=timeout_seconds,
        unavailable_error_code="confirmed_profile_api_unavailable",
        failure_error_code="confirmed_profile_api_request_failed",
    )


def request_saved_confirmed_profiles_from_api(
    *,
    limit: int = 10,
    api_base_url: str = DEFAULT_API_BASE_URL,
    timeout_seconds: int = DEFAULT_API_TIMEOUT_SECONDS,
) -> list[dict[str, object]]:
    payload = _get_api(
        f"/profile/confirmed?limit={int(limit)}",
        api_base_url=api_base_url,
        timeout_seconds=timeout_seconds,
        unavailable_error_code="confirmed_profile_api_unavailable",
        failure_error_code="confirmed_profile_api_request_failed",
    )
    if not isinstance(payload, list):
        raise JobAgentError(
            "Confirmed profile API returned an invalid list response",
            "confirmed_profile_api_invalid_json",
        )
    return payload


def request_saved_confirmed_profile_detail_from_api(
    *,
    record_id: int,
    api_base_url: str = DEFAULT_API_BASE_URL,
    timeout_seconds: int = DEFAULT_API_TIMEOUT_SECONDS,
) -> dict[str, object]:
    payload = _get_api(
        f"/profile/confirmed/{int(record_id)}",
        api_base_url=api_base_url,
        timeout_seconds=timeout_seconds,
        unavailable_error_code="confirmed_profile_api_unavailable",
        failure_error_code="confirmed_profile_api_request_failed",
    )
    if not isinstance(payload, dict):
        raise JobAgentError(
            "Confirmed profile API returned an invalid detail response",
            "confirmed_profile_api_invalid_json",
        )
    return payload


def request_profile_search_plan_from_api(
    *,
    query: str,
    profile_context: dict[str, object],
    api_base_url: str = DEFAULT_API_BASE_URL,
    timeout_seconds: int = DEFAULT_API_TIMEOUT_SECONDS,
) -> dict[str, object]:
    return _call_api(
        "/brief/search-plan",
        {
            "query": query,
            "profile_context": profile_context,
        },
        api_base_url=api_base_url,
        timeout_seconds=timeout_seconds,
        unavailable_error_code="profile_search_plan_api_unavailable",
        failure_error_code="profile_search_plan_api_request_failed",
    )


def _ensure_initial_state(sample_resume: str) -> None:
    st.session_state.setdefault("profile_flow_resume_text", sample_resume)
    st.session_state.setdefault(
        "profile_flow_initial_target_roles",
        "AI Agent Engineer, Backend Engineer",
    )
    st.session_state.setdefault("profile_flow_sync_token", 0)


def _parse_resume_profile(*, resume_text: str, target_roles: list[str]) -> None:
    try:
        baseline_review = request_resume_profile_review_from_api(
            resume_text=resume_text,
            target_roles=target_roles,
        )
    except JobAgentError as exc:
        st.error(str(exc))
        return

    parsed_profile = ResumeProfile.model_validate(
        dict(baseline_review.get("parsed_profile") or {})
    )
    draft = create_profile_draft(
        parsed_profile,
        target_roles,
        quality_warnings=baseline_review.get("quality_warnings") or [],
        missing_info_questions=baseline_review.get("missing_info_questions") or [],
    )
    st.session_state["profile_flow_baseline_review"] = baseline_review
    set_profile_draft_state(st.session_state, draft)
    st.success("Search-ready profile draft created.")


def _run_profile_enrichment(*, resume_text: str, target_roles: list[str]) -> None:
    try:
        enrichment_result = request_resume_profile_enrichment_from_api(
            resume_text=resume_text,
            target_roles=target_roles,
            use_llm=True,
        )
    except JobAgentError as exc:
        st.error(str(exc))
        return
    st.session_state["profile_flow_enrichment_result"] = enrichment_result
    st.success("Profile enrichment completed.")


def _render_profile_draft_editor(
    baseline_review: dict[str, Any],
    draft: ProfileDraft,
) -> None:
    _render_search_ready_overview(baseline_review, draft)
    _render_summary_card(draft)
    _render_chip_list_card(
        title="Target Directions",
        field="target_directions",
        help_text="Add or remove draft role directions for later job search.",
    )
    _render_chip_list_card(
        title="Core Skills",
        field="core_skills",
        help_text="These are the main profile signals the system will keep in focus.",
    )
    _render_chip_list_card(
        title="Auxiliary Skills",
        field="auxiliary_skills",
        help_text="Secondary skills stay editable and deduplicated.",
    )
    _render_chip_list_card(
        title="Search Keywords",
        field="search_keywords",
        help_text="这些关键词会影响后续岗位搜索。",
    )
    _render_preferences_card()
    _render_profile_notes_card()
    _render_missing_info_card()
    _render_quality_warnings_card()
    _render_raw_evidence_card()
    _render_confirm_profile_draft_card()


def _render_search_ready_overview(
    baseline_review: dict[str, Any],
    draft: ProfileDraft,
) -> None:
    profile = draft.search_ready_profile
    cols = st.columns(4)
    cols[0].metric("Target Directions", len(profile.target_directions))
    cols[1].metric("Core Skills", len(profile.core_skills))
    cols[2].metric("Keywords", len(profile.search_keywords))
    cols[3].metric("Missing Answers", len(draft.user_answers))
    if baseline_review.get("confidence_label"):
        st.caption(f"Confidence: {baseline_review['confidence_label']}")
    for warning in baseline_review.get("quality_warnings") or []:
        st.warning(str(warning))


def _render_summary_card(draft: ProfileDraft) -> None:
    st.markdown("#### Summary")
    summary = st.text_area(
        "summary",
        value=draft.search_ready_profile.summary,
        key="profile_flow_search_ready_summary",
        height=120,
    )
    if summary != draft.search_ready_profile.summary:
        _replace_profile_draft(update_profile_draft(draft, {"summary": summary}))


def _render_chip_list_card(*, title: str, field: str, help_text: str) -> None:
    draft = _current_profile_draft()
    if draft is None:
        return

    st.markdown(f"#### {title}")
    st.caption(help_text)
    items = list(getattr(draft.search_ready_profile, field))
    if not items:
        st.caption("No items yet.")
    for index, item in enumerate(items):
        label_col, action_col = st.columns([8, 1])
        label_col.markdown(f"`{item}`")
        if action_col.button("x", key=f"profile_flow_remove_{field}_{index}"):
            updated_items = [existing for existing in items if existing != item]
            _replace_profile_draft(update_profile_draft(draft, {field: updated_items}))
            st.rerun()

    add_key = f"profile_flow_add_{field}"
    new_value = st.text_input(
        f"Add {field}",
        key=add_key,
        placeholder="Type a value and click Add",
        label_visibility="collapsed",
    )
    if st.button(f"Add to {title}", key=f"profile_flow_add_button_{field}"):
        _replace_profile_draft(update_profile_draft(draft, {field: [*items, new_value]}))
        st.session_state[add_key] = ""
        st.rerun()


def _render_preferences_card() -> None:
    st.markdown("#### Preferences")
    _render_chip_list_card(
        title="Preferred Locations",
        field="preferred_locations",
        help_text="Keep only explicit location preferences.",
    )
    _render_chip_list_card(
        title="Work Arrangements",
        field="work_arrangements",
        help_text="Internship, full-time, remote, onsite, or hybrid.",
    )
    _render_chip_list_card(
        title="Company Preferences",
        field="company_preferences",
        help_text="Optional company or company-type preferences.",
    )


def _render_profile_notes_card() -> None:
    draft = _current_profile_draft()
    if draft is None:
        return

    st.markdown("#### Profile Notes")
    notes_text = st.text_area(
        "profile_notes",
        value="\n".join(draft.search_ready_profile.profile_notes),
        key="profile_flow_profile_notes_editor",
        height=140,
        help="One note per line.",
    )
    updated_notes = _split_lines(notes_text)
    if updated_notes != draft.search_ready_profile.profile_notes:
        _replace_profile_draft(update_profile_draft(draft, {"profile_notes": updated_notes}))


def _render_missing_info_card() -> None:
    draft = _current_profile_draft()
    if draft is None:
        return

    st.markdown("#### Missing Info Questions")
    questions = draft.search_ready_profile.missing_info_questions
    if not questions:
        st.success("No missing-info questions right now.")
        return

    for index, question in enumerate(questions):
        st.write(question)
        answer_key = f"profile_flow_missing_info_answer_{index}"
        st.text_area(
            "Your answer",
            value=draft.user_answers.get(question, ""),
            key=answer_key,
            height=80,
        )
        if st.button("Save Answer", key=f"profile_flow_missing_info_save_{index}"):
            updated = answer_missing_info_question(
                draft,
                question,
                st.session_state.get(answer_key, ""),
            )
            _replace_profile_draft(updated)
            st.success("Answer saved to draft.")
            st.rerun()


def _render_quality_warnings_card() -> None:
    draft = _current_profile_draft()
    if draft is None:
        return

    st.markdown("#### Quality Warnings")
    warnings = draft.search_ready_profile.quality_warnings
    if not warnings:
        st.caption("No quality warnings.")
        return
    for warning in warnings:
        st.warning(warning)


def _render_raw_evidence_card() -> None:
    draft = _current_profile_draft()
    if draft is None:
        return

    with st.expander("Raw Evidence / Parsed Details"):
        snapshot = draft.source_profile_snapshot or draft.search_ready_profile.source_profile_snapshot or {}
        st.json(
            {
                "skills": snapshot.get("skills") or [],
                "projects": snapshot.get("projects") or [],
                "work_experiences": snapshot.get("work_experiences") or [],
                "education": snapshot.get("education") or [],
                "highlights": snapshot.get("highlights") or [],
            }
        )


def _render_confirm_profile_draft_card() -> None:
    draft = _current_profile_draft()
    if draft is None:
        return

    st.markdown("#### Confirm Draft")
    if st.button("Confirm Profile Draft", key="profile_flow_confirm_draft", use_container_width=True):
        payload = confirm_profile_draft(draft)
        _replace_profile_draft(draft.model_copy(update={"status": "confirmed"}))
        set_confirmed_profile_draft_payload(st.session_state, payload)
        st.success("Confirmed profile payload is ready.")
        st.rerun()

    payload = st.session_state.get("profile_draft_confirmed_payload")
    if payload:
        st.success("Confirmed profile payload ready for persistence reuse.")
        st.json(payload)


def _current_profile_draft() -> ProfileDraft | None:
    draft = st.session_state.get("profile_flow_profile_draft")
    if draft is None:
        draft = st.session_state.get("profile_draft")
    if isinstance(draft, ProfileDraft):
        return draft
    if isinstance(draft, dict):
        return ProfileDraft.model_validate(draft)
    return None


def _replace_profile_draft(draft: ProfileDraft) -> None:
    st.session_state["profile_flow_profile_draft"] = draft
    st.session_state["profile_draft"] = draft


def _render_profile_overview(
    baseline_review: dict[str, Any],
    profile_draft: dict[str, Any],
) -> None:
    cols = st.columns(4)
    cols[0].metric("Skills", len(profile_draft.get("skills") or []))
    cols[1].metric("Projects", len(profile_draft.get("projects") or []))
    cols[2].metric("Work", len(profile_draft.get("work_experiences") or []))
    cols[3].metric("Education", len(profile_draft.get("education") or []))
    confidence_label = baseline_review.get("confidence_label")
    if confidence_label:
        st.caption(f"Confidence: {confidence_label}")
    for warning in baseline_review.get("quality_warnings") or []:
        st.warning(str(warning))
    suggested_edits = baseline_review.get("suggested_edits") or []
    if suggested_edits:
        with st.expander("Suggested edits"):
            for item in suggested_edits:
                st.write(f"- {item}")


def _render_skills_card(profile_draft: dict[str, Any]) -> None:
    token = _sync_token()
    skills_text = st.text_area(
        "Skills",
        value="\n".join(profile_draft.get("skills") or []),
        key=f"profile_flow_skills_editor_{token}",
        height=120,
        help="One skill per line.",
    )
    profile_draft["skills"] = dedupe_skills(_split_lines(skills_text))
    new_skill = st.text_input("Add skill", key="profile_flow_new_skill")
    if st.button("Add Skill", key="profile_flow_add_skill"):
        profile_draft["skills"] = dedupe_skills(
            [*profile_draft.get("skills", []), new_skill]
        )
        st.rerun()


def _render_projects_card(profile_draft: dict[str, Any]) -> None:
    token = _sync_token()
    projects = list(profile_draft.get("projects") or [])
    for index, project in enumerate(projects):
        with st.container(border=True):
            st.text_input(
                "Project name",
                value=str(project.get("name") or ""),
                key=f"profile_flow_project_{index}_name_{token}",
            )
            st.text_area(
                "Description",
                value=str(project.get("description") or ""),
                key=f"profile_flow_project_{index}_description_{token}",
                height=90,
            )
            st.text_area(
                "Technologies",
                value="\n".join(project.get("technologies") or []),
                key=f"profile_flow_project_{index}_technologies_{token}",
                height=90,
                help="One technology per line.",
            )
            st.text_area(
                "Highlights",
                value="\n".join(project.get("highlights") or []),
                key=f"profile_flow_project_{index}_highlights_{token}",
                height=90,
                help="One highlight per line.",
            )
            with st.expander("raw_text"):
                st.write(project.get("raw_text") or "")

            project["name"] = st.session_state[f"profile_flow_project_{index}_name_{token}"]
            project["description"] = st.session_state[
                f"profile_flow_project_{index}_description_{token}"
            ]
            project["technologies"] = dedupe_strings(
                _split_lines(st.session_state[f"profile_flow_project_{index}_technologies_{token}"])
            )
            project["highlights"] = dedupe_strings(
                _split_lines(st.session_state[f"profile_flow_project_{index}_highlights_{token}"])
            )
            _render_item_suggestion_status("project", index)
    profile_draft["projects"] = projects


def _render_work_card(profile_draft: dict[str, Any]) -> None:
    token = _sync_token()
    work_items = list(profile_draft.get("work_experiences") or [])
    if not work_items:
        st.info("No work experience evidence parsed yet.")
    for index, work in enumerate(work_items):
        with st.container(border=True):
            st.text_input(
                "Company",
                value=str(work.get("company") or ""),
                key=f"profile_flow_work_{index}_company_{token}",
            )
            st.text_input(
                "Role",
                value=str(work.get("role") or ""),
                key=f"profile_flow_work_{index}_role_{token}",
            )
            st.text_area(
                "Description",
                value=str(work.get("description") or ""),
                key=f"profile_flow_work_{index}_description_{token}",
                height=90,
            )
            st.text_area(
                "Technologies",
                value="\n".join(work.get("technologies") or []),
                key=f"profile_flow_work_{index}_technologies_{token}",
                height=90,
            )
            with st.expander("raw_text"):
                st.write(work.get("raw_text") or "")

            work["company"] = st.session_state[f"profile_flow_work_{index}_company_{token}"]
            work["role"] = st.session_state[f"profile_flow_work_{index}_role_{token}"]
            work["description"] = st.session_state[
                f"profile_flow_work_{index}_description_{token}"
            ]
            work["technologies"] = dedupe_strings(
                _split_lines(st.session_state[f"profile_flow_work_{index}_technologies_{token}"])
            )
            _render_item_suggestion_status("work", index)
    profile_draft["work_experiences"] = work_items


def _render_education_card(profile_draft: dict[str, Any]) -> None:
    token = _sync_token()
    education_items = list(profile_draft.get("education") or [])
    if not education_items:
        st.info("No education evidence parsed yet.")
    for index, education in enumerate(education_items):
        with st.container(border=True):
            for field in ["school", "degree", "major"]:
                st.text_input(
                    field,
                    value=str(education.get(field) or ""),
                    key=f"profile_flow_education_{index}_{field}_{token}",
                )
                education[field] = st.session_state[
                    f"profile_flow_education_{index}_{field}_{token}"
                ]
            with st.expander("raw_text"):
                st.write(education.get("raw_text") or "")
            _render_item_suggestion_status("education", index)
    profile_draft["education"] = education_items


def _render_certificates_highlights_card(profile_draft: dict[str, Any]) -> None:
    token = _sync_token()
    certificates_text = st.text_area(
        "Certificates",
        value="\n".join(profile_draft.get("certificates") or []),
        key=f"profile_flow_certificates_editor_{token}",
        height=100,
    )
    highlights_text = st.text_area(
        "Highlights",
        value="\n".join(profile_draft.get("highlights") or []),
        key=f"profile_flow_highlights_editor_{token}",
        height=120,
    )
    profile_draft["certificates"] = dedupe_strings(_split_lines(certificates_text))
    profile_draft["highlights"] = dedupe_strings(_split_lines(highlights_text))


def _render_enrichment_suggestions(
    enrichment_result: dict[str, Any] | None,
    profile_draft: dict[str, Any],
) -> None:
    if not enrichment_result:
        st.info("Run enrichment to review evidence-bound suggestions.")
        return

    metrics = (
        f"LLM success: {enrichment_result.get('llm_success_count', 0)} | "
        f"Fallback: {enrichment_result.get('fallback_count', 0)} | "
        f"Discarded: {enrichment_result.get('discarded_suggestion_count', 0)}"
    )
    st.caption(metrics)
    for warning in enrichment_result.get("quality_warnings") or []:
        st.warning(str(warning))

    suggestions = list(enrichment_result.get("enrichment_suggestions") or [])
    if not suggestions:
        st.info("No accepted-by-checker LLM suggestions were returned.")
        return

    for index, suggestion in enumerate(suggestions):
        key = _suggestion_key(index, suggestion)
        status = _suggestion_status(key)
        with st.container(border=True):
            st.caption(f"Status: {status}")
            st.write(
                f"{suggestion.get('section')}[{suggestion.get('item_index')}]."
                f"{suggestion.get('field')}"
            )
            st.write(suggestion.get("suggested_value"))
            st.caption(f"Source quote: {suggestion.get('source_quote')}")
            st.caption(f"Confidence: {suggestion.get('confidence_label', 'medium')}")
            for warning in suggestion.get("warnings") or []:
                st.warning(str(warning))

            edited_value = st.text_area(
                "Edit suggested value",
                value=_suggestion_value_text(suggestion.get("suggested_value")),
                key=f"profile_flow_suggestion_{index}_edit_value",
                height=80,
            )
            accept_col, edit_col, reject_col = st.columns(3)
            if accept_col.button("Accept", key=f"profile_flow_accept_{index}"):
                _accept_suggestion(key, suggestion, profile_draft)
            if edit_col.button("Save Edit", key=f"profile_flow_edit_{index}"):
                _edit_suggestion(key, suggestion, edited_value, profile_draft)
            if reject_col.button("Reject", key=f"profile_flow_reject_{index}"):
                _reject_suggestion(key, suggestion)


def _render_missing_info_questions(
    baseline_review: dict[str, Any],
    enrichment_result: dict[str, Any] | None,
    profile_draft: dict[str, Any],
) -> None:
    questions = []
    questions.extend(baseline_review.get("missing_info_questions") or [])
    if enrichment_result:
        questions.extend(enrichment_result.get("missing_info_questions") or [])
    questions = dedupe_strings([str(question) for question in questions])
    if not questions:
        st.success("No missing-info questions right now.")
        return

    for index, question in enumerate(questions):
        st.write(question)
        answer = st.text_area(
            "Your answer",
            key=f"profile_flow_missing_answer_{index}",
            height=80,
        )
        if st.button("Save Answer", key=f"profile_flow_save_missing_{index}"):
            updated = append_missing_info_answer(
                profile_draft,
                question=question,
                answer=answer,
            )
            profile_draft.update(updated)
            st.session_state.setdefault("profile_flow_missing_info_answers", {})[
                question
            ] = answer
            _bump_sync_token()
            st.success("Answer saved to draft notes.")
            st.rerun()

    token = _sync_token()
    st.text_area(
        "Draft notes",
        value=str(profile_draft.get("notes") or ""),
        key=f"profile_flow_notes_editor_{token}",
        height=120,
    )
    profile_draft["notes"] = st.session_state[f"profile_flow_notes_editor_{token}"]


def _render_confirm_profile(
    baseline_review: dict[str, Any],
    profile_draft: dict[str, Any],
) -> None:
    st.text_input(
        "target_roles",
        value=", ".join(profile_draft.get("target_roles") or []),
        key="profile_flow_target_roles_editor",
    )
    st.text_input(
        "preferred_locations",
        value=", ".join(profile_draft.get("preferred_locations") or []),
        key="profile_flow_preferred_locations_editor",
    )
    st.text_area(
        "constraints",
        value="\n".join(profile_draft.get("constraints") or []),
        key="profile_flow_constraints_editor",
        height=100,
    )
    profile_draft["target_roles"] = _split_comma_list(
        st.session_state["profile_flow_target_roles_editor"]
    )
    profile_draft["preferred_locations"] = _split_comma_list(
        st.session_state["profile_flow_preferred_locations_editor"]
    )
    profile_draft["constraints"] = _split_lines(
        st.session_state["profile_flow_constraints_editor"]
    )

    user_edits = build_confirm_user_edits_from_profile_draft(profile_draft)
    with st.expander("Confirm request preview"):
        st.json(user_edits.model_dump(mode="json"))

    if st.button("Confirm Profile", key="profile_flow_confirm", use_container_width=True):
        try:
            confirmed_profile_result = request_confirm_resume_profile_from_api(
                parsed_profile=dict(baseline_review.get("parsed_profile") or {}),
                user_edits=user_edits.model_dump(mode="json"),
            )
        except JobAgentError as exc:
            st.error(str(exc))
            return
        st.session_state["confirmed_profile_result"] = confirmed_profile_result
        default_query = " ".join(user_edits.target_roles).strip()
        if default_query:
            st.session_state["profile_flow_search_query"] = default_query
        st.success("Profile confirmed.")

    confirmed_profile_result = st.session_state.get("confirmed_profile_result")
    if confirmed_profile_result:
        st.success("Confirmed profile is ready.")
        with st.expander("Confirmed profile result"):
            st.json(confirmed_profile_result)
        for warning in confirmed_profile_result.get("remaining_warnings") or []:
            st.warning(str(warning))
        _render_save_confirmed_profile(baseline_review, profile_draft)
        _render_saved_profiles_list()


def _render_save_confirmed_profile(
    baseline_review: dict[str, Any],
    profile_draft: dict[str, Any],
) -> None:
    confirmed_profile_result = st.session_state.get("confirmed_profile_result")
    payload = build_confirmed_profile_save_payload(
        resume_text=st.session_state.get("profile_flow_resume_text", ""),
        baseline_review=baseline_review,
        confirmed_profile_result=confirmed_profile_result,
        accepted_suggestions=st.session_state.get("profile_flow_accepted_suggestions", {}),
        edited_suggestions=st.session_state.get("profile_flow_edited_suggestions", {}),
        rejected_suggestions=st.session_state.get("profile_flow_rejected_suggestions", {}),
        missing_info_answers=st.session_state.get("profile_flow_missing_info_answers", {}),
        notes=str(profile_draft.get("notes") or "").strip() or None,
    )
    if payload is None:
        return

    if st.button(
        "Save Confirmed Profile",
        key="profile_flow_save_confirmed_profile",
        use_container_width=True,
    ):
        try:
            response = request_save_confirmed_profile_from_api(payload=payload)
        except JobAgentError as exc:
            st.error(str(exc))
            return
        record_id = response.get("id")
        st.session_state["saved_confirmed_profile_id"] = record_id
        st.success(f"Saved confirmed profile: ID {record_id}")


def _render_saved_profiles_list() -> None:
    with st.expander("Saved Profiles"):
        if st.button("Refresh Saved Profiles", key="profile_flow_refresh_saved_profiles"):
            try:
                st.session_state["profile_flow_saved_profiles"] = (
                    request_saved_confirmed_profiles_from_api(limit=10)
                )
            except JobAgentError as exc:
                st.error(str(exc))
                return

        saved_profiles = st.session_state.get("profile_flow_saved_profiles")
        if not saved_profiles:
            st.caption("No saved profiles loaded yet.")
            return

        rows = [
            {
                "id": item.get("id"),
                "confidence_label": item.get("confidence_label"),
                "target_roles": ", ".join(item.get("target_roles") or []),
                "skill_count": item.get("skill_count"),
                "project_count": item.get("project_count"),
                "work_experience_count": item.get("work_experience_count"),
                "decision_count": item.get("decision_count"),
                "missing_answer_count": item.get("missing_answer_count"),
                "created_at": item.get("created_at"),
            }
            for item in saved_profiles
        ]
        st.dataframe(rows, hide_index=True, use_container_width=True)
        for item in saved_profiles:
            record_id = item.get("id")
            if st.button(f"Load {record_id}", key=f"profile_flow_load_saved_{record_id}"):
                try:
                    st.session_state["saved_confirmed_profile_detail"] = (
                        request_saved_confirmed_profile_detail_from_api(
                            record_id=int(record_id)
                        )
                    )
                except JobAgentError as exc:
                    st.error(str(exc))
                    return

        detail = st.session_state.get("saved_confirmed_profile_detail")
        if detail:
            with st.expander("Saved profile detail", expanded=True):
                st.json(detail)


def _render_search_and_brief_flow(
    resume_text: str,
    confirmed_profile_result: dict[str, Any],
) -> None:
    st.markdown("### Search Plan Preview")
    st.text_input(
        "query",
        key="profile_flow_search_query",
        placeholder="AI Agent Engineer Backend Engineer",
    )
    if st.button(
        "Preview Search Plan",
        key="profile_flow_search_plan",
        use_container_width=True,
    ):
        try:
            search_plan = request_profile_search_plan_from_api(
                query=st.session_state.get("profile_flow_search_query", ""),
                profile_context=_build_profile_context(confirmed_profile_result),
            )
        except JobAgentError as exc:
            st.error(str(exc))
        else:
            st.session_state["profile_search_plan"] = search_plan
            st.success("Search plan preview ready.")

    profile_search_plan = st.session_state.get("profile_search_plan")
    if profile_search_plan:
        st.text_input(
            "effective_query",
            value=str(profile_search_plan.get("effective_query", "")),
            disabled=True,
            key="profile_flow_effective_query_display",
        )

    st.markdown("### Brief From Search")
    if not profile_search_plan:
        st.info("Preview a search plan before running brief from search.")
        return

    provider = st.selectbox(
        "provider",
        options=["mock", "local_db", "gemini_cli", "cuhksz_live"],
        index=0,
        key="profile_flow_provider",
    )
    limit = st.number_input(
        "limit",
        min_value=1,
        max_value=10,
        value=5,
        key="profile_flow_limit",
    )
    use_llm_jd = st.checkbox(
        "use_llm_jd",
        value=False,
        key="profile_flow_use_llm_jd",
    )
    if st.button(
        "Run Brief From Search",
        key="profile_flow_run_brief",
        use_container_width=True,
    ):
        try:
            brief_result = request_job_brief_from_api(
                resume_text=resume_text,
                query=st.session_state.get("profile_flow_search_query", ""),
                provider=provider,
                limit=int(limit),
                use_llm_jd=use_llm_jd,
                profile_context=_build_profile_context(confirmed_profile_result),
            )
        except JobAgentError as exc:
            st.error(str(exc))
        else:
            st.session_state["brief_result"] = brief_result.model_dump(mode="json")
            st.success("Brief generated.")

    brief_result = st.session_state.get("brief_result")
    if brief_result:
        brief_report = JobBriefReport.model_validate(brief_result)
        st.write(
            f"Provider: {brief_report.provider} | Total jobs: {brief_report.total_jobs} | Query: {brief_report.query}"
        )
        recommendations = [
            {
                "rank": item.rank,
                "title": item.job.title,
                "company": item.job.company,
                "fit_score": item.fit_score,
                "quality": format_scoring_quality(item.scoring_quality),
            }
            for item in brief_report.recommended_jobs
        ]
        if recommendations:
            st.dataframe(recommendations, hide_index=True, use_container_width=True)


def _render_raw_debug() -> None:
    with st.expander("Advanced / Raw JSON Debug"):
        st.json(st.session_state.get("profile_flow_baseline_review"))
        draft = _current_profile_draft()
        st.json(draft.model_dump(mode="json") if draft else None)
        st.json(st.session_state.get("profile_draft_confirmed_payload"))


def _render_reset_button() -> None:
    st.markdown("### Reset")
    if st.button(
        "Reset Profile Flow",
        key="profile_flow_reset",
        use_container_width=True,
    ):
        for key in FLOW_KEYS:
            st.session_state.pop(key, None)
        st.success("Profile flow state cleared.")
        st.rerun()


def _accept_suggestion(
    key: str,
    suggestion: dict[str, Any],
    profile_draft: dict[str, Any],
) -> None:
    updated = apply_suggestion_to_profile_draft(profile_draft, suggestion)
    profile_draft.update(updated)
    st.session_state["profile_flow_accepted_suggestions"][key] = suggestion
    st.session_state["profile_flow_rejected_suggestions"].pop(key, None)
    st.session_state["profile_flow_edited_suggestions"].pop(key, None)
    _bump_sync_token()
    st.success("Suggestion accepted.")
    st.rerun()


def _edit_suggestion(
    key: str,
    suggestion: dict[str, Any],
    edited_value: str,
    profile_draft: dict[str, Any],
) -> None:
    updated = apply_suggestion_to_profile_draft(
        profile_draft,
        suggestion,
        edited_value=edited_value,
    )
    profile_draft.update(updated)
    edited_record = dict(suggestion)
    edited_record["edited_value"] = edited_value
    st.session_state["profile_flow_edited_suggestions"][key] = edited_record
    st.session_state["profile_flow_accepted_suggestions"].pop(key, None)
    st.session_state["profile_flow_rejected_suggestions"].pop(key, None)
    _bump_sync_token()
    st.success("Edited suggestion applied.")
    st.rerun()


def _reject_suggestion(key: str, suggestion: dict[str, Any]) -> None:
    st.session_state["profile_flow_rejected_suggestions"][key] = suggestion
    st.session_state["profile_flow_accepted_suggestions"].pop(key, None)
    st.session_state["profile_flow_edited_suggestions"].pop(key, None)
    st.success("Suggestion rejected.")


def _sync_token() -> int:
    return int(st.session_state.get("profile_flow_sync_token", 0))


def _bump_sync_token() -> None:
    st.session_state["profile_flow_sync_token"] = _sync_token() + 1


def _suggestion_status(key: str) -> str:
    if key in st.session_state.get("profile_flow_accepted_suggestions", {}):
        return "accepted"
    if key in st.session_state.get("profile_flow_edited_suggestions", {}):
        return "edited"
    if key in st.session_state.get("profile_flow_rejected_suggestions", {}):
        return "rejected"
    return "pending"


def _render_item_suggestion_status(section: str, item_index: int) -> None:
    enrichment_result = st.session_state.get("profile_flow_enrichment_result") or {}
    suggestions = [
        suggestion
        for suggestion in enrichment_result.get("enrichment_suggestions") or []
        if suggestion.get("section") == section
        and suggestion.get("item_index") == item_index
    ]
    if suggestions:
        st.caption(f"{len(suggestions)} enrichment suggestion(s) available below.")


def _suggestion_key(index: int, suggestion: dict[str, Any]) -> str:
    return "|".join(
        [
            str(index),
            str(suggestion.get("section") or ""),
            str(suggestion.get("item_index") or ""),
            str(suggestion.get("field") or ""),
            _suggestion_value_text(suggestion.get("suggested_value")),
        ]
    )


def _suggestion_value_text(value: Any) -> str:
    if isinstance(value, list):
        return "\n".join(str(item) for item in value)
    return str(value or "")


def _split_comma_list(value: str) -> list[str]:
    items: list[str] = []
    for item in value.split(","):
        normalized = item.strip()
        if normalized and normalized not in items:
            items.append(normalized)
    return items


def _split_lines(value: str) -> list[str]:
    items: list[str] = []
    for item in value.splitlines():
        normalized = item.strip()
        if normalized and normalized not in items:
            items.append(normalized)
    return items


def _build_profile_context(confirmed_profile_result: dict[str, object]) -> dict[str, object]:
    return {
        "confirmed_profile": dict(confirmed_profile_result.get("confirmed_profile") or {}),
        "user_confirmed_data": dict(confirmed_profile_result.get("user_confirmed_data") or {}),
    }


def _call_api(
    path: str,
    payload: dict[str, object],
    *,
    api_base_url: str = DEFAULT_API_BASE_URL,
    timeout_seconds: int = DEFAULT_API_TIMEOUT_SECONDS,
    unavailable_error_code: str = "api_unavailable",
    failure_error_code: str = "api_request_failed",
) -> dict[str, object]:
    request = Request(
        f"{api_base_url.rstrip('/')}{path}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            response_body = response.read().decode("utf-8")
    except HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        error_payload = _load_json_payload(error_body)
        raise JobAgentError(
            str(error_payload.get("detail", f"{path} failed with status {exc.code}")),
            str(error_payload.get("error_code", failure_error_code)),
        ) from exc
    except URLError as exc:
        raise JobAgentError(
            "Cannot connect to FastAPI backend. Start it with: "
            ".venv\\Scripts\\python.exe -m uvicorn app.main:app --reload",
            unavailable_error_code,
        ) from exc

    return _load_json_payload(response_body)


def _get_api(
    path: str,
    *,
    api_base_url: str = DEFAULT_API_BASE_URL,
    timeout_seconds: int = DEFAULT_API_TIMEOUT_SECONDS,
    unavailable_error_code: str = "api_unavailable",
    failure_error_code: str = "api_request_failed",
) -> dict[str, object] | list[dict[str, object]]:
    request = Request(
        f"{api_base_url.rstrip('/')}{path}",
        headers={"Content-Type": "application/json"},
        method="GET",
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            response_body = response.read().decode("utf-8")
    except HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        error_payload = _load_json_payload(error_body)
        raise JobAgentError(
            str(error_payload.get("detail", f"{path} failed with status {exc.code}")),
            str(error_payload.get("error_code", failure_error_code)),
        ) from exc
    except URLError as exc:
        raise JobAgentError(
            "Cannot connect to FastAPI backend. Start it with: "
            ".venv\\Scripts\\python.exe -m uvicorn app.main:app --reload",
            unavailable_error_code,
        ) from exc

    return _load_json_payload(response_body)


def _load_json_payload(raw_text: str) -> dict[str, object] | list[dict[str, object]]:
    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise JobAgentError("Job Brief API returned invalid JSON", "brief_api_invalid_json") from exc

    if not isinstance(payload, (dict, list)):
        raise JobAgentError("Job Brief API returned an invalid response object", "brief_api_invalid_json")
    return payload


def format_scoring_quality(value: str) -> str:
    return SCORING_QUALITY_LABELS.get(value, value)
