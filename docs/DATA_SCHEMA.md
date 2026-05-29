# JobAgent Data Schema

> 用途：稳定核心数据结构，让 Agent、service、UI 和后续 API 围绕同一组 schema 协作。

## 1. 设计原则

1. 所有核心输入输出优先使用 Pydantic schema。
2. 原始文本和结构化结果都要保留。
3. 简历优化必须保留原文、建议和改写示例，不能覆盖原始内容。
4. 匹配报告必须包含评分、证据、风险和建议。
5. 项目追问必须包含问题、考察点、回答框架和暴露短板。
6. 信息不足时返回空值、空列表或 `missing_info`，不要编造。

## 2. 核心对象

- `UserProfile`
- `ResumeProfile`
- `JobPosting`
- `JobAnalysis`
- `MatchReport`
- `ResumeOptimizationResult`
- `ProjectChallengeReport`
- `FinalReport`

## 3. UserProfile

用途：描述用户求职画像。

关键字段：

- `target_roles: list[str]`
- `target_locations: list[str]`
- `target_industries: list[str]`
- `seniority: str | None`
- `core_skills: list[str]`
- `constraints: list[str]`
- `notes: str | None`

## 4. ResumeProfile

用途：保存简历解析后的结构化信息。

关键字段：

- `raw_text: str`
- `name: str | None`
- `education: list[EducationItem]`
- `skills: list[str]`
- `projects: list[ProjectExperience]`
- `work_experiences: list[WorkExperience]`
- `certificates: list[str]`
- `highlights: list[str]`
- `missing_info: list[str]`

## 5. JobPosting

用途：保存岗位原始信息。

关键字段：

- `title: str | None`
- `company: str | None`
- `location: str | None`
- `source_url: str | None`
- `raw_jd: str`
- `created_at: str | None`

## 6. JobAnalysis

用途：保存 JD 结构化分析结果。

关键字段：

- `job_title: str | None`
- `company: str | None`
- `responsibilities: list[str]`
- `required_skills: list[str]`
- `preferred_skills: list[str]`
- `experience_requirements: list[str]`
- `education_requirements: list[str]`
- `soft_skills: list[str]`
- `implicit_requirements: list[str]`
- `keywords: list[str]`
- `job_category: str | None`

## 7. MatchReport

用途：比较简历和 JD，输出可解释的匹配结果。

建议字段：

```python
class MatchReport(BaseModel):
    overall_score: float
    skill_score: float
    project_score: float
    experience_score: float
    keyword_coverage: float
    matched_points: list[str]
    missing_points: list[str]
    risks: list[str]
    evidence: list[str]
    apply_recommendation: str
    short_term_suggestions: list[str]
    long_term_suggestions: list[str]
```

## 8. ResumeOptimizationResult

用途：输出简历优化建议。

关键字段：

- `overall_issues: list[str]`
- `keywords_to_add: list[str]`
- `skills_section_suggestions: list[str]`
- `project_rewrite_suggestions: list[RewriteSuggestion]`
- `jd_targeted_bullets: list[str]`
- `do_not_exaggerate: list[str]`
- `missing_info_needed: list[str]`

约束：

- 不新增用户没有提供的经历、项目、公司、数据或技术。
- 需要量化但缺少数据时，只提示用户补充。

## 9. ProjectChallengeReport

用途：生成项目面试追问和补强建议。

关键字段：

- `basic_questions: list[ChallengeQuestion]`
- `technical_deep_dive_questions: list[ChallengeQuestion]`
- `architecture_questions: list[ChallengeQuestion]`
- `tradeoff_questions: list[ChallengeQuestion]`
- `data_and_evaluation_questions: list[ChallengeQuestion]`
- `scalability_questions: list[ChallengeQuestion]`
- `interviewer_concerns: list[str]`
- `answer_frameworks: list[str]`
- `improvement_suggestions: list[str]`

## 10. FinalReport

用途：聚合上游结果，生成最终 Markdown 报告。

关键字段：

- `title: str`
- `user_summary: str`
- `job_summary: str`
- `match_report: MatchReport`
- `optimization_result: ResumeOptimizationResult`
- `project_challenge_report: ProjectChallengeReport`
- `weekly_action_plan: list[str]`
- `markdown: str`

## 11. 后续实现约定

- schema 文件放在 `app/schemas/`。
- service 之间传递 schema 实例，而不是随手传嵌套 dict。
- LLM 输出必须先过 schema 校验，再进入下游流程。
- mock 输出也要遵守同一套 schema，方便后续替换真实 Agent。
