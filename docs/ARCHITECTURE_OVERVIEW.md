# JobAgent Architecture Overview

## Resume Profile Review API

Resume Profile Review API is the first step of the Slate-like flow:

```text
resume upload/text -> profile review -> later search / analysis
```

The first phase exposes `POST /resume/profile-review` to parse `resume_text`
into a draft `ResumeProfile` plus deterministic warnings, questions,
suggested edits, editable sections, and a confidence label.

v1.8 adds `POST /resume/profile-review/confirm`. It is stateless, does not
persist a `review_id`, and merges user-provided edits/answers into a confirmed
profile result for later search/analysis phases. It still does not add UI,
persistence, search integration, or profile versioning.

v1.9 adds `profile_context` support for `POST /brief/from-search`.
`profile_context` combines `confirmed_profile` and `user_confirmed_data`, then
builds an effective query without replacing the user's explicit query. This is
the first minimal bridge from Profile Review to Search/Brief, without UI,
persistence, tracker integration, multi-provider ranking changes, or live
provider internals changes.

v2.0 adds `ProfileSearchPlan`. `profile_context` is no longer treated as a flat
query append only; it is normalized into role terms, skill terms, location
terms, constraint terms, warnings, and `effective_query`. `brief/from-search`
still sends only `effective_query` into providers, so provider internals remain
unchanged.

v2.1 adds `POST /brief/search-plan`. It previews `ProfileSearchPlan` before any
provider search runs, which supports a Slate-like middle state:
`confirmed profile -> search plan -> brief/from-search`. The endpoint does not
call providers, does not persist data, and does not change `JobBriefReport`.

v2.2 adds a minimal Streamlit panel that visualizes the same middle state:
`resume input -> profile review -> profile confirm -> search plan preview -> brief/from-search`.
It reuses existing APIs only. It does not add persistence, tracker integration,
provider internals changes, or new backend logic.

## 1. Project Goal

JobAgent 不是一个单纯的聊天机器人，也不是一个通用爬虫项目。它更像一个面向求职准备场景的本地工作台，用来把“找岗位、判断匹配度、改简历、准备面试、记录投递进展”串成一个可复盘的流程。

当前最核心的目标是把下面这条链路做扎实：

```text
岗位发现
-> 候选岗位确认
-> 投递 tracker
-> 针对岗位的深度分析
-> 简历证据匹配
-> 简历改写建议
-> 项目追问
-> 最终准备报告
```

它强调的是：

- 小步、可测试、可追踪的求职分析闭环
- deterministic core first，而不是一开始就堆复杂 AI 能力
- LLM 可选、可 fallback，而不是把主链路完全绑定在模型输出上

## 2. Current Business Loop

当前已经形成的核心业务闭环可以概括为：

```text
Job Source
  -> SearchResultItem
  -> JobImportCandidate
  -> ApplicationRecord
  -> Application Deep Analysis
  -> FinalReport
```

关键对象边界如下：

- `SearchResultItem`
  - 搜索阶段的临时结果
  - 可能来自 `mock`、`local_db`、`gemini_cli`、`cuhksz_live`
  - 还不是正式跟踪对象
- `JobImportCandidate`
  - 用户待确认的候选岗位
  - 是 search/brief 与 tracker 之间的缓冲层
- `ApplicationRecord`
  - 用户正式跟踪的岗位
  - 有状态、备注、下一步动作、简历版本关联
- `AnalysisRecord`
  - 已保存的分析结果
  - 可以关联 `application_id`

## 3. Core Analysis Workflow

当前核心分析 workflow 为：

```text
ResumeParseAgent
  -> JDAnalysisAgent
  -> MatchAgent
  -> ResumeOptimizeAgent
  -> ProjectChallengeAgent
  -> ReportAgent
```

每个 Agent 的职责与输入输出：

- `ResumeParseAgent`
  - 输入：`resume_text`
  - 输出：`ResumeProfile`
  - 作用：识别技能、项目、工作经历、missing info
