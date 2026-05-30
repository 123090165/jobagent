from __future__ import annotations

from app.schemas.job import JobAnalysis
from app.schemas.match import MatchReport
from app.schemas.resume import ResumeProfile
from app.agents.types import AgentRunMetadata, AgentRunResult


def analyze_match(
    resume_profile: ResumeProfile,
    job_analysis: JobAnalysis,
) -> MatchReport:
    """Compare a structured resume and JD analysis."""
    return run_match_agent(resume_profile, job_analysis).output


def run_match_agent(
    resume_profile: ResumeProfile,
    job_analysis: JobAnalysis,
) -> AgentRunResult[MatchReport]:
    """Compare a structured resume and JD analysis with metadata."""
    from app.services.mock_pipeline import mock_match_analysis

    return AgentRunResult(
        output=mock_match_analysis(resume_profile, job_analysis),
        metadata=AgentRunMetadata(
            agent_name="MatchAgent",
            mode="mock",
            guardrails=[
                "匹配分必须有证据",
                "缺失项必须来自 JD 和简历差距",
            ],
        ),
    )
