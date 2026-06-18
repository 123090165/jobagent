# Ollama Workflow Evaluation - ollama-jd-only

## Config

- model: qwen2.5:1.5b
- base_url: http://127.0.0.1:11434/v1
- temperature: 0.0
- timeout: 300.0
- mode: ollama-jd-only
- generated_at: 2026-06-11T05:17:57+00:00

## Workflow Steps

| step | agent_name | mode | fallback_reason | quality_warnings | duration_ms | llm_success_count | fallback_count | prompt_version | item_fallback_reasons | summary |
| --- | --- | --- | --- | --- | ---: | ---: | ---: | --- | --- | --- |
| 1 | ResumeParseAgent | mock |  | None | 1.328 |  |  |  |  | 识别技能 12 个，项目 2 个。 |
| 2 | JDAnalysisAgent | fallback | ValidationError | None | 16858.255 |  |  |  |  | LLM 分析失败，已回退 mock（ValidationError） 必备技能 9 个。 |
| 3 | MatchAgent | mock |  | None | 2.477 |  |  |  |  | 生成匹配报告，总分 77.0。 |
| 4 | ResumeOptimizeAgent | mock |  | None | 0.596 |  |  |  |  | 使用 mock 简历优化 生成 2 条 JD 定向建议。 |
| 5 | ProjectInterviewAgent | mock |  | None | 0.180 |  |  |  |  | 使用 mock 项目追问 |
| 6 | ReportAgent | mock |  | None | 0.303 |  |  |  |  | 聚合结构化结果并生成 Markdown 报告。 |

## Token Estimate

| agent | estimated_input_tokens | estimated_output_tokens | estimated_total_tokens | mode | fallback_reason | actual_prompt_tokens | actual_completion_tokens | actual_total_tokens |
| --- | ---: | ---: | ---: | --- | --- | ---: | ---: | ---: |
| JDAnalysisAgent | 768 | 401 | 1169 | fallback | ValidationError | 644 | 281 | 925 |
| ResumeOptimizeAgent | 2259 | 1166 | 3425 | mock |  |  |  |  |
| ProjectInterviewAgent | 1779 | 1495 | 3274 | mock |  |  |  |  |

## JDAnalysisAgent Output

- step_mode: fallback
- fallback_reason: ValidationError
- quality_warnings: []
- job_title: Role: AI Agent Backend Intern
- company: None
- location: None
- required_skills: Python, FastAPI, Pydantic, LangGraph, LLM, SQL, SQLite, Docker, Git
- preferred_skills: None
- responsibilities: Role: AI Agent Backend Intern, Company: Example AI Lab, Location: Shenzhen / Remote
- keywords: Python, FastAPI, Pydantic, LangGraph, LLM, SQL, SQLite, Docker, Git

## ResumeOptimizeAgent Output

- rewrite_suggestions_count: 6
- jd_targeted_bullets_count: 2
- missing_info_needed: 缺少结果或量化亮点
- do_not_exaggerate: 不要编造没有做过的公司、项目、数据指标或技术栈。, 没有量化数据时，只写“建议补充指标”，不要直接生成虚假百分比。

## ProjectChallengeAgent Output

- llm_success_count: None
- fallback_count: None
- item_fallback_reasons: []
- prompt_version: 
- basic_questions_count: 2
- technical_deep_dive_questions_count: 3
- architecture_questions_count: 1
- grounded_questions_count: 8

## Final Report Summary

- overall_score: 77.0
- analysis_quality: medium
- project_count: 2
- work_experience_count: 0
- rewrite_suggestions_count: 6
- grounded_questions_count: 8

## Output Quality Notes

- Workflow ran with 1 fallback step(s).
- JDAnalysisAgent extracted 9 required skills and 9 keywords.
- JDAnalysisAgent quality warnings: None.
- Check required_skills for preferred-skill leakage; the report lists preferred_skills separately for manual review.
- ResumeOptimizeAgent produced 6 rewrite suggestions and 2 JD-targeted bullets.
- 0 non-missing rewrite suggestions lack explicit evidence sources.
- ProjectChallengeAgent produced 8 grounded questions.
- Missing requirements surfaced by MatchAgent: None.
- Estimated total tokens for the three LLM-capable agents: 7868.
- Quality warnings: resume has no quantified or highlight evidence, JD has no clear experience requirements.
- At least one requested LLM step fell back, so quality should be judged as fallback output for those agents.

## Final Markdown Report

# JobAgent Analysis Report

## 1. Resume Summary

- Detected skills: Python, FastAPI, Pydantic, LangGraph, LLM, RAG, SQL, SQLite, Docker, Git, REST API, pytest
- Project count: 2
- Work experience count: 0
- Missing information: 缺少结果或量化亮点

