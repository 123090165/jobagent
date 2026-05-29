from __future__ import annotations

import re

from app.schemas.job import JobAnalysis
from app.schemas.match import (
    ChallengeQuestion,
    MatchReport,
    ProjectChallengeReport,
    ResumeOptimizationResult,
    RewriteSuggestion,
)
from app.schemas.report import FinalReport
from app.schemas.resume import EducationItem, ProjectExperience, ResumeProfile, WorkExperience
from app.services.report_service import generate_markdown_report


KNOWN_SKILLS = [
    "Python",
    "FastAPI",
    "Streamlit",
    "Pydantic",
    "LangGraph",
    "LangChain",
    "OpenAI",
    "LLM",
    "RAG",
    "MCP",
    "SQL",
    "SQLite",
    "PostgreSQL",
    "Redis",
    "Docker",
    "Git",
    "REST API",
    "pytest",
    "React",
    "TypeScript",
    "JavaScript",
    "HTML",
    "CSS",
    "Pandas",
    "NumPy",
    "scikit-learn",
    "机器学习",
    "数据分析",
]


def _clean_lines(text: str) -> list[str]:
    return [line.strip(" -•\t") for line in text.splitlines() if line.strip()]


def _extract_skills(text: str) -> list[str]:
    lowered = text.lower()
    found: list[str] = []
    for skill in KNOWN_SKILLS:
        if skill.lower() in lowered and skill not in found:
            found.append(skill)
    return found


def _split_clauses(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"[，,。；;：:]", text) if part.strip()]


def _extract_preferred_skills(lines: list[str]) -> list[str]:
    skills: list[str] = []
    for line in lines:
        if "加分" in line:
            skills.extend(_extract_skills(line.split("加分", 1)[1]))
            continue
        for clause in _split_clauses(line):
            if "优先" in clause:
                skills.extend(_extract_skills(clause))
    return _dedupe(skills)


def _extract_required_skills(lines: list[str]) -> list[str]:
    trigger_words = ["要求", "必须", "熟悉", "掌握", "精通", "职责", "负责"]
    preferred_words = ["优先", "加分"]
    skills: list[str] = []
    for line in lines:
        if not any(word in line for word in trigger_words):
            continue
        segment = line.split("要求", 1)[1] if "要求" in line else line
        required_clauses = [
            clause for clause in _split_clauses(segment) if not any(word in clause for word in preferred_words)
        ]
        skills.extend(_extract_skills("，".join(required_clauses)))
    return _dedupe(skills)


def _first_reasonable_title(lines: list[str], fallback: str) -> str:
    for line in lines:
        if len(line) <= 60 and any(word in line for word in ["工程师", "开发", "实习", "Agent", "LLM", "算法"]):
            return line
    return fallback


def mock_resume_parse(resume_text: str) -> ResumeProfile:
    """Parse a resume with lightweight heuristics for the v0.1 mock pipeline."""
    lines = _clean_lines(resume_text)
    skills = _extract_skills(resume_text)

    education_lines = [
        line
        for line in lines
        if any(word in line for word in ["大学", "学院", "本科", "硕士", "博士", "计算机"])
    ][:3]
    education = [EducationItem(raw_text=line) for line in education_lines]

    work_lines = [line for line in lines if any(word in line for word in ["实习", "工作", "公司", "负责"])]
    work_experiences = [
        WorkExperience(description=line, raw_text=line, technologies=_extract_skills(line))
        for line in work_lines[:3]
    ]

    project_lines = [
        line
        for line in lines
        if any(word in line for word in ["项目", "系统", "平台", "应用", "Agent", "Demo"])
    ]
    if not project_lines and resume_text.strip():
        project_lines = [resume_text.strip()[:240]]

    projects = [
        ProjectExperience(
            name=f"项目 {index + 1}",
            description=line,
            raw_text=line,
            technologies=_extract_skills(line),
            highlights=[line] if any(word in line for word in ["实现", "优化", "提升", "完成"]) else [],
        )
        for index, line in enumerate(project_lines[:3])
    ]

    certificates = [
        line
        for line in lines
        if any(word in line for word in ["证书", "CET", "英语", "软考", "竞赛"])
    ][:5]

    highlights = [
        line
        for line in lines
        if any(word in line for word in ["优化", "提升", "负责", "独立", "落地", "上线"])
    ][:5]

    missing_info: list[str] = []
    if not skills:
        missing_info.append("技能栈不够明确")
    if not projects:
        missing_info.append("项目经历不够明确")
    if not highlights:
        missing_info.append("缺少结果或量化亮点")

    name = lines[0] if lines and len(lines[0]) <= 20 and not _extract_skills(lines[0]) else None

    return ResumeProfile(
        raw_text=resume_text,
        name=name,
        education=education,
        skills=skills,
        projects=projects,
        work_experiences=work_experiences,
        certificates=certificates,
        highlights=highlights,
        missing_info=missing_info,
    )


