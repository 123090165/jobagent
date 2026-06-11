# Ollama Workflow Evaluation - ollama-jd-only

## Config

- model: qwen2.5:1.5b
- base_url: http://127.0.0.1:11434/v1
- temperature: 0.0
- timeout: 180.0
- mode: ollama-jd-only
- generated_at: 2026-06-11T00:32:02+00:00

## Workflow Steps

| step | agent_name | mode | fallback_reason | duration_ms | summary |
| --- | --- | --- | --- | ---: | --- |
| 1 | ResumeParseAgent | mock |  | 0.140 | 识别技能 12 个，项目 2 个。 |
| 2 | JDAnalysisAgent | llm |  | 17490.855 | 使用 LLM JD 分析 必备技能 4 个。 |
| 3 | MatchAgent | mock |  | 1.767 | 生成匹配报告，总分 27.0。 |
| 4 | ResumeOptimizeAgent | mock |  | 0.151 | 使用 mock 简历优化 生成 2 条 JD 定向建议。 |
| 5 | ProjectInterviewAgent | mock |  | 0.118 | 使用 mock 项目追问 |
| 6 | ReportAgent | mock |  | 0.156 | 聚合结构化结果并生成 Markdown 报告。 |

## Token Estimate

| agent | estimated_input_tokens | estimated_output_tokens | estimated_total_tokens | mode | fallback_reason | actual_prompt_tokens | actual_completion_tokens | actual_total_tokens |
| --- | ---: | ---: | ---: | --- | --- | ---: | ---: | ---: |
| JDAnalysisAgent | 456 | 583 | 1039 | llm |  | 382 | 324 | 706 |
| ResumeOptimizeAgent | 3273 | 1538 | 4811 | mock |  |  |  |  |
| ProjectInterviewAgent | 1466 | 1866 | 3332 | mock |  |  |  |  |

## JDAnalysisAgent Output

- job_title: None
- company: Example AI Lab
- location: Shenzhen / Remote
- required_skills: Python backend development experience, FastAPI or similar web framework experience, LLM / agent workflow experience, including LangGraph or equivalent orchestration, SQL database experience, preferably SQLite for prototypes
- preferred_skills: Docker and GitHub Actions, Experience with job search, resume analysis, or recommendation systems
- responsibilities: Build Python backend services for AI agent workflow demos., Implement FastAPI endpoints, Pydantic schemas, and SQLite-backed persistence., Connect LLM or agent workflow components while keeping deterministic fallbacks., Write tests, documentation, and quality checks for generated model outputs., Review workflow outputs for evidence grounding, missing information, and hallucination risk.
- keywords: AI Agent Backend Intern, Python backend services, FastAPI endpoints, LLM/agent workflow components, SQLite-backed persistence, model output quality evaluation, Git, testing, documentation

## ResumeOptimizeAgent Output

- rewrite_suggestions_count: 6
- jd_targeted_bullets_count: 2
- missing_info_needed: 缺少结果或量化亮点
- do_not_exaggerate: 不要编造没有做过的公司、项目、数据指标或技术栈。, 没有量化数据时，只写“建议补充指标”，不要直接生成虚假百分比。

## ProjectChallengeAgent Output

- basic_questions_count: 2
- technical_deep_dive_questions_count: 3
- architecture_questions_count: 1
- grounded_questions_count: 8

## Final Report Summary

- overall_score: 27.0
- analysis_quality: medium
- project_count: 2
- work_experience_count: 0
- rewrite_suggestions_count: 6
- grounded_questions_count: 8

## Output Quality Notes

- Workflow ran with 0 fallback step(s).
- JDAnalysisAgent extracted 4 required skills and 7 keywords.
- Check required_skills for preferred-skill leakage; the report lists preferred_skills separately for manual review.
- ResumeOptimizeAgent produced 6 rewrite suggestions and 2 JD-targeted bullets.
- 0 non-missing rewrite suggestions lack explicit evidence sources.
- ProjectChallengeAgent produced 8 grounded questions.
- Missing requirements surfaced by MatchAgent: Write tests, documentation, and quality checks for generated model outputs., Review workflow outputs for evidence grounding, missing information, and hallucination risk..
- Estimated total tokens for the three LLM-capable agents: 9182.
- Quality warnings: resume has no quantified or highlight evidence, JD has no job title, JD has no clear experience requirements.
- Requested LLM steps returned schema-valid outputs; compare specificity against the mock baseline.

## Final Markdown Report

# JobAgent Analysis Report

## 1. Resume Summary

- Detected skills: Python, FastAPI, Pydantic, LangGraph, LLM, RAG, SQL, SQLite, Docker, Git, REST API, pytest
- Project count: 2
- Work experience count: 0
- Missing information: 缺少结果或量化亮点

