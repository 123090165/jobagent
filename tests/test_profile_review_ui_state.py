from __future__ import annotations

from types import SimpleNamespace

import frontend.profile_review_flow as profile_review_flow
from app.services.resume_file_service import ResumeFileParseError
from frontend.profile_review_state import (
    get_profile_flow_step,
    get_selected_provider,
    set_profile_flow_step,
    set_selected_provider,
    set_confirmed_profile_draft_payload,
    set_profile_draft_state,
)
from tests.test_profile_draft_service import _create


class _FakeExpander:
    def __enter__(self) -> "_FakeExpander":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


def test_profile_review_ui_state_tracks_draft_created() -> None:
    session_state: dict[str, object] = {}
    draft = _create("ai_agent_backend")

    set_profile_draft_state(session_state, draft)

    assert session_state["profile_flow_profile_draft"] == draft
    assert session_state["profile_draft"] == draft
    assert session_state["profile_draft_confirmed_payload"] is None


def test_profile_review_ui_state_tracks_draft_confirmed() -> None:
    session_state: dict[str, object] = {}
    draft = _create("weak_resume")
    set_profile_draft_state(session_state, draft)

    payload = {"status": "confirmed", "save_payload_ready": True}
    set_confirmed_profile_draft_payload(session_state, payload)

    assert session_state["profile_flow_profile_draft"] == draft
    assert session_state["profile_draft"] == draft
    assert session_state["profile_draft_confirmed_payload"] == payload


def test_current_profile_draft_reads_main_session_key(monkeypatch) -> None:
    draft = _create("ai_agent_backend")
    fake_st = SimpleNamespace(session_state={"profile_flow_profile_draft": draft})
    monkeypatch.setattr(profile_review_flow, "st", fake_st)

    assert profile_review_flow._current_profile_draft() == draft


def test_current_profile_draft_falls_back_to_compat_alias(monkeypatch) -> None:
    draft = _create("weak_resume")
    fake_st = SimpleNamespace(session_state={"profile_draft": draft})
    monkeypatch.setattr(profile_review_flow, "st", fake_st)

    assert profile_review_flow._current_profile_draft() == draft


def test_parse_resume_profile_stores_draft_under_main_session_key(monkeypatch) -> None:
    review = {
        "parsed_profile": _create("ai_agent_backend").source_profile_snapshot,
        "quality_warnings": [],
        "missing_info_questions": [],
        "confidence_label": "strong",
    }
    events: list[str] = []
    fake_st = SimpleNamespace(
        session_state={},
        error=lambda message: events.append(f"error:{message}"),
        success=lambda message: events.append(f"success:{message}"),
    )
    monkeypatch.setattr(profile_review_flow, "st", fake_st)
    monkeypatch.setattr(
        profile_review_flow,
        "request_resume_profile_review_from_api",
        lambda **kwargs: review,
    )

    profile_review_flow._parse_resume_profile(
        resume_text="Skills: Python",
        target_roles=["AI Agent Engineer"],
        llm_provider="ollama",
    )

    assert fake_st.session_state["profile_flow_step"] == "parsed_review"
    assert "profile_flow_baseline_review" in fake_st.session_state
    assert fake_st.session_state["profile_draft_confirmed_payload"] is None
    assert any(item.startswith("success:") for item in events)


def test_parse_resume_profile_requires_non_empty_text(monkeypatch) -> None:
    events: list[str] = []
    fake_st = SimpleNamespace(
        session_state={},
        warning=lambda message: events.append(f"warning:{message}"),
    )
    monkeypatch.setattr(profile_review_flow, "st", fake_st)

    profile_review_flow._parse_resume_profile(
        resume_text="   ",
        target_roles=[],
        llm_provider="ollama",
    )

    assert fake_st.session_state["profile_flow_resume_input_source"] == "empty"
    assert events == ["warning:Please upload or paste your resume before starting profile setup."]


def test_profile_flow_step_defaults_to_resume_input() -> None:
    assert get_profile_flow_step({}) == "resume_input"


def test_ensure_initial_state_defaults_resume_input_source_to_empty(monkeypatch) -> None:
    fake_st = SimpleNamespace(session_state={})
    monkeypatch.setattr(profile_review_flow, "st", fake_st)

    profile_review_flow._ensure_initial_state("Sample resume")

    assert fake_st.session_state["profile_flow_resume_text"] == ""
    assert fake_st.session_state["profile_flow_resume_input_source"] == "empty"
    assert fake_st.session_state["profile_flow_sample_resume"] == "Sample resume"


