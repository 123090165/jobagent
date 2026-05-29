# Agent Workflow Skill

> 用途：约束 JobAgent 的 Agent 设计，确保每个 Agent 职责单一、输入输出结构化、可替换、可测试。

## Agent 设计规则

1. 每个 Agent 只负责一个明确任务。
2. Agent 输入输出必须结构化。
3. 不要让一个 Agent 同时做解析、评分、优化和报告。
4. 每个 Agent 都应该可以被单独测试。
5. Agent 输出必须能被下游 Agent 使用。
6. 第一版可以 mock，后续再替换为真实 LLM。
7. 真实 LLM 输出必须有 JSON / schema 校验和失败回退。

## 推荐 Agent

- ResumeParseAgent
- JDAnalysisAgent
- MatchAgent
- ResumeOptimizeAgent
- ProjectInterviewAgent
- ReportAgent

## 推荐工作流

```text
START
-> ResumeParseAgent
-> JDAnalysisAgent
-> MatchAgent
-> ResumeOptimizeAgent
-> ProjectInterviewAgent
-> ReportAgent
-> END
```

## 约束

- 简历优化不得编造事实。
- 匹配分析必须给出证据。
- 项目拷打必须具体，不能泛泛提问。
- 报告必须给出可执行建议。
- 信息不足时返回缺失项，而不是补充虚构内容。

## 真实 LLM 接入原则

1. 一次只替换一个 Agent。
2. 先替换 JDAnalysisAgent，因为 JD 文本通常更标准。
3. LLM 输出必须经过 Pydantic 校验。
4. 校验失败时返回错误信息或回退 mock。
5. 不影响现有 Streamlit 页面和 mock pipeline。
