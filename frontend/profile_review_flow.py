from __future__ import annotations

import hashlib
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
from app.services.llm_provider import DEFAULT_LLM_PROVIDER, resolve_llm_provider
from app.services.resume_file_service import (
    ResumeFileParseError,
    extract_text_from_resume_file,
    get_resume_file_type,
    normalize_resume_filename,
)
from app.services.profile_draft_service import (
    answer_missing_info_question,
    confirm_profile_draft,
    create_profile_draft,
    update_profile_draft,
)
from frontend.profile_review_state import (
    get_profile_flow_step,
    get_selected_provider,
    set_confirmed_profile_draft_payload,
    set_profile_draft_state,
    set_profile_flow_step,
    set_selected_provider,
)

DEFAULT_API_BASE_URL = os.getenv("JOBAGENT_API_BASE_URL", "http://127.0.0.1:8000")
DEFAULT_API_TIMEOUT_SECONDS = 30

FLOW_KEYS = [
    "profile_flow_baseline_review",
    "profile_flow_profile_draft",
    "profile_draft_confirmed_payload",
    "profile_flow_step",
    "profile_flow_selected_provider",
    "profile_flow_selected_provider_metadata",
    "profile_flow_uploaded_filename",
    "profile_flow_uploaded_file_type",
    "profile_flow_uploaded_text_length",
    "profile_flow_resume_input_source",
    "profile_flow_upload_error",
    "profile_flow_upload_fingerprint",
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


def render_profile_review_flow_tab(
    *,
    sample_resume: str,
    selected_provider: str = DEFAULT_LLM_PROVIDER,
) -> None:
    _ensure_initial_state(sample_resume)
    _render_profile_setup_intro()

    provider_resolution = resolve_llm_provider(selected_provider)
    set_selected_provider(
        st.session_state,
        provider_resolution.provider,
        {
            "provider": provider_resolution.provider,
            "model": provider_resolution.model,
            "base_url": provider_resolution.base_url,
            "configured": provider_resolution.configured,
            "reason": provider_resolution.reason,
        },
    )
    _render_provider_status(provider_resolution)

    step = get_profile_flow_step(st.session_state)
    baseline_review = st.session_state.get("profile_flow_baseline_review")
    profile_draft = st.session_state.get("profile_flow_profile_draft")

    if step == "resume_input":
        _render_resume_input_step()
    elif step == "parsed_review":
        if baseline_review:
            _render_parsed_review_step(baseline_review)
        else:
            set_profile_flow_step(st.session_state, "resume_input")
            st.info("Start with resume input.")
    elif step == "profile_draft":
        if baseline_review and profile_draft:
            _render_profile_draft_step(baseline_review, profile_draft)
        else:
            set_profile_flow_step(st.session_state, "resume_input")
            st.info("Generate a draft from the parsed review first.")
    elif step == "profile_saved":
        payload = st.session_state.get("profile_draft_confirmed_payload")
        if payload:
            _render_profile_saved_step(payload)
        else:
            set_profile_flow_step(st.session_state, "resume_input")
            st.info("Save a profile draft first.")

    _render_raw_debug()
    _render_reset_button()


def request_resume_profile_review_from_api(
    *,
    resume_text: str,
    target_roles: list[str],
    llm_provider: str,
    api_base_url: str = DEFAULT_API_BASE_URL,
    timeout_seconds: int = DEFAULT_API_TIMEOUT_SECONDS,
) -> dict[str, object]:
    return _call_api(
        "/resume/profile-review",
        {
            "resume_text": resume_text,
            "target_roles": target_roles,
            "llm_provider": llm_provider,
        },
        api_base_url=api_base_url,
        timeout_seconds=timeout_seconds,
        unavailable_error_code="profile_review_api_unavailable",
        failure_error_code="profile_review_api_request_failed",
    )


def _ensure_initial_state(sample_resume: str) -> None:
    st.session_state.setdefault("profile_flow_resume_text", sample_resume)
    st.session_state.setdefault(
        "profile_flow_initial_target_roles",
        "AI Agent Engineer, Backend Engineer",
    )
    st.session_state.setdefault("profile_flow_uploaded_filename", None)
    st.session_state.setdefault("profile_flow_uploaded_file_type", None)
    st.session_state.setdefault("profile_flow_uploaded_text_length", 0)
    st.session_state.setdefault(
        "profile_flow_resume_input_source",
        "paste" if sample_resume.strip() else "empty",
    )
    st.session_state.setdefault("profile_flow_upload_error", None)
    st.session_state.setdefault("profile_flow_upload_fingerprint", None)
    st.session_state.setdefault("profile_flow_step", "resume_input")
    st.session_state.setdefault("profile_flow_selected_provider", DEFAULT_LLM_PROVIDER)
    st.session_state.setdefault("profile_flow_selected_provider_metadata", {})


def _render_profile_setup_intro() -> None:
    st.subheader("JobAgent Profile Setup")
    st.caption(
        "Upload or paste your resume first. JobAgent will parse your background, build a searchable profile, and only then continue to JD search and job analysis."
    )
    phases = [
        ("01 Resume", True),
        ("02 Profile", True),
        ("03 Search", False),
        ("04 Brief", False),
    ]
    with st.container(border=True):
        cols = st.columns(len(phases))
        for col, (label, active) in zip(cols, phases):
            col.markdown(f"**{label}**" if active else label)


def _render_provider_status(provider_resolution: Any) -> None:
    with st.container(border=True):
        st.markdown("### Model Context")
        st.write(f"Provider: `{provider_resolution.provider}`")
        st.write(f"Model: `{provider_resolution.model or 'N/A'}`")
        st.write(f"Base URL: `{provider_resolution.base_url or 'N/A'}`")
        st.write(f"Configured: `{'yes' if provider_resolution.configured else 'no'}`")
        st.write(
            f"Fallback: `deterministic / mock when unavailable`"
        )
        if provider_resolution.reason:
            st.caption(f"Reason: {provider_resolution.reason}")
        st.caption("Resume parse review stays deterministic. Provider metadata is recorded for the draft.")


def _render_resume_input_step() -> None:
    st.markdown("### Step 1: Add Resume")
    st.caption(
        "Start by uploading a txt/md resume or pasting the full resume text below."
    )
    _render_resume_upload_entry()
    existing_text = str(st.session_state.get("profile_flow_resume_text") or "")
    resume_text = st.text_area(
        "Paste resume text",
        key="profile_flow_resume_text",
        height=220,
    )
    _update_resume_input_source(existing_text, resume_text)
    target_roles_text = st.text_input(
        "Target roles",
        key="profile_flow_initial_target_roles",
        placeholder="Optional target roles, e.g. AI Agent Engineer, Backend Engineer",
    )
    st.caption("Target roles are optional for the first profile setup pass.")
    target_roles = _split_comma_list(target_roles_text)
    provider = get_selected_provider(st.session_state)
    st.caption(f"Selected provider: {provider}")

    if st.button("Start Profile Setup", key="profile_flow_parse", use_container_width=True):
        _parse_resume_profile(
            resume_text=resume_text,
            target_roles=target_roles,
            llm_provider=provider,
        )


def build_resume_upload_state(filename: str, content: bytes) -> dict[str, Any]:
    normalized_filename = normalize_resume_filename(filename)
    extracted_text = extract_text_from_resume_file(normalized_filename, content)
    file_type = get_resume_file_type(normalized_filename)
    return {
        "profile_flow_resume_text": extracted_text,
        "profile_flow_uploaded_filename": normalized_filename,
        "profile_flow_uploaded_file_type": file_type,
        "profile_flow_uploaded_text_length": len(extracted_text),
        "profile_flow_resume_input_source": "upload",
        "profile_flow_upload_error": None,
        "profile_flow_upload_fingerprint": f"{normalized_filename}:{hashlib.sha256(content).hexdigest()}",
    }


def _render_resume_upload_entry() -> None:
    uploaded_file = st.file_uploader(
        "Upload resume file",
        type=["txt", "md"],
        key="profile_flow_resume_upload",
    )
    if uploaded_file is not None:
        file_bytes = uploaded_file.getvalue()
        fingerprint = f"{uploaded_file.name}:{hashlib.sha256(file_bytes).hexdigest()}"
        if st.session_state.get("profile_flow_upload_fingerprint") != fingerprint:
            _apply_resume_upload(uploaded_file.name, file_bytes)

    with st.container(border=True):
        st.markdown("#### Resume source")
        source = st.session_state.get("profile_flow_resume_input_source") or "empty"
        if source in {"upload", "upload_edited"}:
            st.write(f"File: `{st.session_state.get('profile_flow_uploaded_filename') or 'N/A'}`")
            st.write(f"Type: `{st.session_state.get('profile_flow_uploaded_file_type') or 'N/A'}`")
            st.write(f"Text length: `{st.session_state.get('profile_flow_uploaded_text_length') or 0}`")
            st.write(f"Status: `{source}`")
        else:
            st.write(f"Status: `{source}`")
        upload_error = st.session_state.get("profile_flow_upload_error")
        if upload_error:
            st.error(str(upload_error))


def _apply_resume_upload(filename: str, content: bytes) -> None:
    try:
        upload_state = build_resume_upload_state(filename, content)
    except ResumeFileParseError as exc:
        st.session_state["profile_flow_upload_error"] = str(exc)
        st.session_state["profile_flow_upload_fingerprint"] = None
        return

    st.session_state.update(upload_state)
    st.success(f"Resume loaded from file: {upload_state['profile_flow_uploaded_filename']}")


def _update_resume_input_source(previous_text: str, current_text: str) -> None:
    if current_text == previous_text:
        return
    normalized = current_text.strip()
    if not normalized:
        st.session_state["profile_flow_resume_input_source"] = "empty"
        return
    current_source = str(st.session_state.get("profile_flow_resume_input_source") or "empty")
    if current_source in {"upload", "upload_edited"}:
        st.session_state["profile_flow_resume_input_source"] = "upload_edited"
        return
    st.session_state["profile_flow_resume_input_source"] = "paste"


def _parse_resume_profile(
    *,
    resume_text: str,
    target_roles: list[str],
    llm_provider: str,
) -> None:
    normalized_resume_text = resume_text.strip()
    if not normalized_resume_text:
        st.session_state["profile_flow_resume_input_source"] = "empty"
        st.warning("Add resume text before starting profile setup.")
        return
    try:
        baseline_review = request_resume_profile_review_from_api(
            resume_text=normalized_resume_text,
            target_roles=target_roles,
            llm_provider=llm_provider,
        )
    except JobAgentError as exc:
        st.error(str(exc))
        return

    st.session_state["profile_flow_baseline_review"] = baseline_review
    st.session_state["profile_draft_confirmed_payload"] = None
    set_profile_flow_step(st.session_state, "parsed_review")
    st.success("Parsed resume review is ready.")


def _render_parsed_review_step(baseline_review: dict[str, Any]) -> None:
    st.markdown("### Step 2: Review Parsed Resume")
    st.caption(
        "Confirm that JobAgent understood the core facts of your resume before generating the searchable profile."
    )
    parsed_profile = dict(baseline_review.get("parsed_profile") or {})
    st.write(f"Skills: {', '.join(parsed_profile.get('skills') or []) or '-'}")
    st.write(f"Projects: {len(parsed_profile.get('projects') or [])}")
    st.write(f"Work Experiences: {len(parsed_profile.get('work_experiences') or [])}")
    st.write(f"Education: {len(parsed_profile.get('education') or [])}")
    st.write(f"Highlights: {len(parsed_profile.get('highlights') or [])}")
    for warning in baseline_review.get("quality_warnings") or []:
        st.warning(str(warning))
    for question in baseline_review.get("missing_info_questions") or []:
        st.info(str(question))
    with st.expander("Raw parsed profile"):
        st.json(parsed_profile)

    back_col, next_col = st.columns(2)
    if back_col.button("Back", key="profile_flow_back_to_input", use_container_width=True):
        set_profile_flow_step(st.session_state, "resume_input")
        st.rerun()
    if next_col.button(
        "Generate Search-Ready Profile",
        key="profile_flow_generate_draft",
        use_container_width=True,
    ):
        _generate_profile_draft(baseline_review)


def _generate_profile_draft(baseline_review: dict[str, Any]) -> None:
    parsed_profile = ResumeProfile.model_validate(
        dict(baseline_review.get("parsed_profile") or {})
    )
    target_roles = _split_comma_list(
        str(st.session_state.get("profile_flow_initial_target_roles") or "")
    )
    draft = create_profile_draft(
        parsed_profile,
        target_roles,
        quality_warnings=baseline_review.get("quality_warnings") or [],
        missing_info_questions=baseline_review.get("missing_info_questions") or [],
        llm_provider=get_selected_provider(st.session_state),
    )
    set_profile_draft_state(st.session_state, draft)
    set_profile_flow_step(st.session_state, "profile_draft")
    st.success("Search-ready profile draft created.")
    st.rerun()


def _render_profile_draft_step(
    baseline_review: dict[str, Any],
    draft_like: ProfileDraft | dict[str, Any],
) -> None:
    draft = _current_profile_draft() if not isinstance(draft_like, ProfileDraft) else draft_like
    if draft is None:
        st.info("No profile draft available.")
        return

    st.markdown("### Step 3: Search-Ready Profile Draft")
    st.caption(f"Draft provider: {draft.llm_provider} | configured: {'yes' if draft.llm_configured else 'no'}")
    _render_profile_draft_editor(baseline_review, draft)

    back_col, save_col = st.columns(2)
    if back_col.button("Back", key="profile_flow_back_to_parsed_review", use_container_width=True):
        set_profile_flow_step(st.session_state, "parsed_review")
        st.rerun()
    if save_col.button("Save Profile", key="profile_flow_save_profile", use_container_width=True):
        _save_profile_draft(draft)
        st.rerun()


def _render_profile_saved_step(payload: dict[str, Any]) -> None:
    st.markdown("### Step 4: Profile Saved")
    confirmed = payload.get("confirmed_search_ready_profile") or {}
    st.success("Your search-ready profile has been saved.")
    st.caption(
        "You can return to the start or continue to the later JD search and job analysis stage."
    )
    st.write(f"Summary: {confirmed.get('summary') or '-'}")
    st.write(
        "Target Directions: "
        + (", ".join(confirmed.get("target_directions") or []) or "-")
    )
    with st.expander("Confirmed profile payload", expanded=True):
        st.json(payload)

    home_col, next_col = st.columns(2)
    if home_col.button("Return to Start", key="profile_flow_return_home", use_container_width=True):
        set_profile_flow_step(st.session_state, "resume_input")
        st.rerun()
    if next_col.button(
        "Continue to JD Search / Analysis",
        key="profile_flow_continue_to_jd",
        use_container_width=True,
    ):
        st.session_state["profile_flow_next_stage"] = "jd_search_ready"
        st.info("Next stage marked as ready for JD search / analysis.")


def _save_profile_draft(draft: ProfileDraft) -> None:
    payload = confirm_profile_draft(draft)
    _replace_profile_draft(draft.model_copy(update={"status": "confirmed"}))
    set_confirmed_profile_draft_payload(st.session_state, payload)
    set_profile_flow_step(st.session_state, "profile_saved")
    st.success("Profile saved.")


def _render_profile_draft_editor(
    baseline_review: dict[str, Any],
    draft: ProfileDraft,
) -> None:
    _render_search_ready_overview(baseline_review, draft)
    _render_summary_card(draft)
    _render_chip_list_card("Target Directions", "target_directions", "Role directions for later search.")
    _render_chip_list_card("Core Skills", "core_skills", "Primary candidate signals.")
    _render_chip_list_card("Auxiliary Skills", "auxiliary_skills", "Secondary candidate signals.")
    _render_chip_list_card("Search Keywords", "search_keywords", "These keywords will influence later job search.")
    _render_chip_list_card("Preferred Locations", "preferred_locations", "Explicit location preferences.")
    _render_chip_list_card("Work Arrangements", "work_arrangements", "Internship, full-time, remote, onsite, or hybrid.")
    _render_chip_list_card("Company Preferences", "company_preferences", "Optional company or company-type preferences.")
    _render_profile_notes_card()
    _render_missing_info_card()
    _render_quality_warnings_card()
    _render_raw_evidence_card()


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


def _render_chip_list_card(title: str, field: str, help_text: str) -> None:
    draft = _current_profile_draft()
    if draft is None:
        return
    items = list(getattr(draft.search_ready_profile, field))
    st.markdown(f"#### {title}")
    st.caption(help_text)
    for index, item in enumerate(items):
        text_col, remove_col = st.columns([8, 1])
        text_col.markdown(f"`{item}`")
        if remove_col.button("x", key=f"profile_flow_remove_{field}_{index}"):
            _replace_profile_draft(update_profile_draft(draft, {field: [x for x in items if x != item]}))
            st.rerun()
    new_value = st.text_input(
        f"Add {field}",
        key=f"profile_flow_add_{field}",
        placeholder="Type a value and click Add",
        label_visibility="collapsed",
    )
    if st.button(f"Add to {title}", key=f"profile_flow_add_button_{field}"):
        _replace_profile_draft(update_profile_draft(draft, {field: [*items, new_value]}))
        st.session_state[f"profile_flow_add_{field}"] = ""
        st.rerun()


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
    )
    updated_notes = _split_lines(notes_text)
    if updated_notes != draft.search_ready_profile.profile_notes:
        _replace_profile_draft(update_profile_draft(draft, {"profile_notes": updated_notes}))


