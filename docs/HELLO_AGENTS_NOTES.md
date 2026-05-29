# Hello-Agents Notes for JobAgent

> 用途：把 Hello-Agents 课程知识点映射到 JobAgent，方便毕业设计、README 和答辩说明。

## 1. ReAct / Agent Loop

JobAgent 中的 MatchAgent、ResumeOptimizeAgent、ProjectInterviewAgent 都可以理解为具备推理能力的 Agent。

对应方式：

- 根据输入材料分析目标。
- 判断需要提取哪些信息。
- 调用工具或 schema。
- 生成结构化输出。
- 交给下游 Agent 使用。

v0.1 暂不实现完整 ReAct loop，只保留可替换的 Agent 边界。

## 2. Tool Calling

JobAgent 后续可封装的工具：

- `resume_reader`
- `resume_parser`
- `jd_parser`
- `url_fetcher`
- `keyword_extractor`
- `report_writer`
- `database_tool`

v0.1 先用普通 Python 函数模拟工具能力。

## 3. Multi-Agent

JobAgent 将求职任务拆分为多个专用 Agent：

- ResumeParseAgent 负责简历解析。
- JDAnalysisAgent 负责 JD 分析。
- MatchAgent 负责匹配判断。
- ResumeOptimizeAgent 负责简历优化。
- ProjectInterviewAgent 负责项目追问。
- ReportAgent 负责报告汇总。

这种拆分可以减少单个 Agent 的职责混乱，也方便测试和替换。

## 4. RAG

后期 RAG 的用途：

- 检索历史 JD。
- 检索历史匹配报告。
- 检索面试题库。
- 分析岗位技能趋势。
- 生成更个性化的补强建议。

v0.1 不做 RAG，先保留岗位和报告的数据结构。

## 5. MCP

后期可以将这些能力封装成 MCP tools：

- 文件读取。
- 岗位搜索。
- 岗位数据库查询。
- 报告生成。
- tracker 查询。

MCP 放在后期，因为 v0.1 的关键是跑通核心业务闭环。

## 6. Evaluation

JobAgent 的评估重点：

- 输出格式是否符合 schema。
- 是否基于用户简历和 JD。
- 是否编造用户经历。
- 匹配分是否有证据。
- 建议是否具体可执行。
- 项目追问是否有深度。
- 端到端流程是否稳定。

## 7. 为什么适合作为毕业设计

- 有明确真实场景。
- 能覆盖 Agent、工具调用、多 Agent、RAG、MCP 和评估等课程知识点。
- 可以从 MVP 逐步扩展到完整系统。
- 最终成果适合放进 GitHub、简历和答辩材料。
