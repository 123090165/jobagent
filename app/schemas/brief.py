from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.match import MatchReport
from app.schemas.search import SearchResultItem


class JobRecommendationItem(BaseModel):
    rank: int
    job: SearchResultItem
    match_report: MatchReport
    fit_score: float
    advice: str
    scoring_quality: str
    fit_reasons: list[str] = Field(default_factory=list)
    risk_points: list[str] = Field(default_factory=list)


class JobBriefReport(BaseModel):
    query: str
    provider: str
    total_jobs: int
    recommended_jobs: list[JobRecommendationItem] = Field(default_factory=list)
    top_skills: list[str] = Field(default_factory=list)
    market_summary: str
    application_strategy: list[str] = Field(default_factory=list)
    scoring_quality_summary: str | None = None