def mock_jd_analysis(jd_text: str) -> JobAnalysis:
    """Analyze a JD with lightweight heuristics for the v0.1 mock pipeline."""
    lines = _clean_lines(jd_text)
    all_skills = _extract_skills(jd_text)

    preferred_skills = _extract_preferred_skills(lines)
    required_skills = _extract_required_skills(lines)
    if not required_skills:
        required_skills = [skill for skill in all_skills if skill not in preferred_skills]

    responsibilities = [
        line
        for line in lines
        if any(word in line for word in ["负责", "参与", "设计", "开发", "构建", "维护"])
    ][:6]
    if not responsibilities and lines:
        responsibilities = lines[:3]

    experience_requirements = [
        line for line in lines if any(word in line for word in ["经验", "年", "实习"])
    ][:4]
    education_requirements = [
        line for line in lines if any(word in line for word in ["本科", "硕士", "学历", "计算机"])
    ][:3]
    soft_skills = [
        line
        for line in lines
        if any(word in line for word in ["沟通", "协作", "学习", "主动", "责任心"])
    ][:3]

    job_category = "AI / LLM 应用开发" if any(skill in all_skills for skill in ["LLM", "RAG", "OpenAI", "LangGraph"]) else "软件开发"

    return JobAnalysis(
        raw_jd=jd_text,
        job_title=_first_reasonable_title(lines, "目标岗位"),
        responsibilities=responsibilities,
        required_skills=required_skills,
        preferred_skills=preferred_skills,
        experience_requirements=experience_requirements,
        education_requirements=education_requirements,
        soft_skills=soft_skills,
        implicit_requirements=["需要能把项目讲清楚并经得住技术追问"],
        keywords=all_skills,
        job_category=job_category,
    )


def _dedupe(items) -> list[str]:
    result: list[str] = []
    for item in items:
        if item and item not in result:
            result.append(item)
    return result


def _score_ratio(matched: int, total: int, fallback: float = 0.0) -> float:
    if total == 0:
        return fallback
    return matched / total


