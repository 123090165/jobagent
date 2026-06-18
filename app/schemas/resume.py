from __future__ import annotations

from pydantic import BaseModel, Field


class EducationItem(BaseModel):
    school: str | None = None
    degree: str | None = None
    major: str | None = None
    raw_text: str


class WorkExperience(BaseModel):
    company: str | None = None
    role: str | None = None
    description: str
    technologies: list[str] = Field(default_factory=list)
    raw_text: str


class ProjectExperience(BaseModel):
    name: str | None = None
    description: str
    technologies: list[str] = Field(default_factory=list)
    highlights: list[str] = Field(default_factory=list)
    raw_text: str


class ResumeProfile(BaseModel):
    raw_text: str
    name: str | None = None
    target_roles: list[str] = Field(default_factory=list)
    education: list[EducationItem] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    projects: list[ProjectExperience] = Field(default_factory=list)
    work_experiences: list[WorkExperience] = Field(default_factory=list)
    certificates: list[str] = Field(default_factory=list)
    highlights: list[str] = Field(default_factory=list)
    missing_info: list[str] = Field(default_factory=list)
