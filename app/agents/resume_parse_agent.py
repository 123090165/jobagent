"""把原始简历文本交给确定性解析器，并返回统一的 Agent 执行元数据。"""

from __future__ import annotations

from app.schemas.resume import ResumeProfile
from app.agents.types import AgentRunMetadata, AgentRunResult


def parse_resume(resume_text: str) -> ResumeProfile:
    """Parse resume text into the shared ResumeProfile schema."""
    return run_resume_parse_agent(resume_text).output


def run_resume_parse_agent(resume_text: str) -> AgentRunResult[ResumeProfile]:
    """Parse resume text and return execution metadata."""
    normalized_resume = resume_text.strip()
    if not normalized_resume:
        raise ValueError("resume_text cannot be empty")

    from app.services.mock_pipeline import mock_resume_parse

    return AgentRunResult(
        output=mock_resume_parse(normalized_resume),
        metadata=AgentRunMetadata(
            agent_name="ResumeParseAgent",
            mode="mock",
            guardrails=[
                "保留原始简历文本",
                "信息不足时使用 missing_info，不编造经历",
            ],
        ),
    )