def test_build_sample_resume_state_loads_sample_resume() -> None:
    sample_state = profile_review_flow.build_sample_resume_state("Sample resume text")

    assert sample_state["profile_flow_resume_text"] == "Sample resume text"
    assert sample_state["profile_flow_resume_input_source"] == "sample"
    assert sample_state["profile_flow_upload_error"] is None


def test_profile_flow_step_transitions() -> None:
    session_state: dict[str, object] = {}
    set_profile_flow_step(session_state, "parsed_review")
    assert get_profile_flow_step(session_state) == "parsed_review"
    set_profile_flow_step(session_state, "profile_draft")
    assert get_profile_flow_step(session_state) == "profile_draft"
    set_profile_flow_step(session_state, "profile_saved")
    assert get_profile_flow_step(session_state) == "profile_saved"


def test_selected_provider_defaults_to_ollama() -> None:
    assert get_selected_provider({}) == "ollama"


def test_selected_provider_can_switch_to_deepseek() -> None:
    session_state: dict[str, object] = {}
    set_selected_provider(session_state, "deepseek", {"configured": False})

    assert get_selected_provider(session_state) == "deepseek"
    assert session_state["profile_flow_selected_provider_metadata"] == {"configured": False}


def test_generate_profile_draft_moves_step_to_profile_draft(monkeypatch) -> None:
    baseline_review = {
        "parsed_profile": _create("ai_agent_backend").source_profile_snapshot,
        "quality_warnings": [],
        "missing_info_questions": [],
    }
    fake_st = SimpleNamespace(
        session_state={
            "profile_flow_initial_target_roles": "AI Agent Engineer",
            "profile_flow_selected_provider": "ollama",
        },
        success=lambda message: None,
        rerun=lambda: None,
    )
    monkeypatch.setattr(profile_review_flow, "st", fake_st)

    profile_review_flow._generate_profile_draft(baseline_review)

    assert fake_st.session_state["profile_flow_step"] == "profile_draft"
    assert fake_st.session_state["profile_flow_profile_draft"].llm_provider == "ollama"


def test_build_resume_upload_state_accepts_txt_file() -> None:
    upload_state = profile_review_flow.build_resume_upload_state(
        "resume.txt",
        b"Skills: Python\nProjects: JobAgent",
    )

    assert upload_state["profile_flow_resume_text"] == "Skills: Python\nProjects: JobAgent"
    assert upload_state["profile_flow_uploaded_filename"] == "resume.txt"
    assert upload_state["profile_flow_uploaded_file_type"] == "txt"
    assert upload_state["profile_flow_uploaded_text_length"] == len(
        "Skills: Python\nProjects: JobAgent"
    )
    assert upload_state["profile_flow_resume_input_source"] == "upload"


def test_build_resume_upload_state_accepts_md_file() -> None:
    upload_state = profile_review_flow.build_resume_upload_state(
        "resume.md",
        b"# Resume\n\nSkills: Python",
    )

    assert upload_state["profile_flow_resume_text"] == "# Resume\n\nSkills: Python"
    assert upload_state["profile_flow_uploaded_file_type"] == "md"
    assert upload_state["profile_flow_resume_input_source"] == "upload"


def test_build_resume_upload_state_rejects_empty_file() -> None:
    try:
        profile_review_flow.build_resume_upload_state("resume.txt", b"")
    except ResumeFileParseError as exc:
        assert exc.error_code == "resume_file_empty"
    else:
        raise AssertionError("expected ResumeFileParseError for empty file")


def test_build_resume_upload_state_rejects_non_utf8_file() -> None:
    try:
        profile_review_flow.build_resume_upload_state("resume.txt", b"\xff\xfe\x00\x00")
    except ResumeFileParseError as exc:
        assert exc.error_code == "resume_file_decode_failed"
    else:
        raise AssertionError("expected ResumeFileParseError for decode failure")


def test_build_resume_upload_state_rejects_unsupported_file_type() -> None:
    try:
        profile_review_flow.build_resume_upload_state("resume.pdf", b"fake pdf")
    except ResumeFileParseError as exc:
        assert exc.error_code == "resume_file_type_unsupported"
    else:
        raise AssertionError("expected ResumeFileParseError for unsupported file type")


