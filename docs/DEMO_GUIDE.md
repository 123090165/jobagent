# Demo Guide

## Resume Profile Review API

The Slate-like flow now starts with:

```text
resume upload/text -> profile review -> later search / analysis
```

Demo `POST /resume/profile-review` first. It returns a parsed profile draft
with deterministic warnings, missing-info questions, suggested edits, editable
sections, and a confidence label.

v1.8 adds `POST /resume/profile-review/confirm`. It is stateless, does not
persist a `review_id`, and merges user-provided edits/answers into a confirmed
profile result for later search/analysis phases. Do not demo UI, persistence,
search integration, or profile versioning for this phase.

v1.9 lets `POST /brief/from-search` accept `profile_context`, which combines
`confirmed_profile` and `user_confirmed_data`. The context enhances the search
query without replacing the user's explicit query, creating the first minimal
bridge from Profile Review to Search/Brief. Do not demo persistence, tracker
integration, multi-provider ranking changes, or live provider internals.

v2.0 turns that enhancement into `ProfileSearchPlan`: original query, effective
query, role terms, skill terms, location terms, constraint terms, warnings, and
whether profile context was used. `brief/from-search` still passes only the
effective query to providers, so do not demo provider-specific planning, UI,
persistence, tracker integration, or live provider parser changes.

适用对象：

- 面试官
- 课程项目 reviewer
- 未来回看项目的自己

## 1. Demo Goal

这个 demo 展示的不是一个“聊天机器人”，而是一个求职准备闭环：

```text
job source
-> search result
-> import candidate
-> application tracker
-> application deep analysis
-> evidence-based report
```

当前 demo 的重点亮点：

- provider metadata / warnings
- candidate-to-tracker
- application deep analysis
- requirement-level evidence matching
- evidence-based resume rewrite suggestions
- grounded project challenge questions
- JD-Resume Evidence Chain
- Analysis Quality Gate

## 2. Before You Start

开始前建议确认：

- Python virtualenv 已安装依赖
- FastAPI 可运行
- 本地 SQLite 可用
- 可使用 `mock` / `local_db` provider
- `cuhksz_live` 可选，不作为 demo 必须依赖

推荐 demo 使用 `mock` / `local_db`，保证稳定。`cuhksz_live` 可以作为 live provider 补充展示，但不要依赖外网稳定性。

## 3. Recommended Demo Path

推荐用一条 3-5 分钟路径讲清当前闭环。

### Step 1: Run backend / prepare environment

你在演示什么：
- 项目是一个可运行的本地工作台，不只是文档或原型图

为什么这个步骤存在：
- 先建立“系统已经能跑通”的前提

该看哪个输出：
- FastAPI `/docs`
- 本地数据库可用

### Step 2: Search jobs through provider

你在演示什么：
- 通过 `mock` 或 `local_db` 获取岗位搜索结果

为什么这个步骤存在：
- 闭环必须先有岗位来源，后续 candidate、tracker、analysis 都依赖这里

该看哪个输出：
- `SearchResultItem`
- provider 名称
- metadata / warnings

### Step 3: Review SearchResultItem / metadata / warnings

你在演示什么：
- 搜索结果不是只有标题和链接，还保留 provider 的解释信号

为什么这个步骤存在：
- 说明系统不是盲目抓取，而是保留来源质量和不确定性

该看哪个输出：
- result metadata
- warnings
- JD 完整度或质量信号

### Step 4: Create or review JobImportCandidate

你在演示什么：
- 搜索结果先进入 `JobImportCandidate`，作为用户确认缓冲层

为什么这个步骤存在：
- 搜索结果是临时对象，不应该直接进入 tracker

该看哪个输出：
- `JobImportCandidate`
- 候选岗位状态
- 从 search / brief 到 candidate 的转换结果

### Step 5: Import candidate into ApplicationRecord

你在演示什么：
- 把确认后的 candidate 导入 `ApplicationRecord`

为什么这个步骤存在：
- `ApplicationRecord` 才是正式跟踪对象，负责状态、备注、下一步动作和简历版本关联

该看哪个输出：
- `ApplicationRecord`
- `status`
- `notes`
- `next_action`

### Step 6: Run application deep analysis

你在演示什么：
- 对已进入 tracker 的 application 运行完整分析 workflow

为什么这个步骤存在：
- 说明 tracker 不是终点，而是驱动单岗位深度分析的入口

该看哪个输出：
- `POST /applications/{application_id}/analyze`
- `record_id`
- `application_id`
- `workflow_steps`

### Step 7: Open final Markdown report

你在演示什么：
- 最终报告把匹配、改写建议、项目追问和质量信号串成一个可读结果

为什么这个步骤存在：
- 把结构化分析落成真正可复盘的产物