def _render_missing_info_card() -> None:
    draft = _current_profile_draft()
    if draft is None:
        return
    st.markdown("#### Missing Info Questions")
    if not draft.search_ready_profile.missing_info_questions:
        st.success("No missing-info questions right now.")
        return
    for index, question in enumerate(draft.search_ready_profile.missing_info_questions):
        st.write(question)
        answer_key = f"profile_flow_missing_info_answer_{index}"
        st.text_area("Your answer", value=draft.user_answers.get(question, ""), key=answer_key, height=80)
        if st.button("Save Answer", key=f"profile_flow_missing_info_save_{index}"):
            _replace_profile_draft(
                answer_missing_info_question(
                    draft,
                    question,
                    st.session_state.get(answer_key, ""),
                )
            )
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
        st.json(snapshot)


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


def _render_safe_debug_json(label: str, payload: Any) -> None:
    st.caption(label)
    if payload is None:
        st.caption("Not available yet.")
        return
    if isinstance(payload, ProfileDraft):
        st.json(payload.model_dump(mode="json"))
        return
    if hasattr(payload, "model_dump"):
        st.json(payload.model_dump(mode="json"))
        return
    if isinstance(payload, (dict, list, str, int, float, bool)):
        st.json(payload)
        return
    st.code(str(payload))


def _render_raw_debug() -> None:
    with st.expander("Advanced / Raw JSON Debug"):
        _render_safe_debug_json(
            "Baseline review",
            st.session_state.get("profile_flow_baseline_review"),
        )
        draft = _current_profile_draft()
        _render_safe_debug_json("Profile draft", draft)
        _render_safe_debug_json(
            "Confirmed payload",
            st.session_state.get("profile_draft_confirmed_payload"),
        )


def _render_reset_button() -> None:
    st.markdown("### Reset")
    if st.button("Reset Profile Flow", key="profile_flow_reset", use_container_width=True):
        for key in FLOW_KEYS:
            st.session_state.pop(key, None)
        st.success("Profile flow state cleared.")
        st.rerun()


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


def _load_json_payload(raw_text: str) -> dict[str, object] | list[dict[str, object]]:
    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise JobAgentError("Job Brief API returned invalid JSON", "brief_api_invalid_json") from exc

    if not isinstance(payload, (dict, list)):
        raise JobAgentError("Job Brief API returned an invalid response object", "brief_api_invalid_json")
    return payload
