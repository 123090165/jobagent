from __future__ import annotations

from app.schemas.job import JobAnalysis
from app.schemas.match import (
    ChallengeQuestion,
    MatchReport,
    ProjectChallengeReport,
    ResumeOptimizationResult,
)
from app.schemas.resume import ResumeProfile


def _bullet_list(items: list[str]) -> str:
    if not items:
        return "- 暂无明确内容"
    return "\n".join(f"- {item}" for item in items)


def _question_list(items: list[ChallengeQuestion]) -> str:
    if not items:
        return "- 暂无明确问题"
    lines: list[str] = []
    for item in items:
        lines.append(f"- **问题**：{item.question}")
        lines.append(f"  - 考察点：{item.evaluates}")
        lines.append(f"  - 回答框架：{item.answer_framework}")
    return "\n".join(lines)


def generate_markdown_report(
    *,
    resume_profile: ResumeProfile,
    job_analysis: JobAnalysis,
    match_report: MatchReport,
    optimization_result: ResumeOptimizationResult,
    project_challenge_report: ProjectChallengeReport,
) -> str:
    """Generate a readable Markdown report from structured analysis objects."""
    job_title = job_analysis.job_title or "目标岗位"
    skills = "、".join(resume_profile.skills) if resume_profile.skills else "暂未识别到明确技能"
    required_skills = (
        "、".join(job_analysis.required_skills)
        if job_analysis.required_skills
        else "暂未识别到明确必备技能"
    )

    return f"""# JobAgent 求职分析报告

## 1. 用户画像摘要

- 识别技能：{skills}
- 项目数量：{len(resume_profile.projects)}
- 工作/实习经历数量：{len(resume_profile.work_experiences)}
- 信息缺失：{", ".join(resume_profile.missing_info) if resume_profile.missing_info else "暂无明显缺失"}

## 2. 目标岗位摘要

- 岗位名称：{job_title}
- 岗位类别：{job_analysis.job_category or "暂未判断"}
- 必备技能：{required_skills}
- 加分技能：{", ".join(job_analysis.preferred_skills) if job_analysis.preferred_skills else "暂未识别到明确加分项"}

## 3. 匹配度总览

- 总匹配分：{match_report.overall_score:.1f} / 100
- 技能匹配分：{match_report.skill_score:.1f} / 100
- 项目匹配分：{match_report.project_score:.1f} / 100
- 经验匹配分：{match_report.experience_score:.1f} / 100
- 关键词覆盖率：{match_report.keyword_coverage:.1f}%
- 投递建议：{match_report.apply_recommendation}

## 4. 匹配优势

{_bullet_list(match_report.matched_points)}

## 5. 短板和风险

### 缺失能力

{_bullet_list(match_report.missing_points)}

### 风险点

{_bullet_list(match_report.risks)}

## 6. 简历优化建议

### 整体问题

{_bullet_list(optimization_result.overall_issues)}

### 建议补充或强化的关键词

{_bullet_list(optimization_result.keywords_to_add)}

### 技能栏建议

{_bullet_list(optimization_result.skills_section_suggestions)}

### 针对该 JD 的 bullet 建议

{_bullet_list(optimization_result.jd_targeted_bullets)}

### 不能夸大的部分

{_bullet_list(optimization_result.do_not_exaggerate)}

## 7. 项目拷打问题

### 基础问题

{_question_list(project_challenge_report.basic_questions)}

### 技术细节追问

{_question_list(project_challenge_report.technical_deep_dive_questions)}

### 架构与取舍追问

{_question_list(project_challenge_report.architecture_questions + project_challenge_report.tradeoff_questions)}

## 8. 一周行动计划

- 第 1 天：补全简历中缺失的项目背景、个人职责和结果指标。
- 第 2 天：围绕 JD 必备技能重排技能栏，避免堆无关技术名词。
- 第 3 天：把最相关项目改成“问题 -> 方案 -> 技术 -> 结果”的表达。
- 第 4 天：回答本报告中的项目追问，记录答不上来的问题。
- 第 5 天：补一个最小 demo、测试或文档证据，支撑项目真实性。
- 第 6 天：根据岗位关键词生成一版定制简历。
- 第 7 天：复盘匹配分和短板，决定是否投递或先补强。

## 9. 证据

{_bullet_list(match_report.evidence)}
"""
