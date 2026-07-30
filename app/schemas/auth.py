"""定义认证账户与会话在 API、领域服务和 JSON 快照之间共用的 Pydantic 契约。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class UserAccount(BaseModel):
    user_id: str
    username: str
    display_name: str | None = None
    created_at: datetime
    updated_at: datetime
    disabled_at: datetime | None = None


class AuthRegisterRequest(BaseModel):
    """描述认证register的输入结构。"""
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=8, max_length=256)
    display_name: str | None = Field(default=None, max_length=120)

    @field_validator("username")
    @classmethod
    def _clean_username(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if not cleaned:
            raise ValueError("username cannot be empty")
        if any(char.isspace() for char in cleaned):
            raise ValueError("username cannot contain whitespace")
        return cleaned

    @field_validator("display_name")
    @classmethod
    def _clean_display_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class AuthLoginRequest(BaseModel):
    """描述认证login的输入结构。"""
    username: str
    password: str

    @field_validator("username")
    @classmethod
    def _clean_username(cls, value: str) -> str:
        return value.strip().lower()


class AuthTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    user: UserAccount


class AuthMeResponse(BaseModel):
    user: UserAccount
