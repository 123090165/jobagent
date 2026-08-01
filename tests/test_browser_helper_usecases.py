from __future__ import annotations

from types import SimpleNamespace

from app.application.browser_helper_usecases import create_browser_helper_session


class AuthSessionRepositoryStub:
    def __init__(self) -> None:
        self.created: dict[str, object] | None = None

    def create(self, **kwargs) -> str:
        self.created = kwargs
        return "helper-session"


class ProfileSessionRepositoryStub:
    def list_ready_by_user(self, user_id: str):
        assert user_id == "user-1"
        return [
            SimpleNamespace(session_id="session-secondary"),
            SimpleNamespace(session_id="session-default"),
        ]


class ResumeProfileRepositoryStub:
    def list_by_user(self, user_id: str):
        assert user_id == "user-1"
        return [
            SimpleNamespace(
                source_session_id="session-default",
                resume_profile_id="profile-default",
                name="Backend Profile",
                is_default=True,
            ),
            SimpleNamespace(
                source_session_id="session-secondary",
                resume_profile_id="profile-secondary",
                name="Data Profile",
                is_default=False,
            ),
        ]


def test_browser_helper_session_uses_profile_names_and_default_order() -> None:
    auth_sessions = AuthSessionRepositoryStub()

    result = create_browser_helper_session(
        user_id="user-1",
        user_agent="test",
        sessions=auth_sessions,
        profile_sessions=ProfileSessionRepositoryStub(),
        resume_profiles=ResumeProfileRepositoryStub(),
    )

    assert [(item.session_id, item.label, item.is_default) for item in result.profile_sessions] == [
        ("session-default", "Backend Profile", True),
        ("session-secondary", "Data Profile", False),
    ]
    assert [item.resume_profile_id for item in result.profile_sessions] == [
        "profile-default",
        "profile-secondary",
    ]
    assert auth_sessions.created is not None
    assert auth_sessions.created["session_scope"] == "browser_helper"
