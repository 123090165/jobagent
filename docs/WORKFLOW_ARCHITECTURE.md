# Workflow Architecture

> 用途：记录 JobAgent 当前的显式工作流编排层。它是从普通 service pipeline 迁移到 LangGraph 之前的过渡层，用来稳定步骤边界、状态结构和可观察性。

## 1. 当前目标

当前目标不是马上引入 LangGraph，而是先把主链路拆成可追踪步骤：

```text
ResumeParseAgent
-> JDAnalysisAgent
-> MatchAgent
-> ResumeOptimizeAgent
-> ProjectInterviewAgent
-> ReportAgent
```

每一步都写入 `WorkflowStepTrace`，并聚合到 `JobAnalysisWorkflowState`。

## 2. 代码位置

```text
app/workflows/
  __init__.py
  job_analysis_workflow.py
```

现有入口仍然兼容：

```python
from app.services.mock_pipeline import run_mock_pipeline
```

`run_mock_pipeline` 现在委托给：

```python
from app.workflows.job_analysis_workflow import run_job_analysis_workflow
```

这样 Streamlit、FastAPI 和旧测试不需要改调用方式。

当前 workflow 调用 `app/agents/` 中的 Agent 外壳，而不是直接调用底层 mock 函数。

## 3. 核心对象

### WorkflowStepTrace

记录一次步骤执行：

- `name`
- `status`
- `mode`
- `summary`
- `fallback_reason`
- `guardrails`

### JobAnalysisWorkflowState

保存工作流运行状态：

- 原始输入：`resume_text`、`jd_text`
- 配置：`use_llm_jd`
- 中间结果：`resume_profile`、`job_analysis`、`match_report`
- 下游结果：`optimization_result`、`project_challenge_report`、`markdown_report`
- 执行轨迹：`steps`

### JobAnalysisWorkflowResult

返回：

- `final_report`
- `state`

## 4. 当前边界

- 不引入 LangGraph。
- 不改变 API 响应结构。
- 不改变 Streamlit 调用入口。
- 不改变 mock pipeline 的外部契约。
- 不在 workflow 里直接写数据库。
- 不在 workflow 里做 UI 展示逻辑。

## 5. 为什么先做这一层

直接把现有函数迁移到 LangGraph，容易把业务逻辑、状态结构和框架用法搅在一起。

先做显式 workflow 有几个好处：

- 步骤顺序可以被测试保护。
- 每一步输入输出更清楚。
- 后续替换某个 Agent 更容易。
- LangGraph 迁移时可以按步骤映射成 node。
- 面试时能讲清楚“为什么不是为了用框架而用框架”。

## 6. 测试重点

当前测试覆盖：

- workflow 能返回完整 `FinalReport`。
- workflow 会记录 6 个步骤。
- workflow 步骤通过 Agent 外壳执行。
- workflow 步骤必须记录执行模式和 guardrails。
- JDAnalysisAgent fallback 时必须记录 fallback 原因。
- `run_mock_pipeline` 委托给 workflow 后外部契约不变。
- 空输入仍然抛出清晰错误。

## 7. 面试官可能追问

- 为什么不直接上 LangGraph？
- workflow state 里应该放什么，不应该放什么？
- 现在的 workflow 和 service 层边界是什么？
- 后续每个步骤如何迁移成 LangGraph node？
- 某个 Agent 失败后应该在哪里处理 fallback？

## 8. 后续方向

- 把 mock Agent 外壳从 service 进一步拆到 `app/agents/`。
- 给每个步骤补充耗时。
- 增加 workflow run id，方便和分析记录关联。
- 将 trace 写入 SQLite。
- 在 LangGraph 版本中复用当前 state 字段和步骤名称。