def mock_match_analysis(resume_profile: ResumeProfile, job_analysis: JobAnalysis) -> MatchReport:
    resume_skills = {skill.lower() for skill in resume_profile.skills}
    required_skills = job_analysis.required_skills or job_analysis.keywords
    matched_skills = [skill for skill in required_skills if skill.lower() in resume_skills]
    missing_skills = [skill for skill in required_skills if skill.lower() not in resume_skills]

    skill_ratio = _score_ratio(len(matched_skills), len(required_skills), fallback=0.45)
    project_overlap = any(
        skill.lower() in resume_skills
        for project in resume_profile.projects
        for skill in project.technologies
    )
    project_score = 72.0 if resume_profile.projects and project_overlap else 58.0 if resume_profile.projects else 35.0
    experience_score = 68.0 if resume_profile.work_experiences else 48.0
    skill_score = round(skill_ratio * 100, 1)
    keyword_coverage = round(_score_ratio(len(matched_skills), len(job_analysis.keywords), fallback=0.0) * 100, 1)
    overall_score = round(skill_score * 0.5 + project_score * 0.3 + experience_score * 0.2, 1)

    matched_points = [f"简历中出现了 JD 关注的技能：{skill}" for skill in matched_skills]
    if resume_profile.projects:
        matched_points.append("简历中包含项目经历，可以用于支撑岗位相关能力。")

    risks: list[str] = []
    if missing_skills:
        risks.append("JD 中的部分关键技能未在简历中明确出现。")
    if "缺少结果或量化亮点" in resume_profile.missing_info:
        risks.append("项目结果缺少量化指标，面试时容易被追问贡献和效果。")
    if not resume_profile.work_experiences:
        risks.append("工作或实习经历不明显，需要用项目细节补足可信度。")

    if overall_score >= 75:
        recommendation = "建议投递，同时针对缺失点定制简历。"
    elif overall_score >= 55:
        recommendation = "可以投递，但建议先补强简历关键词和项目证据。"
    else:
        recommendation = "暂不建议直接投递，先补齐关键技能和项目表达。"

    return MatchReport(
        overall_score=overall_score,
        skill_score=skill_score,
        project_score=project_score,
        experience_score=experience_score,
        keyword_coverage=keyword_coverage,
        matched_points=matched_points,
        missing_points=[f"需要补强或明确展示：{skill}" for skill in missing_skills],
        risks=risks,
        evidence=[
            f"简历识别技能：{', '.join(resume_profile.skills) if resume_profile.skills else '暂无'}",
            f"JD 关键词：{', '.join(job_analysis.keywords) if job_analysis.keywords else '暂无'}",
        ],
        apply_recommendation=recommendation,
        short_term_suggestions=[
            "把 JD 中已掌握的技能前置到技能栏和项目 bullet 中。",
            "为最相关项目补充背景、个人职责、技术方案和结果。",
            "准备项目追问答案，尤其是技术选型和效果评估。",
        ],
        long_term_suggestions=[
            "围绕缺失技能补一个小 demo 或实验记录。",
            "积累可展示的测试、部署、性能或用户反馈证据。",
        ],
    )


def mock_resume_optimization(
    resume_text: str,
    resume_profile: ResumeProfile,
    job_analysis: JobAnalysis,
    match_report: MatchReport,
) -> ResumeOptimizationResult:
    missing_keywords = [
        item.replace("需要补强或明确展示：", "") for item in match_report.missing_points
    ]
    first_project = resume_profile.projects[0].description if resume_profile.projects else resume_text[:120]

    return ResumeOptimizationResult(
        overall_issues=[
            "当前简历需要更明确地对齐目标 JD 的必备技能。",
            "项目经历应补充问题背景、技术方案、个人贡献和结果指标。",
        ],
        keywords_to_add=missing_keywords,
        skills_section_suggestions=[
            "把与 JD 直接相关的技能放在技能栏前半部分。",
            "技能不要只罗列名词，项目中也要出现对应使用场景。",
        ],
        project_rewrite_suggestions=[
            RewriteSuggestion(
                original=first_project,
                suggestion="按“业务问题 -> 技术方案 -> 个人职责 -> 结果证据”的顺序重写项目 bullet。",
                reason="面试官更关心你如何解决问题，而不是只看到技术名词。",
            )
        ],
        jd_targeted_bullets=[
            "基于已有项目，补充与目标 JD 技能相关的模块、接口、数据流或评估方式。",
            "如果确实使用过相关技术，写清楚使用位置、解决的问题和结果；没有使用过则不要硬写。",
        ],
        do_not_exaggerate=[
            "不要编造没有做过的公司、项目、数据指标或技术栈。",
            "没有量化数据时，只写“建议补充指标”，不要直接生成虚假百分比。",
        ],
        missing_info_needed=resume_profile.missing_info,
    )


