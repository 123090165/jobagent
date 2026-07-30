"""回归验证浏览器助手会话的正常链路、失败边界和兼容契约。"""

from __future__ import annotations

from types import SimpleNamespace

from app.application.browser_helper_usecases import create_browser_helper_session


class AuthSessionRepositoryStub:
    """为当前测试场景提供 AuthSessionRepositoryStub 夹具或替身。"""
    def __init__(self) -> None:
        self.created: dict[str, object] | None = None

    def create(self, **kwargs) -> str:
        """提供 AuthSessionRepositoryStub.create 所需的测试行为。"""
        self.created = kwargs
        return "helper-session"


class ProfileSessionRepositoryStub:
    """为当前测试场景提供 ProfileSessionRepositoryStub 夹具或替身。"""
    def list_ready_by_user(self, user_id: str):
        """提供 ProfileSessionRepositoryStub.list_ready_by_user 所需的测试行为。"""
        assert user_id == "user-1"
        return [
            SimpleNamespace(session_id="session-secondary"),
            SimpleNamespace(session_id="session-default"),
        ]


class ResumeProfileRepositoryStub:
    """为当前测试场景提供 ResumeProfileRepositoryStub 夹具或替身。"""
    def list_by_user(self, user_id: str):
        """提供 ResumeProfileRepositoryStub.list_by_user 所需的测试行为。"""
        assert user_id == "user-1"
        return [
            SimpleNamespace(
                source_session_id="session-default",
                name="Backend Profile",
                is_default=True,
            ),
            SimpleNamespace(
                source_session_id="session-secondary",
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
    assert auth_sessions.created is not None
    assert auth_sessions.created["session_scope"] == "browser_helper"
