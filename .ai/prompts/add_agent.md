# Add Agent Prompt

> 用途：新增 Agent 时使用，确保职责、schema、prompt、mock、测试和工作流位置都明确。

我要为 JobAgent 新增一个 Agent：[AgentName]。

请完成：

1. 明确 Agent 职责。
2. 定义输入 schema。
3. 定义输出 schema。
4. 写 system prompt。
5. 先写 mock 实现。
6. 预留真实 LLM 调用接口。
7. 说明它在工作流中的位置。
8. 给出测试样例。

约束：

- 一个 Agent 只做一个明确任务。
- 输出必须结构化。
- 不要编造用户简历经历。
- 如果信息不足，应返回 `missing_info` 或 suggestions，而不是假设事实。
- 不要为了新增 Agent 大规模改动项目结构。
