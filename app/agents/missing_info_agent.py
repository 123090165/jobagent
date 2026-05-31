from __future__ import annotations

import re

from app.agents.types import AgentRunMetadata, AgentRunResult
from app.schemas.job import JobAnalysis
from app.schemas.match import MatchReport
from app.schemas.missing_info import MissingInfoQuestion, MissingInfoReport
from app.schemas.resume import ProjectExperience, ResumeProfile

SHORT_PROJECT_DESCRIPTION_LENGTH = 40
QUANTIFIED_PATTERN = re.compile(r"\d")
ENGINEERING_SIGNAL_GROUPS = {
    "deployment": ["deploy", "deployment", "上线", "发布", "docker", "k8s", "kubernetes", "ci/cd"],
    "testing": ["test", "testing", "pytest", "unit test", "集成测试", "自动化测试"],
    "database": ["database", "db", "sql", "mysql", "postgresql", "sqlite", "redis", "mongo"],
    "api": ["api", "rest", "fastapi", "flask", "接口", "服务", "backend"],
}


def generate_missing_info_report(
    resume_profile: ResumeProfile,
    job_analysis: JobAnalysis,
    match_report: MatchReport,
) -> MissingInfoReport:
    return run_missing_info_agent(
        resume_profile,
        job_analysis,
        match_report,
    ).output


def run_missing_info_agent(
    resume_profile: ResumeProfile,
    job_analysis: JobAnalysis,
    match_report: MatchReport,
) -> AgentRunResult[MissingInfoReport]:
    return AgentRunResult(
        output=_build_missing_info_report(
            resume_profile=resume_profile,
            job_analysis=job_analysis,
            match_report=match_report,
        ),
        metadata=AgentRunMetadata(
            agent_name="MissingInfoAgent",
            mode="mock",
            guardrails=[
                "Only detect missing evidence or unclear areas from the existing resume and JD.",
                "Do not invent experiences, metrics, projects, or technologies.",
                "Questions should help the user clarify or supplement real information only.",
            ],
        ),
    )


def _build_missing_info_report(
    *,
    resume_profile: ResumeProfile,
    job_analysis: JobAnalysis,
    match_report: MatchReport,
) -> MissingInfoReport:
    questions: list[MissingInfoQuestion] = []
    resume_skills = {skill.lower(): skill for skill in resume_profile.skills}
    project_evidence_text = "\n".join(
        _project_evidence_text(project) for project in resume_profile.projects
    ).lower()

    for skill in job_analysis.required_skills:
        normalized_skill = skill.lower()
        if normalized_skill not in resume_skills:
            questions.append(
                MissingInfoQuestion(
                    question=f"你是否真实使用过 {skill}？如果用过，请补充项目或经历中的具体使用场景。",
                    reason="JD 将该技能列为必备项，但简历技能栏里没有明确出现。",
                    related_skill=skill,
                    priority="high",
                )
            )
        if normalized_skill not in project_evidence_text:
            questions.append(
                MissingInfoQuestion(
                    question=f"如果 {skill} 是你真实掌握的能力，能否补充它在项目中的模块、职责或技术细节？",
                    reason="JD 关注该技能，但当前项目描述里缺少对应项目证据。",
                    related_skill=skill,
                    priority="high" if normalized_skill in resume_skills else "medium",
                )
            )

    for index, project in enumerate(resume_profile.projects, start=1):
        label = project.name or f"项目 {index}"
        if len(project.description.strip()) < SHORT_PROJECT_DESCRIPTION_LENGTH:
            questions.append(
                MissingInfoQuestion(
                    question=f"{label} 的描述偏短。你能补充业务背景、你的职责、技术方案和结果吗？",
                    reason="项目描述太短，难以支撑面试追问或 JD 对齐。",
                    priority="medium",
                )
            )
        if not _has_quantified_evidence(project):
            questions.append(
                MissingInfoQuestion(
                    question=f"{label} 有没有真实的量化结果，例如耗时、准确率、用户数、性能或交付规模？",
                    reason="当前项目缺少量化指标，容易被追问实际效果。",
                    priority="medium",
                )
            )

    if not _has_engineering_evidence(resume_profile, "deployment"):
        questions.append(
            MissingInfoQuestion(
                question="如果你做过部署、上线或交付，能否补充发布方式、环境或运维协作信息？",
                reason="当前简历里缺少部署或上线证据，工程闭环不够完整。",
                priority="medium",
            )
        )
    if not _has_engineering_evidence(resume_profile, "testing"):
        questions.append(
            MissingInfoQuestion(
                question="如果你写过测试，能否补充单元测试、接口测试或自动化测试的真实实践？",
                reason="当前简历里缺少测试证据，难以体现工程质量意识。",
                priority="medium",
            )
        )
    if not _has_engineering_evidence(resume_profile, "database"):
        questions.append(
            MissingInfoQuestion(
                question="如果你在项目里接触过数据库或缓存，能否补充表设计、查询、事务或存储选型？",
                reason="当前简历里缺少数据库或存储层证据。",
                priority="medium",
            )
        )
    if not _has_engineering_evidence(resume_profile, "api"):
        questions.append(
            MissingInfoQuestion(
                question="如果你设计或维护过 API，能否补充接口职责、输入输出或异常处理方式？",
                reason="当前简历里缺少 API/服务层工程证据。",
                priority="medium",
            )
        )

    summary = _build_summary(questions, match_report)
    return MissingInfoReport(questions=questions, summary=summary)


def _project_evidence_text(project: ProjectExperience) -> str:
    parts = [
        project.name or "",
        project.description,
        project.raw_text,
        *project.technologies,
        *project.highlights,
    ]
    return "\n".join(part for part in parts if part)


def _has_quantified_evidence(project: ProjectExperience) -> bool:
    text = "\n".join(
        [
            project.description,
            project.raw_text,
            *project.highlights,
        ]
    )
    return bool(QUANTIFIED_PATTERN.search(text))


def _has_engineering_evidence(resume_profile: ResumeProfile, group: str) -> bool:
    keywords = ENGINEERING_SIGNAL_GROUPS[group]
    corpus = "\n".join(
        [
            resume_profile.raw_text,
            *resume_profile.skills,
            *(project.raw_text for project in resume_profile.projects),
            *(project.description for project in resume_profile.projects),
            *(work.raw_text for work in resume_profile.work_experiences),
            *(work.description for work in resume_profile.work_experiences),
        ]
    ).lower()
    return any(keyword in corpus for keyword in keywords)


def _build_summary(questions: list[MissingInfoQuestion], match_report: MatchReport) -> str:
    if not questions:
        return (
            f"No obvious missing-information questions detected. "
            f"The current match score is {match_report.overall_score:.1f}."
        )

    high_priority_count = sum(1 for question in questions if question.priority == "high")
    return (
        f"Generated {len(questions)} clarification questions from the resume/JD gap. "
        f"{high_priority_count} question(s) are high priority. "
        f"Current match score: {match_report.overall_score:.1f}."
    )
