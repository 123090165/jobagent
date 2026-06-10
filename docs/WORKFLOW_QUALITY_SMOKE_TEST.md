# Workflow Quality Smoke Test

## Purpose

This document records a repeatable smoke test for manually reviewing the current JobAgent workflow output quality. It uses deterministic mock agents, so it does not require an API key and can be rerun during review.

## Run Command

```bash
.venv\Scripts\python.exe scripts\run_workflow_quality_smoke.py
```

Outputs:

- Demo report: `docs/demo_outputs/workflow_quality_smoke_report.md`
- Quality analysis: `docs/WORKFLOW_QUALITY_SMOKE_TEST.md`
- Local smoke database: `data/workflow_quality_smoke.sqlite3` (not committed)

## Test Input

Resume summary: Alex Chen targets an AI Agent / Backend Engineer Intern role and presents Python, FastAPI, SQLite, LangGraph, LLM API, Docker, GitHub Actions, testing, and documentation experience. The resume includes a JobAgent-like matching system, a semantic search job crawler prototype, an STM32 networking course project, and a small backend internship.

JD summary: Example AI Lab is hiring an AI Agent Backend Intern to build Python/FastAPI services, SQLite persistence, LLM or agent workflow components, tests, documentation, and quality checks for evidence grounding and hallucination risk.

## Workflow Result Summary

- generated_at: 2026-06-10T13:05:21+00:00
- workflow_run_id: 61fb2b3a29914ed59829937e60350e46
- saved analysis_record_id: 1
- overall_score: 77.0
- analysis_quality: medium
- parsed project count: 2
- parsed work experience count: 0
- number of rewrite suggestions: 6
- number of project challenge questions: 15

Matched strengths:

- 简历中出现了 JD 关注的技能：Python
- 简历中出现了 JD 关注的技能：FastAPI
- 简历中出现了 JD 关注的技能：Pydantic
- 简历中出现了 JD 关注的技能：LangGraph
- 简历中出现了 JD 关注的技能：LLM
- 简历中出现了 JD 关注的技能：SQL
- 简历中出现了 JD 关注的技能：SQLite
- 简历中出现了 JD 关注的技能：Docker
- 简历中出现了 JD 关注的技能：Git
- 简历中包含项目经历，可以用于支撑岗位相关能力。

Major gaps:

- 项目结果缺少量化指标，面试时容易被追问贡献和效果。
- 工作或实习经历不明显，需要用项目细节补足可信度。

Analysis quality details:

- resume_quality_label: medium
- jd_quality_label: medium
- overall_quality_label: medium
- warning: resume has no quantified or highlight evidence
- warning: JD has no clear experience requirements

Workflow steps:

| step | agent_name | mode | summary | duration_ms | fallback_reason |
| --- | --- | --- | --- | ---: | --- |
| 1 | ResumeParseAgent | mock | 识别技能 12 个，项目 2 个。 | 2.333 |  |
| 2 | JDAnalysisAgent | mock | 使用 mock JD 规则分析 必备技能 9 个。 | 0.518 |  |
| 3 | MatchAgent | mock | 生成匹配报告，总分 77.0。 | 0.893 |  |
| 4 | ResumeOptimizeAgent | mock | 使用 mock 简历优化 生成 2 条 JD 定向建议。 | 0.257 |  |
| 5 | ProjectInterviewAgent | mock | 使用 mock 项目追问 | 0.107 |  |
| 6 | ReportAgent | mock | 聚合结构化结果并生成 Markdown 报告。 | 0.117 |  |

## Quality Review

### 1. What works well

- The workflow identifies 10 matched points and keeps the strongest ones visible: 简历中出现了 JD 关注的技能：Python; 简历中出现了 JD 关注的技能：FastAPI; 简历中出现了 JD 关注的技能：Pydantic.
- Resume optimization produced 6 rewrite suggestions and 2 JD-targeted bullets.
- Project challenge generation produced 8 grounded questions tied back to matched or missing requirements.

### 2. What looks weak or generic

- The overall score is 77.0, but the report still needs clearer reasoning about how each subscore contributes to that number.
- Rewrite suggestions include explicit evidence sources, but several still read as generic skill-alignment bullets rather than project-specific achievements.
- The interview questions are useful for review, but several remain broad unless they cite the exact project detail the candidate should defend.

### 3. Where evidence grounding is good

- Requirement matching is strongest for 9 requirements with resume evidence, including: Python; FastAPI; Pydantic.
- 6 rewrite suggestions include evidence_source values.
- 8 grounded interview questions include related resume evidence.

### 4. Where hallucination risk exists

- Hallucination risk is highest around missing requirements: none detected.
- 0 rewrite suggestions lack explicit evidence sources; these should remain framed as conditional or gap-closing suggestions.
- Quality warnings also constrain trust in the output: resume has no quantified or highlight evidence; JD has no clear experience requirements.

### 5. Which agent should be improved first

- Improve MatchAgent first, because it controls the evidence chain used by both resume rewrite and project interview outputs.

## Next Improvement Candidates

- Make ResumeParseAgent preserve project names, technologies, and evidence spans more explicitly.
- Make MatchAgent separate strong evidence from broad keyword overlap in its scoring explanation.
- Make ResumeOptimizeAgent produce fewer template-like bullets and cite the source project for every suggestion.
- Make ProjectInterviewAgent ask deeper follow-up questions for the highest-value matched requirement.
- Add stable quality metrics for report specificity, evidence coverage, and unsupported claims.