## 2. Job Summary

- Job title: Target Role
- Job category: Unknown
- Required skills: Python backend development experience, FastAPI or similar web framework experience, LLM / agent workflow experience, including LangGraph or equivalent orchestration, SQL database experience, preferably SQLite for prototypes
- Preferred skills: Docker and GitHub Actions, Experience with job search, resume analysis, or recommendation systems

## Analysis Quality

- Overall quality: medium
- Resume quality: medium
- JD quality: medium
- Warnings:
- resume has no quantified or highlight evidence
- JD has no job title
- JD has no clear experience requirements
- Confidence notes:
- Keyword coverage is low, so the match score may underrepresent true fit.

## 3. Match Overview

- Overall score: 27.0 / 100
- Skill score: 0.0 / 100
- Project score: 58.0 / 100
- Experience score: 48.0 / 100
- Keyword coverage: 0.0%
- Apply recommendation: 暂不建议直接投递，先补齐关键技能和项目表达。

## 4. Strengths

- 简历中包含项目经历，可以用于支撑岗位相关能力。

## 5. Gaps and Risks

### Missing points

- 需要补强或明确展示：Python backend development experience
- 需要补强或明确展示：FastAPI or similar web framework experience
- 需要补强或明确展示：LLM / agent workflow experience, including LangGraph or equivalent orchestration
- 需要补强或明确展示：SQL database experience, preferably SQLite for prototypes

### Risks

- JD 中的部分关键技能未在简历中明确出现。
- 项目结果缺少量化指标，面试时容易被追问贡献和效果。
- 工作或实习经历不明显，需要用项目细节补足可信度。

## 6. Resume Optimization

### Overall issues

- 当前简历需要更明确地对齐目标 JD 的必备技能。
- 项目经历应补充问题背景、技术方案、个人贡献和结果指标。

### Keywords to add

- Python backend development experience
- FastAPI or similar web framework experience
- LLM / agent workflow experience, including LangGraph or equivalent orchestration
- SQL database experience, preferably SQLite for prototypes

### Skills section suggestions

- 把与 JD 直接相关的技能放在技能栏前半部分。
- 技能不要只罗列名词，项目中也要出现对应使用场景。

### JD-targeted bullets

- 基于已有项目，补充与目标 JD 技能相关的模块、接口、数据流或评估方式。
- 如果确实使用过相关技术，写清楚使用位置、解决的问题和结果；没有使用过则不要硬写。

### Do not exaggerate

- 不要编造没有做过的公司、项目、数据指标或技术栈。
- 没有量化数据时，只写“建议补充指标”，不要直接生成虚假百分比。

## 7. JD-Resume Evidence Chain

### Requirement: Python backend development experience
- Match level: partial
- Resume evidence:
  - Skill: Python
  - 项目 1 | Target: AI Agent / Backend Engineer Intern
- Gap / hint: Resume mentions related evidence for Python backend development experience, but coverage is still incomplete. | Make Python backend development experience explicit in a project or work bullet with outcome evidence.
- Rewrite suggestion: Core skill: Python, highlighted directly against the JD requirement for Python backend development experience.
- Interview challenge: Your resume shows partial evidence for Python backend development experience. What exactly did you implement, what related pieces were missing from the resume wording, and how would you clarify the boundary in an interview?

### Requirement: FastAPI or similar web framework experience
- Match level: partial
- Resume evidence:
  - Skill: FastAPI
- Gap / hint: Resume mentions related evidence for FastAPI or similar web framework experience, but coverage is still incomplete. | Make FastAPI or similar web framework experience explicit in a project or work bullet with outcome evidence.
- Rewrite suggestion: Core skill: FastAPI, highlighted directly against the JD requirement for FastAPI or similar web framework experience.
- Interview challenge: Your resume shows partial evidence for FastAPI or similar web framework experience. What exactly did you implement, what related pieces were missing from the resume wording, and how would you clarify the boundary in an interview?

### Requirement: LLM / agent workflow experience, including LangGraph or equivalent orchestration
- Match level: partial
- Resume evidence:
  - Skill: LangGraph
  - Skill: LLM
  - 项目 1 | Target: AI Agent / Backend Engineer Intern
- Gap / hint: Resume mentions related evidence for LLM / agent workflow experience, including LangGraph or equivalent orchestration, but coverage is still incomplete. | Make LLM / agent workflow experience, including LangGraph or equivalent orchestration explicit in a project or work bullet with outcome evidence.
- Rewrite suggestion: Core skill: LangGraph, highlighted directly against the JD requirement for LLM / agent workflow experience, including LangGraph or equivalent orchestration.
- Interview challenge: Your resume shows partial evidence for LLM / agent workflow experience, including LangGraph or equivalent orchestration. What exactly did you implement, what related pieces were missing from the resume wording, and how would you clarify the boundary in an interview?

