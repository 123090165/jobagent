from __future__ import annotations

from pydantic import BaseModel, Field


class JobPosting(BaseModel):
    title: str | None = None
    company: str | None = None
    location: str | None = None
    source_url: str | None = None
    raw_jd: str


class JobAnalysis(BaseModel):
    raw_jd: str
    job_title: str | None = None
    company: str | None = None
    location: str | None = None
    responsibilities: list[str] = Field(default_factory=list)
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    experience_requirements: list[str] = Field(default_factory=list)
    education_requirements: list[str] = Field(default_factory=list)
    soft_skills: list[str] = Field(default_factory=list)
    implicit_requirements: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    job_category: str | None = None