## 2. Job Summary

- Job title: Role: AI Agent Backend Intern
- Job category: AI / LLM 应用开发
- Required skills: Python, FastAPI, Pydantic, LangGraph, LLM, SQL, SQLite, Docker, Git
- Preferred skills: None

## Analysis Quality

- Overall quality: medium
- Resume quality: medium
- JD quality: medium
- Warnings:
- resume has no quantified or highlight evidence
- JD has no clear experience requirements
- Confidence notes:
- None

## 3. Match Overview

- Overall score: 77.0 / 100
- Skill score: 100.0 / 100
- Project score: 58.0 / 100
- Experience score: 48.0 / 100
- Keyword coverage: 100.0%
- Apply recommendation: 建议投递，同时针对缺失点定制简历。

## 4. Strengths

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

## 5. Gaps and Risks

### Missing points

- None

### Risks

- 项目结果缺少量化指标，面试时容易被追问贡献和效果。
- 工作或实习经历不明显，需要用项目细节补足可信度。

## 6. Resume Optimization

### Overall issues

- 当前简历需要更明确地对齐目标 JD 的必备技能。
- 项目经历应补充问题背景、技术方案、个人贡献和结果指标。

### Keywords to add

- None

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

### Requirement: Python
- Match level: matched
- Resume evidence:
  - Skill: Python
- Gap / hint: No additional gap or improvement note.
- Rewrite suggestion: Core skill: Python, highlighted directly against the JD requirement for Python.
- Interview challenge: You have resume evidence for Python. Walk through the specific project or work context, the key implementation choices, the tradeoffs you made, and the result.

### Requirement: FastAPI
- Match level: matched
- Resume evidence:
  - Skill: FastAPI
- Gap / hint: No additional gap or improvement note.
- Rewrite suggestion: Core skill: FastAPI, highlighted directly against the JD requirement for FastAPI.
- Interview challenge: You have resume evidence for FastAPI. Walk through the specific project or work context, the key implementation choices, the tradeoffs you made, and the result.

### Requirement: Pydantic
- Match level: matched
- Resume evidence:
  - Skill: Pydantic
- Gap / hint: No additional gap or improvement note.
- Rewrite suggestion: Core skill: Pydantic, highlighted directly against the JD requirement for Pydantic.
- Interview challenge: You have resume evidence for Pydantic. Walk through the specific project or work context, the key implementation choices, the tradeoffs you made, and the result.

### Requirement: LangGraph
- Match level: matched
- Resume evidence:
  - Skill: LangGraph
- Gap / hint: No additional gap or improvement note.
- Rewrite suggestion: Core skill: LangGraph, highlighted directly against the JD requirement for LangGraph.
- Interview challenge: You have resume evidence for LangGraph. Walk through the specific project or work context, the key implementation choices, the tradeoffs you made, and the result.

### Requirement: LLM
- Match level: matched
- Resume evidence:
  - Skill: LLM
- Gap / hint: No additional gap or improvement note.
- Rewrite suggestion: Core skill: LLM, highlighted directly against the JD requirement for LLM.
- Interview challenge: You have resume evidence for LLM. Walk through the specific project or work context, the key implementation choices, the tradeoffs you made, and the result.

## 8. Project Challenge Questions

### Basic questions

- **Question**: 项目 1 解决的真实问题是什么？为什么需要做这个项目？
  - Evaluates: 项目背景是否真实，是否能讲清楚需求来源。
  - Answer framework: 先讲使用场景，再讲痛点，最后讲你的目标和边界。
- **Question**: 这个项目中你个人负责了哪一部分？哪些不是你做的？
  - Evaluates: 个人贡献边界是否清楚，是否存在夸大风险。
  - Answer framework: 按模块列出个人负责内容，并诚实说明协作或参考部分。

### Technical deep dive questions

- **Question**: 你在项目中如何体现 Python？具体用在什么模块？
  - Evaluates: 技能是否只是写在简历上，还是有真实使用场景。
  - Answer framework: 说明使用位置、输入输出、关键实现和遇到的问题。
- **Question**: 你在项目中如何体现 FastAPI？具体用在什么模块？
  - Evaluates: 技能是否只是写在简历上，还是有真实使用场景。
  - Answer framework: 说明使用位置、输入输出、关键实现和遇到的问题。
- **Question**: 你在项目中如何体现 Pydantic？具体用在什么模块？
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
- JD 关键词：Python, FastAPI, Pydantic, LangGraph, LLM, SQL, SQLite, Docker, Git
