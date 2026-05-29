# Implement Feature Prompt

> 用途：实现具体功能时使用，帮助 AI 明确层级、边界、交付物和测试方式。

我要为 JobAgent 实现一个新功能：[功能名]。

请按以下方式工作：

1. 先判断这个功能属于哪一层：
   - frontend
   - api
   - service
   - agent
   - tool
   - storage
   - evaluation

2. 给出最小实现方案。

3. 遵守项目边界：
   - 不引入不必要依赖。
   - 不大规模重构。
   - 不做自动投递相关内容。
   - 不破坏现有流程。

4. 实现时优先保持结构清晰：
   - schema 放 `app/schemas/`
   - 业务逻辑放 `app/services/`
   - Agent 逻辑放 `app/agents/`
   - 工具函数放 `app/tools/`
   - API 放 `app/api/`

5. 输出：
   - 修改文件列表。
   - 关键实现说明。
   - 如何运行。
   - 如何测试。
   - 后续可扩展点。
