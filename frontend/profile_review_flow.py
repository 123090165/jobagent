from __future__ import annotations

import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import streamlit as st

from app.schemas.brief import JobBriefReport
from app.services.errors import JobAgentError

DEFAULT_API_BASE_URL = os.getenv("JOBAGENT_API_BASE_URL", "http://127.0.0.1:8000")
DEFAULT_API_TIMEOUT_SECONDS = 30
SCORING_QUALITY_LABELS = {
    "full_jd": "完整 JD",
    "partial_jd": "部分 JD",
    "external_link_only": "外链详情",
    "snippet_only": "摘要评估",
    "invalid": "无效 JD",
}


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
            "无法连接 FastAPI 后端，请先启动 .venv\\Scripts\\python.exe -m uvicorn app.main:app --reload",
            "brief_api_unavailable",
        ) from exc

    return JobBriefReport.model_validate(_load_json_payload(response_body))


def render_profile_review_flow_tab(*, sample_resume: str) -> None:
    st.subheader("Slate-like Profile Review Flow")
    st.caption(
        "Resume -> Profile Review -> Confirm -> Search Plan -> Brief。这个面板只串联现有 API，不新增后端逻辑。"
    )

    if "profile_flow_resume_text" not in st.session_state:
        st.session_state["profile_flow_resume_text"] = sample_resume
    if "profile_flow_initial_target_roles" not in st.session_state:
        st.session_state["profile_flow_initial_target_roles"] = (
            "AI Agent Engineer, Backend Engineer"
        )
    if "profile_flow_search_query" not in st.session_state:
        st.session_state["profile_flow_search_query"] = ""

    st.markdown("### 01 Resume")
    resume_text = st.text_area(
        "resume_text",
        key="profile_flow_resume_text",
        height=220,
    )
    st.text_input(
        "target_roles (initial, comma-separated)",
        key="profile_flow_initial_target_roles",
        placeholder="AI Agent Engineer, Backend Engineer",
    )
    if st.button("Parse Resume Profile", key="profile_flow_parse", use_container_width=True):
        try:
            profile_review = request_resume_profile_review_from_api(
                resume_text=resume_text,
                target_roles=_split_comma_list(
                    st.session_state.get("profile_flow_initial_target_roles", "")
                ),
            )
        except JobAgentError as exc:
            st.error(str(exc))
        else:
            st.session_state["profile_review"] = profile_review
            st.success("Resume profile parsed.")

    profile_review = st.session_state.get("profile_review")
    if profile_review:
        st.json(profile_review.get("parsed_profile") or {})
        for warning in profile_review.get("quality_warnings") or []:
            st.warning(str(warning))
        for question in profile_review.get("missing_info_questions") or []:
            st.info(str(question))
        suggested_edits = profile_review.get("suggested_edits") or []
        if suggested_edits:
            with st.expander("Suggested edits"):
                for item in suggested_edits:
                    st.write(f"- {item}")
        editable_sections = profile_review.get("editable_sections") or []
        if editable_sections:
            st.caption(
                "Editable sections: "
                + ", ".join(str(section) for section in editable_sections)
            )
        confidence_label = profile_review.get("confidence_label")
        if confidence_label:
            st.caption(f"Confidence: {confidence_label}")
        if st.button(
            "Run LLM Profile Enrichment",
            key="profile_flow_run_enrichment",
            use_container_width=True,
        ):
            try:
                enrichment_result = request_resume_profile_enrichment_from_api(
                    resume_text=resume_text,
                    target_roles=_split_comma_list(
                        st.session_state.get("profile_flow_initial_target_roles", "")
                    ),
                    use_llm=True,
                )
            except JobAgentError as exc:
                st.error(str(exc))
            else:
                st.session_state["profile_enrichment_result"] = enrichment_result
                st.success("Profile enrichment completed.")

    profile_enrichment_result = st.session_state.get("profile_enrichment_result")
    if profile_enrichment_result:
        suggestions = profile_enrichment_result.get("enrichment_suggestions") or []
        metrics = (
            f"LLM success: {profile_enrichment_result.get('llm_success_count', 0)} | "
            f"Fallback: {profile_enrichment_result.get('fallback_count', 0)} | "
            f"Discarded: {profile_enrichment_result.get('discarded_suggestion_count', 0)}"
        )
        st.caption(metrics)
        for warning in profile_enrichment_result.get("quality_warnings") or []:
            st.warning(str(warning))
        if suggestions:
            with st.expander("Enrichment suggestions", expanded=True):
                for suggestion in suggestions:
                    st.write(
                        f"- {suggestion.get('section')}[{suggestion.get('item_index')}]."
                        f"{suggestion.get('field')}: {suggestion.get('suggested_value')}"
                    )
                    st.caption(f"Quote: {suggestion.get('source_quote')}")
                    for warning in suggestion.get("warnings") or []:
                        st.warning(str(warning))

    st.markdown("### 02 Profile Review")
    if profile_review:
        st.text_input(
            "target_roles",
            key="profile_flow_target_roles_edit",
            placeholder="AI Agent Engineer, Backend Engineer",
        )
        st.text_input(
            "preferred_locations",
            key="profile_flow_preferred_locations_edit",
            placeholder="Shenzhen, Remote",
        )
        st.text_input(
            "additional_skills",
            key="profile_flow_additional_skills_edit",
            placeholder="LangGraph, Pydantic",
        )
        st.text_area(
            "project_clarifications",
            key="profile_flow_project_clarifications_edit",
            height=120,
            placeholder="one item per line",
        )
        st.text_area(
            "work_experience_clarifications",
            key="profile_flow_work_experience_clarifications_edit",
            height=120,
            placeholder="one item per line",
        )
        st.text_area(
            "constraints",
            key="profile_flow_constraints_edit",
            height=100,
            placeholder="one item per line",
        )
        st.text_area(
            "notes",
            key="profile_flow_notes_edit",
            height=100,
        )

        if st.button("Confirm Profile", key="profile_flow_confirm", use_container_width=True):
            user_edits = {
                "target_roles": _split_comma_list(
                    st.session_state.get("profile_flow_target_roles_edit", "")
                ),
                "preferred_locations": _split_comma_list(
                    st.session_state.get("profile_flow_preferred_locations_edit", "")
                ),
                "additional_skills": _split_comma_list(
                    st.session_state.get("profile_flow_additional_skills_edit", "")
                ),
                "project_clarifications": _split_lines(
                    st.session_state.get("profile_flow_project_clarifications_edit", "")
                ),
                "work_experience_clarifications": _split_lines(
                    st.session_state.get(
                        "profile_flow_work_experience_clarifications_edit",
                        "",
                    )
                ),
                "constraints": _split_lines(
                    st.session_state.get("profile_flow_constraints_edit", "")
                ),
                "notes": (
                    st.session_state.get("profile_flow_notes_edit", "").strip() or None
                ),
            }
            try:
                confirmed_profile_result = request_confirm_resume_profile_from_api(
                    parsed_profile=dict(profile_review.get("parsed_profile") or {}),
                    user_edits=user_edits,
                )
            except JobAgentError as exc:
                st.error(str(exc))
            else:
                st.session_state["confirmed_profile_result"] = confirmed_profile_result
                default_query = " ".join(
                    user_edits["target_roles"]
                    or _split_comma_list(
                        st.session_state.get("profile_flow_initial_target_roles", "")
                    )
                ).strip()
                if default_query:
                    st.session_state["profile_flow_search_query"] = default_query
                st.success("Profile confirmed.")
    else:
        st.info("先完成 01 Resume。")

    confirmed_profile_result = st.session_state.get("confirmed_profile_result")
    if confirmed_profile_result:
        st.json(confirmed_profile_result.get("confirmed_profile") or {})
        with st.expander("Confirmed profile result"):
            st.json(confirmed_profile_result)
        for warning in confirmed_profile_result.get("remaining_warnings") or []:
            st.warning(str(warning))

    st.markdown("### 03 Search Plan Preview")
    if confirmed_profile_result:
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
    else:
        st.info("先完成 02 Profile Review。")

    profile_search_plan = st.session_state.get("profile_search_plan")
    if profile_search_plan:
        col1, col2 = st.columns(2)
        col1.text_input(
            "original_query",
            value=str(profile_search_plan.get("original_query", "")),
            disabled=True,
            key="profile_flow_original_query_display",
        )
        col2.text_input(
            "effective_query",
            value=str(profile_search_plan.get("effective_query", "")),
            disabled=True,
            key="profile_flow_effective_query_display",
        )
        for warning in profile_search_plan.get("warnings") or []:
            st.warning(str(warning))
        with st.expander("Search plan JSON"):
            st.json(profile_search_plan)

    st.markdown("### 04 Brief From Search")
    if profile_search_plan:
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
    else:
        st.info("先完成 03 Search Plan Preview。")

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
        with st.expander("Brief JSON"):
            st.json(brief_result)

    st.markdown("### 05 Debug / Reset")
    if st.button(
        "Reset Profile Flow",
        key="profile_flow_reset",
        use_container_width=True,
    ):
        for key in [
            "profile_review",
            "profile_enrichment_result",
            "confirmed_profile_result",
            "profile_search_plan",
            "brief_result",
        ]:
            st.session_state.pop(key, None)
        st.success("Profile flow state cleared.")
        st.rerun()


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
            "无法连接 FastAPI 后端，请先启动 .venv\\Scripts\\python.exe -m uvicorn app.main:app --reload",
            unavailable_error_code,
        ) from exc

    return _load_json_payload(response_body)


def _load_json_payload(raw_text: str) -> dict[str, object]:
    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise JobAgentError("Job Brief API returned invalid JSON", "brief_api_invalid_json") from exc

    if not isinstance(payload, dict):
        raise JobAgentError("Job Brief API returned an invalid response object", "brief_api_invalid_json")
    return payload


def format_scoring_quality(value: str) -> str:
    return SCORING_QUALITY_LABELS.get(value, value)