该看哪个输出：
- final Markdown report
- `requirement_matches`
- `rewrite_suggestions`
- `grounded_questions`

### Step 8: Explain Evidence Chain and Analysis Quality

你在演示什么：
- 报告不是只给分，而是解释证据链和质量边界

为什么这个步骤存在：
- 这是 JobAgent 和普通 JD 分析工具的关键区别

该看哪个输出：
- `JD-Resume Evidence Chain`
- `Analysis Quality`

## 4. What To Highlight During Demo

讲解时建议明确说清：

1. `SearchResultItem` 不直接进入 tracker
2. `JobImportCandidate` 是缓冲层
3. `ApplicationRecord` 是正式跟踪对象
4. `AnalysisRecord` 关联 `application_id`
5. `MatchAgent` 生成 `requirement_matches`
6. `ResumeOptimizeAgent` 消费 `requirement_matches` 生成 `rewrite_suggestions`
7. `ProjectChallengeAgent` 消费 `requirement_matches` 生成 `grounded_questions`
8. `ReportAgent` 把 requirement / evidence / rewrite / challenge 串成 evidence chain
9. `Analysis Quality Gate` 提醒输入质量和分析可信度

## 5. Suggested Demo Script

这个项目解决的不是“能不能聊几句”的问题，而是把求职准备里最核心的一条链路做扎实：岗位从哪里来，为什么值得跟进，进入 tracker 之后怎么做单岗位深度分析，最后怎么把 JD 要求、简历证据、改写建议和项目追问串成一个可复盘的报告。

所以它不是一个单纯 chatbot。搜索结果不会直接进 tracker，而是先经过 `JobImportCandidate` 这个确认层，再进入 `ApplicationRecord`。这样用户真正跟踪的是确认过的目标岗位，而不是一堆临时搜索结果。后面的 deep analysis 也不是只给一个分数，而是要求每条关键 requirement 都尽量找到 resume evidence，再往下生成 rewrite suggestion 和 grounded question，最后在报告里形成 evidence chain。

我还加了 quality gate，因为很多分析工具的问题不是“不会输出”，而是会在输入不完整时给出看起来很像真的结论。这里会明确提示 JD、resume 或 evidence coverage 的质量边界，让结果更可信，也更适合演示和复盘。

## 6. Stable Demo Mode

稳定演示建议：

- 首选 `mock` / `local_db`
- 避免 live site 网络波动
- 避免依赖真实 LLM key
- LLM 是 optional enhancement
- deterministic core 可以保证测试和演示稳定

最稳的 demo 讲法是：先展示 deterministic core 已经能把核心闭环跑通，再说明 LLM 和 live provider 是增强项，而不是主链路前提。

## 7. Optional Live Provider Demo

如果你想补充展示 `cuhksz_live`，建议只把它当作 optional live provider：

- 展示它是定制 live provider
- 展示 metadata / warnings
- 展示 detail rerank
- 明确它不是通用爬虫，也不是全网搜索

不建议把它写成必须执行步骤，也不建议把整个 demo 成败压在外部站点可用性上。

## 8. Common Reviewer Questions

**Q: 为什么不直接把搜索结果放进 tracker？**  
A: 因为 `SearchResultItem` 是临时结果，`JobImportCandidate` 作为用户确认缓冲层，`ApplicationRecord` 才是正式跟踪对象。

**Q: 为什么不直接做全网爬虫？**  
A: 当前重点是稳定闭环和可解释分析，不是爬虫规模。live provider 先做可观测和可测试的定制源。

**Q: LLM 不稳定怎么办？**  
A: 主链路是 mock-first / deterministic-first，LLM 是 optional enhancement，并且有 fallback。

**Q: 如何避免简历优化胡编？**  
A: `rewrite_suggestions` 绑定 `resume_evidence`，缺失 requirement 只生成 gap guidance，不伪造经历。

**Q: 这个项目和普通 JD 分析工具有什么区别？**  
A: 它把岗位来源、候选确认、tracker、深度分析、证据链报告串成一个可复盘工作台。

## 9. What Not To Demo Yet

当前不要把下面这些当成已完成 demo 能力：

- AI Interview session
- RAG question bank
- multi-site generic crawler
- auto apply
- email/calendar reminder
- multi-user auth
- PDF/DOCX export

这些可以作为后续方向提到，但不是当前 demo 的重点。

## 10. Related Docs

- [Architecture Overview](ARCHITECTURE_OVERVIEW.md)
- [Workflow Architecture](WORKFLOW_ARCHITECTURE.md)
- [Live Job Provider](LIVE_JOB_PROVIDER.md)
- [Application Tracker](APPLICATION_TRACKER.md)
- [Job Import Candidate](JOB_IMPORT_CANDIDATE.md)
