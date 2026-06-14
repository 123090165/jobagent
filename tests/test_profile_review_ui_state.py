from __future__ import annotations

from types import SimpleNamespace

import frontend.profile_review_flow as profile_review_flow
from frontend.profile_review_state import (
    set_confirmed_profile_draft_payload,
    set_profile_draft_state,
)
from tests.test_profile_draft_service import _create


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
    )

    assert "profile_flow_profile_draft" in fake_st.session_state
    assert fake_st.session_state["profile_flow_profile_draft"].search_ready_profile.target_directions
    assert fake_st.session_state["profile_draft_confirmed_payload"] is None
    assert any(item.startswith("success:") for item in events)
