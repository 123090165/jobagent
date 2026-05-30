# JobAgent Roadmap

> 用途：把开发拆成可执行版本，避免一开始做大而全。

## 当前优先级

当前已经完成 Mock MVP、可选 LLM JDAnalysisAgent、FastAPI、SQLite、岗位库、tracker、简历版本管理、显式 workflow 编排层、mock Agent 外壳、Agent trace 元信息和 workflow trace 持久化。下一步优先继续加强架构可观察性和后续 LangGraph 迁移准备，而不是扩展自动投递或复杂爬虫。

核心目标：

```text
简历 + JD -> 匹配报告 + 简历优化建议 + 项目追问 + Markdown 报告
```

## v0.1 Mock MVP

交付物：

- Streamlit 页面。
- 简历文本输入。
- JD 文本输入。
- Pydantic schema。
- mock 简历解析。
- mock JD 分析。
- mock 匹配报告。
- mock 简历优化。
- mock 项目追问。
- Markdown 报告生成。
- 最小测试。

不做：

- 真实 LLM。
- 数据库。
- LangGraph。
- 自动投递。

## v0.2 LLM MVP

交付物：

- OpenAI-compatible LLM service。
- Agent prompt 模板。
- JSON structured output。
- schema validation。
- 错误重试和 mock fallback。
- 先替换 JDAnalysisAgent，再逐步替换其他 Agent。

## v0.3 FastAPI + SQLite

交付物：

- FastAPI 后端。
- SQLite 数据库。
- 保存 JD。
- 保存简历版本。
- 保存匹配报告。
- 保存项目追问。
- 第一批 API。

## v0.4 LangGraph Workflow

交付物：

- `JobAgentState`。
- 多 Agent 节点。
- 状态流转。
- 日志和错误处理。
- 可视化或可追踪的工作流执行结果。

## v0.5 Job Database

交付物：

- URL 添加 JD。
- 简单网页文本抓取。
- 岗位去重。
- 岗位标签。
- 岗位搜索接口。
- 历史岗位对比。

边界：

- 不处理登录。
- 不处理验证码。
- 不做复杂反爬。

## v0.6 Interview + Tracker

交付物：

- 项目拷打增强。
- 模拟面试流程。
- 投递 tracker。
- 简历版本管理。
- 一周行动计划。
- 面试反馈记录。

## v0.7 Workflow Architecture

交付物：

- `app/workflows/` 显式编排层。
- 将当前 service pipeline 拆成可追踪步骤。
- `JobAnalysisWorkflowState`。
- `WorkflowStepTrace`。
- 保持 `run_mock_pipeline` 外部契约不变。
- 保持现有 schema 和 fallback 路径。
- 为后续 LangGraph 节点迁移做准备。

## v0.8 Agent Boundary Cleanup

交付物：

- 补齐 ResumeParseAgent、MatchAgent、ResumeOptimizeAgent、ProjectChallengeAgent、ReportAgent 的 mock agent 外壳。
- 将 workflow 中的步骤调用逐步迁移到 agent 层。
- 每个 Agent 只负责一个结构化输入输出。
- 保持现有 service、API 和 Streamlit 调用方式不变。

## v0.9 Agent Trace and Fallback Metadata

交付物：

- 记录每个 Agent 的执行模式：mock、LLM、fallback。
- 在 workflow step trace 中展示 fallback 来源。
- 为 LLM Agent 失败原因保留可调试摘要。
- 不把底层异常直接暴露给用户。

## v0.10 Workflow Trace Persistence

交付物：

- 将 workflow step trace 保存到 SQLite。
- 分析记录详情可以展示每一步执行模式。
- 支持排查某次分析是否发生 LLM fallback。
- 不记录敏感底层异常原文。

状态：已完成。

## v0.11 Workflow Observability Cleanup

交付物：

- 为 workflow step trace 增加更清晰的摘要展示。
- 梳理 API、Streamlit、storage 对 trace 字段的边界。
- 增加 `workflow_run_id`、`duration_ms` 和 Streamlit trace 摘要展示。
- 保持 workflow 不直接写数据库、UI 不直接写 SQL。

状态：已完成。

## v0.12 LangGraph Migration Prep

交付物：

- 对照现有 `WorkflowStepTrace` 和 `JobAnalysisWorkflowState`，设计 LangGraph node 映射表。
- 保持现有 API、Streamlit 和 storage 契约不变。
- 先做迁移文档和最小实验，不急于替换稳定主链路。
- 继续保留 mock/fallback 路径。

## v1.0 Portfolio Version

交付物：

- 完整 README。
- Demo 截图。
- 架构图。
- 测试样例。
- Docker。
- 部署说明。
- 毕业设计说明材料。

## 版本推进原则

- 每个版本只解决一个主要问题。
- 先让数据流稳定，再接复杂能力。
- 新能力必须能回退，不破坏已有 MVP。
- 用户简历真实性优先于漂亮输出。
