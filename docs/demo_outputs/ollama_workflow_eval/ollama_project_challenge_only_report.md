# Ollama Workflow Evaluation - ollama-project-challenge-only

## Config

- model: qwen2.5:1.5b
- base_url: http://127.0.0.1:11434/v1
- temperature: 0.0
- timeout: 300.0
- mode: ollama-project-challenge-only
- generated_at: 2026-06-11T05:18:36+00:00

## Workflow Steps

| step | agent_name | mode | fallback_reason | quality_warnings | duration_ms | llm_success_count | fallback_count | prompt_version | item_fallback_reasons | summary |
| --- | --- | --- | --- | --- | ---: | ---: | ---: | --- | --- | --- |
| 1 | ResumeParseAgent | mock |  | None | 1.385 |  |  |  |  | 识别技能 12 个，项目 2 个。 |
| 2 | JDAnalysisAgent | mock |  | None | 2.874 |  |  |  |  | 使用 mock JD 规则分析 必备技能 9 个。 |
| 3 | MatchAgent | mock |  | None | 2.338 |  |  |  |  | 生成匹配报告，总分 77.0。 |
| 4 | ResumeOptimizeAgent | mock |  | None | 0.399 |  |  |  |  | 使用 mock 简历优化 生成 2 条 JD 定向建议。 |
| 5 | ProjectInterviewAgent | llm |  | None | 38549.408 | 6 | 0 | project_question_generator_v1 |  | 使用 LLM 项目追问 |
| 6 | ReportAgent | mock |  | None | 0.240 |  |  |  |  | 聚合结构化结果并生成 Markdown 报告。 |

## Token Estimate

| agent | estimated_input_tokens | estimated_output_tokens | estimated_total_tokens | mode | fallback_reason | actual_prompt_tokens | actual_completion_tokens | actual_total_tokens |
| --- | ---: | ---: | ---: | --- | --- | ---: | ---: | ---: |
| JDAnalysisAgent | 768 | 401 | 1169 | mock |  |  |  |  |
| ResumeOptimizeAgent | 2259 | 1166 | 3425 | mock |  |  |  |  |
| ProjectInterviewAgent | 1779 | 1430 | 3209 | llm |  | 1336 | 603 | 1939 |

## JDAnalysisAgent Output

- step_mode: mock
- fallback_reason: 
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

- llm_success_count: 6
- fallback_count: 0
- item_fallback_reasons: []
- prompt_version: project_question_generator_v1
- basic_questions_count: 1
- technical_deep_dive_questions_count: 5
- architecture_questions_count: 0
- grounded_questions_count: 6

## Final Report Summary

- overall_score: 77.0
- analysis_quality: medium
- project_count: 2
- work_experience_count: 0
- rewrite_suggestions_count: 6
- grounded_questions_count: 6

## Output Quality Notes

- Workflow ran with 0 fallback step(s).
- JDAnalysisAgent extracted 9 required skills and 9 keywords.
- JDAnalysisAgent quality warnings: None.
- Check required_skills for preferred-skill leakage; the report lists preferred_skills separately for manual review.
- ResumeOptimizeAgent produced 6 rewrite suggestions and 2 JD-targeted bullets.
- 0 non-missing rewrite suggestions lack explicit evidence sources.
- ProjectChallengeAgent produced 6 grounded questions.
- Missing requirements surfaced by MatchAgent: None.
- Estimated total tokens for the three LLM-capable agents: 7803.
- Quality warnings: resume has no quantified or highlight evidence, JD has no clear experience requirements.
- Requested LLM steps returned schema-valid outputs; compare specificity against the mock baseline.

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
- Interview challenge: Can you walk me through a project where you used Python to develop an AI backend solution?

### Requirement: FastAPI
- Match level: matched
- Resume evidence:
  - Skill: FastAPI
- Gap / hint: No additional gap or improvement note.
- Rewrite suggestion: Core skill: FastAPI, highlighted directly against the JD requirement for FastAPI.
- Interview challenge: Can you walk me through how you've used FastAPI in a previous project, and what benefits it brought to the team?

### Requirement: Pydantic
- Match level: matched
- Resume evidence:
  - Skill: Pydantic
- Gap / hint: No additional gap or improvement note.
- Rewrite suggestion: Core skill: Pydantic, highlighted directly against the JD requirement for Pydantic.
- Interview challenge: Can you explain how Pydantic can be used to validate and enforce the structure of your backend API responses, ensuring data integrity and consistency?

### Requirement: LangGraph
- Match level: matched
- Resume evidence:
  - Skill: LangGraph
- Gap / hint: No additional gap or improvement note.
- Rewrite suggestion: Core skill: LangGraph, highlighted directly against the JD requirement for LangGraph.
- Interview challenge: Could you walk me through how LangGraph is used in the backend development of an AI project, and explain its significance compared to other graph databases?

### Requirement: LLM
- Match level: matched
- Resume evidence:
  - Skill: LLM
- Gap / hint: No additional gap or improvement note.
- Rewrite suggestion: Core skill: LLM, highlighted directly against the JD requirement for LLM.
- Interview challenge: Can you walk me through a project where you utilized an LLM to solve a specific problem, and how did the model's performance compare to human judgment in terms of accuracy and efficiency?

## 8. Project Challenge Questions

### Basic questions

- **Question**: Can you explain how Pydantic can be used to validate and enforce the structure of your backend API responses, ensuring data integrity and consistency?
  - Evaluates: To assess your understanding of using Pydantic for validating backend API responses.
  - Answer framework: Understanding of Pydantic's role in enforcing data structures

### Technical deep dive questions

- **Question**: 请描述你在项目 1 中如何实现一个基于目标匹配的简历/JD匹配系统，该系统旨在帮助前端工程师快速找到合适的职位。
  - Evaluates: 通过这个问题，我们可以了解你对AI技术在简历匹配中的应用理解和实际操作能力。
  - Answer framework: 简历匹配系统的功能描述; 使用的技术和工具; 实现过程中的挑战与解决方案
- **Question**: Can you walk me through a project where you used Python to develop an AI backend solution?
  - Evaluates: To assess your experience and proficiency with Python in the context of developing AI backend solutions.
  - Answer framework: Project details; Python code snippets; Explanation of key algorithms or models
- **Question**: Can you walk me through how you've used FastAPI in a previous project, and what benefits it brought to the team?
  - Evaluates: To assess your practical experience with FastAPI and its ability to contribute to the development of an AI backend.
  - Answer framework: Explain the setup process; Describe the integration with other components; Discuss any performance improvements or scalability benefits
- **Question**: Could you walk me through how LangGraph is used in the backend development of an AI project, and explain its significance compared to other graph databases?
  - Evaluates: To assess your understanding of LangGraph's capabilities and its role within a larger system.
  - Answer framework: Explanation of LangGraph's features; Comparison with traditional graph databases
- **Question**: Can you walk me through a project where you utilized an LLM to solve a specific problem, and how did the model's performance compare to human judgment in terms of accuracy and efficiency?
  - Evaluates: To assess your ability to apply AI technology effectively and understand its limitations.
  - Answer framework: Project description; Problem statement; Model selection; Performance comparison with human judgment

### Architecture and tradeoff questions

- None

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
