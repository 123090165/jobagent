from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SearchReadyProfile(BaseModel):
    summary: str
    target_directions: list[str] = Field(default_factory=list)
    core_skills: list[str] = Field(default_factory=list)
    auxiliary_skills: list[str] = Field(default_factory=list)
    search_keywords: list[str] = Field(default_factory=list)
    preferred_locations: list[str] = Field(default_factory=list)
    work_arrangements: list[str] = Field(default_factory=list)
    company_preferences: list[str] = Field(default_factory=list)
    profile_notes: list[str] = Field(default_factory=list)
    quality_warnings: list[str] = Field(default_factory=list)
    missing_info_questions: list[str] = Field(default_factory=list)
    source_profile_snapshot: dict[str, Any] | None = None
