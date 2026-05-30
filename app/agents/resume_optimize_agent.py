from __future__ import annotations

from app.schemas.job import JobAnalysis
from app.schemas.match import MatchReport, ResumeOptimizationResult
from app.schemas.resume import ResumeProfile
from app.agents.types import AgentRunMetadata, AgentRunResult


def optimize_resume(
    resume_text: str,
    resume_profile: ResumeProfile,
    job_analysis: JobAnalysis,
    match_report: MatchReport,
) -> ResumeOptimizationResult:
    """Generate resume optimization suggestions without inventing experience."""
    return run_resume_optimize_agent(
        resume_text,
        resume_profile,
        job_analysis,
        match_report,
    ).output


def run_resume_optimize_agent(
    resume_text: str,
    resume_profile: ResumeProfile,
    job_analysis: JobAnalysis,
    match_report: MatchReport,
) -> AgentRunResult[ResumeOptimizationResult]:
    """Generate resume optimization suggestions with safety metadata."""
    from app.services.mock_pipeline import mock_resume_optimization

    return AgentRunResult(
        output=mock_resume_optimization(
            resume_text.strip(),
            resume_profile,
            job_analysis,
            match_report,
        ),
        metadata=AgentRunMetadata(
            agent_name="ResumeOptimizeAgent",
            mode="mock",
            guardrails=[
                "不编造经历、公司、项目、数据或技术栈",
                "需要量化但缺少数据时只提示补充",
                "不覆盖原始简历文本",
            ],
        ),
    )
