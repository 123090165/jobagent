from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class JobPosting(BaseModel):
    title: str | None = None
    company: str | None = None
    location: str | None = None
    source_url: str | None = None
    raw_jd: str


JDRequirementCategory = Literal[
    "skill",
    "experience",
    "education",
    "location",
    "employment_type",
    "work_authorization",
    "other",
]
JDRequirementNecessity = Literal["required", "preferred", "unknown"]


class JDRequirement(BaseModel):
    category: JDRequirementCategory
    name: str
    necessity: JDRequirementNecessity = "unknown"
    evidence_quote: str | None = None
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


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
    requirements: list[JDRequirement] = Field(default_factory=list)