- `JDAnalysisAgent`
  - 输入：`jd_text`
  - 输出：`JobAnalysis`
  - 作用：提取岗位标题、required skills、responsibilities、experience requirements
  - LLM 模式：从 prompt registry 加载 JDAnalysis prompt，并在 schema validation 后通过 JD quality gate 检查 required skills、responsibility metadata pollution、verbose skills/keywords 和 metadata grounding；风险过高时 fallback 到 deterministic baseline。
- `MatchAgent`
  - 输入：`ResumeProfile` + `JobAnalysis`
  - 输出：`MatchReport`
  - 作用：给出 overall score、matched/missing points、evidence
- `ResumeOptimizeAgent`
  - 输入：`resume_text` + `ResumeProfile` + `JobAnalysis` + `MatchReport`
  - 输出：`ResumeOptimizationResult`
  - 作用：生成简历改写和补强建议
- `ProjectChallengeAgent`
  - 输入：`ResumeProfile` + `JobAnalysis` + `MatchReport`
  - 输出：`ProjectChallengeReport`
  - 作用：生成项目追问与 grounded challenge
- `ReportAgent`
  - 输入：所有结构化结果
  - 输出：最终 Markdown report
  - 作用：把分析结果组织成最终可阅读报告

最近新增并且已经进入主链路的关键能力：

- `MatchReport.requirement_matches`
  - requirement 级别的 JD-Resume 对齐结果
- `ResumeOptimizationResult.rewrite_suggestions`
  - 与 requirement match 对齐的简历改写建议
- `ProjectChallengeReport.grounded_questions`
  - 与 requirement match 对齐的项目追问
- `FinalReport.analysis_quality`
  - 对 resume / JD / match evidence 的质量门禁
- `Markdown JD-Resume Evidence Chain`
  - 在最终报告里串起 requirement -> evidence -> rewrite -> challenge

ProjectChallengeAgent LLM mode is decomposed: Python selects requirements and binds evidence, the LLM generates one small grounded question draft at a time, and Python validates and assembles the unchanged `ProjectChallengeReport` schema. A failed question uses local fallback without forcing the whole agent to fallback unless every item fails or no requirements can be selected.

## 4. Code Structure

项目主目录可以按下面理解：

```text
app/api
app/agents
app/services
app/workflows
app/schemas
app/storage
app/services/live_job
tests
docs
.ai/skills
```

各目录职责：

- `app/api`
  - FastAPI route 层
  - 负责 request/response schema 边界和错误返回
- `app/agents`
  - 各分析节点的能力外壳
  - 包含 mock 路径、optional LLM 路径、fallback 约束
- `app/services`
  - 业务服务层
  - 负责 search、candidate、tracker、report、storage orchestration
- `app/workflows`
  - 核心分析编排层
  - 负责主 workflow、LangGraph prototype、trace step
- `app/schemas`
  - Pydantic 数据结构
  - 是 agent、service、API、storage 之间的统一契约
- `app/storage`
  - SQLite 连接和 repository 层
  - 负责 analysis record、job posting、resume version、application record 持久化
- `app/services/live_job`
  - 公共 live job provider 框架
  - 包括 fetcher、parser、provider orchestration
- `tests`
  - 单元与集成测试
  - 覆盖 workflow、API、storage、provider、tracker 等核心链路
- `docs`
  - 项目设计、边界、demo、roadmap 与答辩材料
- `.ai/skills`
  - Codex 开发流程与约束
  - 用来限制每轮开发范围和最终交付格式

## 5. Search Provider Architecture

当前 provider 边界主要是：

```text
mock
local_db
gemini_cli
cuhksz_live
```

各自职责：

- `mock`
  - 演示和测试用稳定 provider
- `local_db`
  - 从本地 `public_job_posts` 回放已采集岗位
  - 适合 repeatable demo 和离线复盘
- `gemini_cli`
  - 实验性 provider
  - 默认关闭，只在显式开启时使用
