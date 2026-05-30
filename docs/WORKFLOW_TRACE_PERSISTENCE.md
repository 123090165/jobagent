# Workflow Trace Persistence

> 用途：记录 JobAgent 如何把 workflow step trace 保存到 SQLite，并通过 API 和 Streamlit 展示。它让每次分析都能追溯每个 Agent 使用的是 `mock`、`llm` 还是 `fallback`。

## 1. 当前目标

把一次分析的执行轨迹从运行时内存变成可复盘数据：

```text
run_job_analysis_workflow
-> WorkflowStepTrace[]
-> workflow_step_traces
-> GET /records/{record_id}
-> Streamlit 历史记录详情
```

## 2. 数据表

新增表：

```text
workflow_step_traces
```

字段：

- `analysis_record_id`
- `workflow_run_id`
- `step_index`
- `agent_name`
- `status`
- `mode`
- `summary`
- `duration_ms`
- `fallback_reason`
- `guardrails_json`
- `created_at`

## 3. API 行为

`POST /analyze/full` 现在返回：

```json
{
  "record_id": 1,
  "workflow_steps": [
    {
      "workflow_run_id": "f4d8a2d0c7f24d5a9c4d3f6c4b2a1e90",
      "name": "ResumeParseAgent",
      "status": "completed",
      "mode": "mock",
      "summary": "识别技能 6 个，项目 1 个。",
      "duration_ms": 1.2,
      "fallback_reason": null,
      "guardrails": ["保留原始简历文本"]
    }
  ]
}
```

当 `save_result=true` 时，`workflow_steps` 会和分析记录一起保存。

`GET /records/{record_id}` 会返回同一组 `workflow_steps`。

## 4. Streamlit 行为

- “生成报告”页会在结构化结果中展示执行轨迹。
- “历史记录”详情新增“执行轨迹”页。
- 执行轨迹会显示步骤数、总耗时、fallback 数和 `workflow_run_id`。
- 旧记录如果没有 workflow trace，会提示“这条历史记录没有保存 workflow trace”。

## 5. 收紧后的开发要求

- 新增分析入口时，必须优先走 `run_job_analysis_workflow`。
- 保存分析记录时，必须同时传入 `workflow_steps`。
- 每次 workflow run 必须生成稳定的 `workflow_run_id`，每个 step 必须记录 `duration_ms`。
- trace 只能记录错误类型或摘要，不记录敏感底层异常原文。
- workflow 仍然不能直接写数据库，持久化只在 storage service/repository 层完成。
- API route 只负责调用 workflow 和 storage，不写 SQL。

## 6. 测试要求

当前测试覆盖：

- 保存分析记录时能写入 workflow steps。
- 读取分析记录时能返回 workflow steps。
- `POST /analyze/full` 响应包含 workflow steps。
- workflow、API 和 storage 都能返回 `workflow_run_id` 和 `duration_ms`。
- 旧的 `run_mock_pipeline` 契约不变。

## 7. 面试官可能追问

- 如何证明某次分析是否用了 LLM？
- 如果 LLM 失败，你如何在历史记录中看出来？
- 为什么不把底层异常原文保存进数据库？
- `workflow_run_id` 和分析记录 ID 的区别是什么？
- 为什么要先记录 step 耗时，再考虑更复杂的 tracing 系统？
- workflow 为什么不直接写 SQLite？
- 后续 LangGraph 如何复用这张 trace 表？