def test_apply_resume_upload_failure_does_not_override_existing_text(monkeypatch) -> None:
    messages: list[str] = []
    fake_st = SimpleNamespace(
        session_state={"profile_flow_resume_text": "Existing resume"},
        error=lambda message: messages.append(str(message)),
        success=lambda message: messages.append(str(message)),
    )
    monkeypatch.setattr(profile_review_flow, "st", fake_st)

    profile_review_flow._apply_resume_upload("resume.txt", b"")

    assert fake_st.session_state["profile_flow_resume_text"] == "Existing resume"
    assert fake_st.session_state["profile_flow_upload_error"] == "resume file cannot be empty"
    assert fake_st.session_state["profile_flow_upload_fingerprint"] is None
    assert messages == []


def test_update_resume_input_source_marks_upload_edited(monkeypatch) -> None:
    fake_st = SimpleNamespace(session_state={"profile_flow_resume_input_source": "upload"})
    monkeypatch.setattr(profile_review_flow, "st", fake_st)

    profile_review_flow._update_resume_input_source("Uploaded text", "Uploaded text plus edits")

    assert fake_st.session_state["profile_flow_resume_input_source"] == "upload_edited"


def test_update_resume_input_source_marks_paste(monkeypatch) -> None:
    fake_st = SimpleNamespace(session_state={"profile_flow_resume_input_source": "empty"})
    monkeypatch.setattr(profile_review_flow, "st", fake_st)

    profile_review_flow._update_resume_input_source("", "Pasted resume text")

    assert fake_st.session_state["profile_flow_resume_input_source"] == "paste"


def test_save_profile_draft_moves_step_to_profile_saved(monkeypatch) -> None:
    draft = _create("weak_resume")
    messages: list[str] = []
    fake_st = SimpleNamespace(
        session_state={"profile_flow_profile_draft": draft},
        success=lambda message: messages.append(message),
    )
    monkeypatch.setattr(profile_review_flow, "st", fake_st)

    profile_review_flow._save_profile_draft(draft)

    assert fake_st.session_state["profile_flow_step"] == "profile_saved"
    assert "profile_draft_confirmed_payload" in fake_st.session_state
    assert (
        fake_st.session_state["profile_draft_confirmed_payload"]["llm_provider_metadata"]["provider"]
        == "ollama"
    )
    assert any("saved" in message.lower() for message in messages)


def test_render_safe_debug_json_handles_none_without_st_json(monkeypatch) -> None:
    captions: list[str] = []
    json_calls: list[object] = []
    code_calls: list[str] = []
    fake_st = SimpleNamespace(
        caption=lambda message: captions.append(message),
        json=lambda payload: json_calls.append(payload),
        code=lambda payload: code_calls.append(payload),
    )
    monkeypatch.setattr(profile_review_flow, "st", fake_st)

    profile_review_flow._render_safe_debug_json("Profile draft", None)

    assert captions == ["Profile draft", "Not available yet."]
    assert json_calls == []
    assert code_calls == []


def test_render_safe_debug_json_serializes_profile_draft(monkeypatch) -> None:
    draft = _create("ai_agent_backend")
    json_calls: list[object] = []
    fake_st = SimpleNamespace(
        caption=lambda message: None,
        json=lambda payload: json_calls.append(payload),
        code=lambda payload: None,
    )
    monkeypatch.setattr(profile_review_flow, "st", fake_st)

    profile_review_flow._render_safe_debug_json("Profile draft", draft)

    assert json_calls == [draft.model_dump(mode="json")]


def test_render_raw_debug_handles_empty_payloads(monkeypatch) -> None:
    json_calls: list[object] = []
    code_calls: list[str] = []
    captions: list[str] = []
    fake_st = SimpleNamespace(
        session_state={},
        expander=lambda label: _FakeExpander(),
        caption=lambda message: captions.append(message),
        json=lambda payload: json_calls.append(payload),
        code=lambda payload: code_calls.append(payload),
    )
    monkeypatch.setattr(profile_review_flow, "st", fake_st)

    profile_review_flow._render_raw_debug()

    assert captions == [
        "Baseline review",
        "Not available yet.",
        "Profile draft",
        "Not available yet.",
        "Confirmed payload",
        "Not available yet.",
    ]
    assert json_calls == []
    assert code_calls == []
