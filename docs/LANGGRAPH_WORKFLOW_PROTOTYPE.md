# LangGraph Workflow Prototype

本轮新增的是一个最小可运行的 LangGraph workflow 原型，用来验证 JobAgent 现有 6 个 Agent 怎样映射到 graph node、怎样维护统一 state、怎样保留 `mock / llm / fallback` trace，以及怎样加入最小条件分支。

注意：当前 LangGraph 版本只是 prototype，不替换默认的 [job_analysis_workflow](../app/workflows/job_analysis_workflow.py)。现有主流程依然是默认入口，LangGraph 版本是并行存在的实验实现。

## 为什么现在引入 LangGraph

当前项目已经具备：

- 明确的 Agent 边界
- 统一的 workflow state
- `WorkflowStepTrace`
- `mock / llm / fallback` 执行模式
- 可以稳定跑通的默认 Python workflow

这意味着我们已经有足够清晰的输入输出契约，可以开始验证 graph orchestration，而不是在边界还不稳的时候直接切主链路。

## 为什么不替换原有 workflow

本轮目标是“验证编排方式”，不是“切换生产主路径”。

保留原有 workflow 的原因：

- 当前默认 workflow 已经被现有 API、Streamlit、SQLite 记录和 pytest 覆盖保护
- LangGraph 原型还没有接入更复杂的交互节点
- 本轮只需要证明 graph 结构、分支和 trace 兼容性，不需要承担默认入口风险

因此现在采取“双轨并存”：

- 默认入口：`run_job_analysis_workflow(...)`
- 原型入口：`run_langgraph_job_analysis_workflow(...)`

## 当前 graph 节点

当前原型包含这些节点：

1. `resume_parse`
2. `jd_analysis`
3. `match`
4. `route_by_match_score`
5. `resume_optimize`
6. `project_challenge`
7. `low_match_prepare`
8. `report`

其中 6 个核心 Agent 仍然复用现有实现：

- ResumeParseAgent
- JDAnalysisAgent
- MatchAgent
- ResumeOptimizeAgent
- ProjectInterviewAgent
- ReportAgent

额外的 `route_by_match_score` 和 `low_match_prepare` 是 orchestration 节点，不复制 Agent 业务逻辑。

## 当前条件分支

主路径：

```text
ResumeParse
-> JDAnalysis
-> Match
-> route_by_match_score
-> ResumeOptimize
-> ProjectChallenge
-> Report
```

低匹配路径：

```text
ResumeParse
-> JDAnalysis
-> Match
-> route_by_match_score
-> low_match_prepare
-> Report
```

分支规则：

- `match_report.overall_score < 50`：进入 `low_match_prepare`
- 否则：进入标准增强路径

## 低匹配路径为什么还要 prepare

当前 `FinalReport` 仍然要求：

- `optimization_result`
- `project_challenge_report`

所以低匹配路径不能直接跳过这两个结构，否则会破坏现有 schema 和报告生成契约。

当前做法是：

- 用 `mock_resume_optimization(...)` 生成基础优化建议
- 用 `mock_project_challenge(...)` 生成基础项目追问
- 在 trace 中明确标记这是 `low-match preparation`

这样可以同时满足：

- 不破坏 `FinalReport`
- 不误报“真的执行了标准 ResumeOptimize / ProjectChallenge 节点”
- 不让低匹配分支把流程打崩

## 与原 Python workflow 的关系

二者共享：

- 同一套 Agent
- 同一套 schema
- 同一套 `WorkflowStepTrace` 结构
- 同样的 `mock / llm / fallback` 执行模式
- 同样的 LLM service 注入方式

差异在于：

- 原 Python workflow 是显式顺序调用
- LangGraph prototype 把节点关系和分支规则显式建模成 graph
- LangGraph prototype 额外暴露 `route_decision`

## 当前限制

本轮 prototype 明确不做：

- RAG
- MCP
- 自动投递
- 默认替换生产主流程
- 多用户权限系统
- JD URL 导入
- Docker

也不改变现有安全边界：

- 不能编造简历经历、公司、项目、数据或技术栈
- LLM 失败时必须 fallback，不能让主流程中断

## 后续计划

后续如果继续沿 LangGraph 方向推进，优先考虑：

1. human-in-the-loop 节点
2. 用户补充信息节点
3. 多岗位分支或多 JD 批量分析分支
4. RAG 检索历史简历版本和岗位 JD

## 如何单独运行

原型入口：

```python
from app.workflows.langgraph_job_analysis_workflow import run_langgraph_job_analysis_workflow

result = run_langgraph_job_analysis_workflow(
    resume_text="...",
    jd_text="...",
    use_llm_jd=False,
    use_llm_resume_optimize=False,
    use_llm_project_challenge=False,
)
```

如果环境里还没有安装 `langgraph`，函数会抛出明确错误，提醒先安装依赖。
