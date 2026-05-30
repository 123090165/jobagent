# Agent Trace and Fallback Metadata

> 用途：记录 JobAgent 的 Agent 执行元信息规范。它把“用了 mock、LLM 还是 fallback”从口头说明变成可测试、可展示、可调试的数据。

## 1. 当前目标

每个 Agent 执行后都必须产生元信息：

```text
Agent output + AgentRunMetadata -> WorkflowStepTrace -> SQLite
```

当前元信息包括：

- `agent_name`：Agent 名称。
- `mode`：执行模式，只允许 `mock`、`llm`、`fallback`。
- `fallback_reason`：发生 fallback 时记录原因类型。
- `guardrails`：该 Agent 必须遵守的约束。

## 2. 代码位置

```text
app/agents/types.py
app/workflows/job_analysis_workflow.py
app/storage/repositories.py
```

核心类型：

```python
AgentRunMetadata
AgentRunResult
WorkflowStepTrace
```

## 3. 收紧后的开发要求

新增或修改 Agent 时必须满足：

- 必须返回共享 Pydantic schema。
- 必须提供 `run_*_agent` 形式的元信息入口。
- 必须记录 `mode`。
- 如果发生 fallback，必须记录 `fallback_reason`。
- 必须写明该 Agent 的 `guardrails`。
- 不允许把底层异常原文直接暴露给用户。
- 不允许在 Agent 中写 UI 展示逻辑。
- 不允许在 workflow 中直接写数据库。

## 4. 当前执行模式

### mock

本地规则或确定性实现。

当前适用：

- ResumeParseAgent
- MatchAgent
- ResumeOptimizeAgent
- ProjectInterviewAgent
- ReportAgent

### llm

真实 LLM 调用成功，并通过 schema 校验。

当前适用：

- JDAnalysisAgent

### fallback

请求 LLM、解析 JSON 或 schema 校验失败后，回退到 mock。

当前适用：

- JDAnalysisAgent

## 5. 当前 Guardrails

### ResumeParseAgent

- 保留原始简历文本。
- 信息不足时使用 `missing_info`，不编造经历。

### JDAnalysisAgent

- 不编造 JD 中不存在的信息。
- 不把加分项误判为必备项。
- LLM 输出必须通过 `JobAnalysis` schema 校验。

### MatchAgent

- 匹配分必须有证据。
- 缺失项必须来自 JD 和简历差距。

### ResumeOptimizeAgent

- 不编造经历、公司、项目、数据或技术栈。
- 需要量化但缺少数据时只提示补充。
- 不覆盖原始简历文本。

### ProjectInterviewAgent

- 追问必须基于简历项目和目标 JD。
- 暴露短板时给出可执行补强方向。

### ReportAgent

- 只聚合结构化结果，不重新分析业务。
- 报告必须保留风险和不能夸大的部分。

## 6. 测试要求

当前测试覆盖：

- Agent 元信息记录 `mode` 和 `guardrails`。
- JDAnalysisAgent LLM 失败时返回 `fallback`。
- workflow step trace 记录每一步的 `mode`。
- workflow step trace 记录 JDAnalysisAgent 的 `fallback_reason`。
- 保存分析记录时，workflow step trace 会写入 SQLite。
- 读取历史记录详情时，会返回已保存的 workflow step trace。
- fallback 后仍返回完整 `FinalReport`。

## 7. 面试官可能追问

- 你如何证明某一步用了 LLM 还是 mock？
- LLM 失败时系统怎么恢复？
- 为什么 fallback 只记录错误类型，不直接展示底层异常？
- guardrails 是写在 prompt 里，还是代码层也有约束？
- 后续 LangGraph 如何利用这些 trace 信息？
- 为什么 trace 只保存错误类型，不保存底层异常原文？

## 8. 后续方向

- 增加耗时统计。
- 增加 workflow run id。
- 区分 schema validation fallback 和 service failure fallback。
- 在 Streamlit 和 API 中增加更友好的 trace 过滤和摘要展示。
