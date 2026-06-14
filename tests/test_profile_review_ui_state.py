from __future__ import annotations

from frontend.profile_review_state import (
    set_confirmed_profile_draft_payload,
    set_profile_draft_state,
)
from tests.test_profile_draft_service import _create


def test_profile_review_ui_state_tracks_draft_created() -> None:
    session_state: dict[str, object] = {}
    draft = _create("ai_agent_backend")

    set_profile_draft_state(session_state, draft)

    assert session_state["profile_draft"] == draft
    assert session_state["profile_draft_confirmed_payload"] is None


def test_profile_review_ui_state_tracks_draft_confirmed() -> None:
    session_state: dict[str, object] = {}
    draft = _create("weak_resume")
    set_profile_draft_state(session_state, draft)

    payload = {"status": "confirmed", "save_payload_ready": True}
    set_confirmed_profile_draft_payload(session_state, payload)

    assert session_state["profile_draft"] == draft
    assert session_state["profile_draft_confirmed_payload"] == payload
