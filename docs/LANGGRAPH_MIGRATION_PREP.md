# LangGraph Migration Prep

> 用途：记录 JobAgent 从显式 workflow 迁移到 LangGraph 前的准备设计。当前阶段不引入 LangGraph 依赖，也不替换稳定主链路，而是先把 node、edge、state 读写和契约固定下来。

## 1. 当前目标

把现有线性 workflow 映射成可测试的 graph spec：

```text
JobAnalysisWorkflowState
-> WorkflowGraphSpec
-> 未来 LangGraph StateGraph
```

当前新增代码：

```text
app/workflows/graph_spec.py
tests/test_graph_spec.py
```

## 2. 为什么先做 graph spec

如果直接把 `run_job_analysis_workflow` 改成 LangGraph，容易把三类变化混在一起：

- 业务流程变化。
- 框架接入变化。
- API、Streamlit、storage 契约变化。

当前阶段只做迁移准备，保持已有主链路稳定：

- `/analyze/full` 响应结构不变。
- Streamlit 调用方式不变。
- SQLite trace 表不变。
- `run_mock_pipeline` 兼容入口不变。
- fallback 仍然留在 Agent 边界内。

## 3. Node 映射

| node_id | Agent | reads | writes | 备注 |
| --- | --- | --- | --- | --- |
| `resume_parse` | `ResumeParseAgent` | `resume_text` | `resume_profile` | 解析原始简历文本 |
| `jd_analysis` | `JDAnalysisAgent` | `jd_text`, `use_llm_jd` | `job_analysis` | 当前唯一可选 LLM node，失败回退 mock |
| `match` | `MatchAgent` | `resume_profile`, `job_analysis` | `match_report` | 生成匹配分和差距 |
| `resume_optimize` | `ResumeOptimizeAgent` | `resume_text`, `resume_profile`, `job_analysis`, `match_report` | `optimization_result` | 不编造经历，只给真实优化建议 |
| `project_interview` | `ProjectInterviewAgent` | `resume_profile`, `job_analysis` | `project_challenge_report` | 生成项目追问 |
| `report` | `ReportAgent` | 上游结构化结果 | `markdown_report` | 聚合报告，不重新分析业务 |

## 4. Edge 映射

当前仍保持线性顺序：

```text
resume_parse
-> jd_analysis
-> match
-> resume_optimize
-> project_interview
-> report
```

这不是因为未来一定只能线性，而是为了先保护稳定主链路。后续如果引入条件分支，比如 LLM fallback 路由、人工确认、RAG 检索，可以在 graph spec 里逐步扩展。

## 5. 收紧后的开发要求

- 新增或调整 workflow step 时，必须同步更新 `graph_spec.py`。
- `graph_spec.py` 必须通过测试证明和真实 workflow step 顺序一致。
- graph node 不直接写 SQLite。
- graph node 不包含 Streamlit 展示逻辑。
- fallback 先留在 Agent 内部，除非后续明确需要 graph 级条件路由。
- 不为了“用了 LangGraph”而引入框架；必须先能解释框架解决的真实复杂度。

## 6. 测试要求

当前测试覆盖：

- graph spec 的 Agent 顺序和真实 workflow step 顺序一致。
- node id 和 edge 顺序保持稳定。
- 每个 node 声明自己的 state reads/writes。
- `jd_analysis` 明确允许 LLM，并保留 mock fallback。
- graph spec 可以输出稳定 Mermaid 图。
- graph spec validation 会拒绝非线性 edge。

## 7. 面试官可能追问

- 为什么不直接把主流程改成 LangGraph？
- `WorkflowGraphSpec` 和真正的 LangGraph `StateGraph` 有什么关系？
- 每个 node 的输入输出怎么从 state 里取？
- fallback 应该放在 Agent 内部，还是 graph 条件分支里？
- 如果未来要并行执行哪些 node 可以并行？
- 迁移 LangGraph 后，API 和 Streamlit 为什么不需要大改？
