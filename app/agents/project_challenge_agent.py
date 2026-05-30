from __future__ import annotations

from app.schemas.job import JobAnalysis
from app.schemas.match import ProjectChallengeReport
from app.schemas.resume import ResumeProfile
from app.agents.types import AgentRunMetadata, AgentRunResult


def generate_project_challenges(
    resume_profile: ResumeProfile,
    job_analysis: JobAnalysis,
) -> ProjectChallengeReport:
    """Generate interview challenge questions from resume and JD context."""
    return run_project_challenge_agent(resume_profile, job_analysis).output


def run_project_challenge_agent(
    resume_profile: ResumeProfile,
    job_analysis: JobAnalysis,
) -> AgentRunResult[ProjectChallengeReport]:
    """Generate interview challenge questions with metadata."""
    from app.services.mock_pipeline import mock_project_challenge

    return AgentRunResult(
        output=mock_project_challenge(resume_profile, job_analysis),
        metadata=AgentRunMetadata(
            agent_name="ProjectInterviewAgent",
            mode="mock",
            guardrails=[
                "追问必须基于简历项目和目标 JD",
                "暴露短板时给出可执行补强方向",
            ],
        ),
    )