def mock_project_challenge(
    resume_profile: ResumeProfile,
    job_analysis: JobAnalysis,
) -> ProjectChallengeReport:
    project_name = resume_profile.projects[0].name if resume_profile.projects else "你的核心项目"
    target_skills = job_analysis.required_skills[:3] or job_analysis.keywords[:3] or ["岗位核心技能"]

    return ProjectChallengeReport(
        basic_questions=[
            ChallengeQuestion(
                question=f"{project_name} 解决的真实问题是什么？为什么需要做这个项目？",
                evaluates="项目背景是否真实，是否能讲清楚需求来源。",
                answer_framework="先讲使用场景，再讲痛点，最后讲你的目标和边界。",
            ),
            ChallengeQuestion(
                question="这个项目中你个人负责了哪一部分？哪些不是你做的？",
                evaluates="个人贡献边界是否清楚，是否存在夸大风险。",
                answer_framework="按模块列出个人负责内容，并诚实说明协作或参考部分。",
            ),
        ],
        technical_deep_dive_questions=[
            ChallengeQuestion(
                question=f"你在项目中如何体现 {skill}？具体用在什么模块？",
                evaluates="技能是否只是写在简历上，还是有真实使用场景。",
                answer_framework="说明使用位置、输入输出、关键实现和遇到的问题。",
            )
            for skill in target_skills
        ],
        architecture_questions=[
            ChallengeQuestion(
                question="如果这个项目用户量增加 10 倍，你会先改哪一层？",
                evaluates="是否理解架构瓶颈和扩展优先级。",
                answer_framework="从数据流、存储、接口、异步任务和监控几个角度分析。",
            )
        ],
        tradeoff_questions=[
            ChallengeQuestion(
                question="当时为什么选择这种技术方案？有没有更简单或更稳定的替代方案？",
                evaluates="是否具备技术选型和取舍意识。",
                answer_framework="讲清楚约束、备选方案、选择理由和后续改进。",
            )
        ],
        interviewer_concerns=[
            "项目是否只是 demo，缺少真实输入输出和测试。",
            "是否只调用模型，没有自己的业务拆解和工程设计。",
            "简历中的技能是否都有项目证据支撑。",
        ],
        improvement_suggestions=[
            "为项目补充一张数据流图或模块图。",
            "准备一组真实样例输入和输出报告。",
            "补充测试、错误处理和边界情况说明。",
        ],
    )


def run_mock_pipeline(resume_text: str, jd_text: str, *, use_llm_jd: bool = False) -> FinalReport:
    """Run the full v0.1 mock analysis flow."""
    normalized_resume = resume_text.strip()
    normalized_jd = jd_text.strip()

    if not normalized_resume:
        raise ValueError("resume_text cannot be empty")
    if not normalized_jd:
        raise ValueError("jd_text cannot be empty")

    resume_profile = mock_resume_parse(normalized_resume)
    if use_llm_jd:
        from app.agents.jd_analysis_agent import analyze_jd

        job_analysis = analyze_jd(normalized_jd, use_llm=True)
    else:
        job_analysis = mock_jd_analysis(normalized_jd)
    match_report = mock_match_analysis(resume_profile, job_analysis)
    optimization_result = mock_resume_optimization(
        normalized_resume,
        resume_profile,
        job_analysis,
        match_report,
    )
    project_challenge_report = mock_project_challenge(resume_profile, job_analysis)
    markdown_report = generate_markdown_report(
        resume_profile=resume_profile,
        job_analysis=job_analysis,
        match_report=match_report,
        optimization_result=optimization_result,
        project_challenge_report=project_challenge_report,
    )

    return FinalReport(
        resume_profile=resume_profile,
        job_analysis=job_analysis,
        match_report=match_report,
        optimization_result=optimization_result,
        project_challenge_report=project_challenge_report,
        markdown_report=markdown_report,
    )
