# Technical Decisions

> 用途：记录关键技术决策，避免后续开发反复摇摆。

## Decision 1: 第一版使用 Streamlit

原因：

- 快速做 Demo。
- 降低前端复杂度。
- 重点放在 Agent 和业务流程。
- 适合毕业设计和简历展示时快速演示。

后续：

- 如果需要更完整的产品体验，再迁移到 Next.js 或其他前端框架。

## Decision 2: 第一版不做自动投递

原因：

- 涉及招聘平台规则、账号风险和验证码。
- 工程稳定性差。
- 不是毕业设计核心。
- 容易把项目重点带偏。

后续：

- 可以做半自动投递助手，但不作为 v0.1 能力。

## Decision 3: 先 mock，再接 LLM

原因：

- 先稳定数据流和 schema。
- 避免早期被 API 调用、JSON 解析和模型波动拖慢。
- mock pipeline 更容易测试端到端流程。

后续：

- 先替换 JDAnalysisAgent，再逐步替换其他 Agent。

## Decision 4: 使用 Pydantic

原因：

- 核心输出需要结构化。
- 方便测试。
- 方便前端展示。
- 方便后续 API、数据库和 LLM 输出校验。

约定：

- schema 放在 `app/schemas/`。
- service 和 agent 之间传递 schema 实例。

## Decision 5: 后续使用 LangGraph

原因：

- 多 Agent 状态管理更清晰。
- 适合展示 Agent 工作流。
- 和当前主流 Agent 工程实践接近。

取舍：

- v0.1 不引入 LangGraph。
- 等 mock pipeline 和 schema 稳定后再迁移。

## Decision 6: SQLite 起步

原因：

- 本地开发简单。
- 适合毕业设计和单用户 Demo。
- 方便保存 JD、简历版本、报告和项目追问。

后续：

- 如果需要多用户和部署，再迁移 PostgreSQL。

## Decision 7: MCP 放后期

原因：

- MCP 适合封装稳定工具能力。
- v0.1 阶段工具边界还在变化。
- 过早接入会增加复杂度。

后续：

- 将文件读取、岗位数据库查询、报告生成、tracker 查询封装为 MCP tools。

## Decision 8: 简历真实性优先

原因：

- 求职场景中编造经历风险很高。
- 简历优化的价值在于更清晰表达真实经历，而不是制造不存在的亮点。

约定：

- 所有优化建议必须基于用户输入。
- 缺少信息时提示用户补充。
- 不生成虚假的公司、项目、数据、技术栈或结果。