- `cuhksz_live`
  - 针对 CUHKSZ career 网站的 live provider
  - 支持 metadata / warnings / detail rerank

关于 `cuhksz_live`，需要特别明确：

- 它是针对 `CUHKSZ` public job source 的定制 provider
- 它不是全网实时搜索
- 它不是通用爬虫
- 它不会做登录、验证码、浏览器自动化或反爬绕过

## 6. Candidate / Tracker / Analysis Boundary

三层边界如下：

```text
SearchResultItem 不直接进入 tracker
JobImportCandidate 是缓冲层
ApplicationRecord 才是正式跟踪对象
ApplicationRecord 可以触发 Deep Analysis
AnalysisRecord 关联 application_id
```

更具体地说：

- `SearchResultItem`
  - 排名/检索结果
  - 生命周期短
- `JobImportCandidate`
  - 用户审阅与确认层
  - 允许轻量编辑和状态流转
- `ApplicationRecord`
  - 真正进入 tracker 的对象
  - 管理状态、备注、resume version、next action
- `AnalysisRecord`
  - 保存一次具体分析的输出
  - 可以回放 workflow trace 和 markdown report

v2.4 adds `ApplicationAnalysisSummary` as a lightweight read-side summary for
`ApplicationRecord` responses. Applications now expose `analysis_count`,
`latest_analysis_record_id`, `last_match_score`, `last_analysis_quality`,
`last_analyzed_at`, and `has_analysis` when possible by reading existing linked
`analysis_records`. This lets tracker/application views reflect deep analysis
progress without adding a dashboard, analysis diff, multi-run comparison UI, or
database-heavy history view.

## 7. Engineering Principles

当前项目的工程原则可以概括为：

```text
small deterministic core first
mock-first and testable
LLM optional / fallback
schema-first
provider metadata and warnings
no unsupported resume fabrication
quality gate for low-confidence analysis
```

对应解释：

- `small deterministic core first`
  - 先把稳定、可验证的闭环做出来
- `mock-first and testable`
  - 没有 LLM 也能跑通主链路，测试可以稳定覆盖
- `LLM optional / fallback`
  - 模型只是增强，不是主链路单点依赖
- `schema-first`
  - 先用 Pydantic 固定数据契约
- `provider metadata and warnings`
  - 对输入质量和 provider 行为保留可解释信号
- `no unsupported resume fabrication`
  - 不允许编造简历经历或项目事实
- `quality gate for low-confidence analysis`
  - 当 resume/JD/evidence 不足时，明确提示分析可信度有限

## 8. What This Project Does Not Do Yet

下面这些不是永久不做，而是当前版本明确不做或尚未完成：

```text
AI Interview session
RAG question bank
multi-site generic crawler
auto apply
email/calendar reminder
multi-user auth
async search run / Celery
PDF/DOCX resume export
```

换句话说，当前边界是：

- 先把本地求职分析工作台做扎实
- 不提前扩展为大型平台化系统
- 不让“未来可能做”的能力压垮当前核心闭环

## 9. Suggested Demo Path

推荐的 3-5 分钟 demo 路线：

```text
1. 使用 search provider 找岗位
2. 生成 / 查看 candidate
3. 导入 Application Tracker
4. 对 application 运行 deep analysis
5. 查看 final report
6. 重点展示 Evidence Chain / Rewrite Suggestions / Grounded Questions / Analysis Quality
```

这样可以比较自然地讲清楚：

- 岗位从哪里来
- 为什么需要 candidate 缓冲层
- tracker 和 analysis 如何接上
- 分析结果如何反向服务简历优化和面试准备

## 10. Roadmap

当前比较克制的路线图可以写成：

```text
v1.x Documentation & demo polish
v1.x Core analysis quality refinement
v1.x Optional tracker summary
v2.x AI interview / RAG question bank
```

重点不是承诺功能，而是说明优先级：

- 先补文档、演示、可解释性
- 再继续打磨核心分析质量
- 更大的 AI interview / RAG 能力放到后续阶段