### Requirement: SQL database experience, preferably SQLite for prototypes
- Match level: partial
- Resume evidence:
  - Skill: SQL
  - Skill: SQLite
- Gap / hint: Resume mentions related evidence for SQL database experience, preferably SQLite for prototypes, but coverage is still incomplete. | Make SQL database experience, preferably SQLite for prototypes explicit in a project or work bullet with outcome evidence.
- Rewrite suggestion: Core skill: SQL, highlighted directly against the JD requirement for SQL database experience, preferably SQLite for prototypes.
- Interview challenge: Your resume shows partial evidence for SQL database experience, preferably SQLite for prototypes. What exactly did you implement, what related pieces were missing from the resume wording, and how would you clarify the boundary in an interview?

### Requirement: Build Python backend services for AI agent workflow demos.
- Match level: partial
- Resume evidence:
  - Skill: Python
  - 项目 1 | Target: AI Agent / Backend Engineer Intern
  - 项目 2 | 1. JobAgent-style Resume/JD Matching System
- Gap / hint: Resume mentions related evidence for Build Python backend services for AI agent workflow demos., but coverage is still incomplete. | Add one project or work bullet that shows how you handled Build Python backend services for AI agent workflow demos..
- Rewrite suggestion: Core skill: Python, highlighted directly against the JD requirement for Build Python backend services for AI agent workflow demos..
- Interview challenge: Your resume shows partial evidence for Build Python backend services for AI agent workflow demos.. What exactly did you implement, what related pieces were missing from the resume wording, and how would you clarify the boundary in an interview?

## 8. Project Challenge Questions

### Basic questions

- **Question**: 项目 1 解决的真实问题是什么？为什么需要做这个项目？
  - Evaluates: 项目背景是否真实，是否能讲清楚需求来源。
  - Answer framework: 先讲使用场景，再讲痛点，最后讲你的目标和边界。
- **Question**: 这个项目中你个人负责了哪一部分？哪些不是你做的？
  - Evaluates: 个人贡献边界是否清楚，是否存在夸大风险。
  - Answer framework: 按模块列出个人负责内容，并诚实说明协作或参考部分。

### Technical deep dive questions

- **Question**: 你在项目中如何体现 Python backend development experience？具体用在什么模块？
  - Evaluates: 技能是否只是写在简历上，还是有真实使用场景。
  - Answer framework: 说明使用位置、输入输出、关键实现和遇到的问题。
- **Question**: 你在项目中如何体现 FastAPI or similar web framework experience？具体用在什么模块？
  - Evaluates: 技能是否只是写在简历上，还是有真实使用场景。
  - Answer framework: 说明使用位置、输入输出、关键实现和遇到的问题。
- **Question**: 你在项目中如何体现 LLM / agent workflow experience, including LangGraph or equivalent orchestration？具体用在什么模块？
  - Evaluates: 技能是否只是写在简历上，还是有真实使用场景。
  - Answer framework: 说明使用位置、输入输出、关键实现和遇到的问题。

### Architecture and tradeoff questions

- **Question**: 如果这个项目用户量增加 10 倍，你会先改哪一层？
  - Evaluates: 是否理解架构瓶颈和扩展优先级。
  - Answer framework: 从数据流、存储、接口、异步任务和监控几个角度分析。
- **Question**: 当时为什么选择这种技术方案？有没有更简单或更稳定的替代方案？
  - Evaluates: 是否具备技术选型和取舍意识。
  - Answer framework: 讲清楚约束、备选方案、选择理由和后续改进。

## 9. One-Week Action Plan

- Day 1: fill in missing project context, ownership, and result signals.
- Day 2: reorder the skills section around the JD's must-have skills.
- Day 3: rewrite the most relevant project bullets as problem -> approach -> tech -> result.
- Day 4: rehearse the challenge questions in this report and mark weak answers.
- Day 5: add one real demo, test artifact, or document that supports project credibility.
- Day 6: tailor one resume version directly against the JD keywords.
- Day 7: review the match gaps and decide whether to apply now or close the gap first.

## 10. Evidence

- 简历识别技能：Python, FastAPI, Pydantic, LangGraph, LLM, RAG, SQL, SQLite, Docker, Git, REST API, pytest
- JD 关键词：AI Agent Backend Intern, Python backend services, FastAPI endpoints, LLM/agent workflow components, SQLite-backed persistence, model output quality evaluation, Git, testing, documentation
