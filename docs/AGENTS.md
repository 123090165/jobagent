# JobAgent Agents

> 用途：明确每个 Agent 的职责、输入、输出和边界，避免出现什么都做的超级 Agent。

## 1. 设计原则

1. 一个 Agent 只负责一类明确任务。
2. Agent 输入输出必须结构化。
3. Agent 输出必须能被下游消费。
4. 第一版可以 mock，后续再逐个替换为真实 LLM。
5. 不允许在简历优化中编造用户经历。
6. 信息不足时返回缺失项和建议，而不是假设事实。

## 2. Agent 列表

| Agent | 职责 | 输入 | 输出 |
|---|---|---|---|
| ProfileAgent | 构建用户画像 | 用户目标、简历摘要、偏好 | UserProfile |
| ResumeParseAgent | 解析简历 | 简历文本或文件内容 | ResumeProfile |
| JDAnalysisAgent | 分析 JD | 原始 JD、岗位标题、公司、URL | JobAnalysis |
| MatchAgent | 匹配分析 | ResumeProfile + JobAnalysis + UserProfile | MatchReport |
| ResumeOptimizeAgent | 简历优化 | 原始简历 + MatchReport + JobAnalysis | ResumeOptimizationResult |
| ProjectInterviewAgent | 项目拷打 | 项目经历 + JobAnalysis | ProjectChallengeReport |
| ReportAgent | 汇总报告 | 上游所有结构化结果 | FinalReport / Markdown |

## 3. 主工作流

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

## 4. ResumeParseAgent

职责：

- 从简历文本中提取教育经历、技能、项目、工作经历、证书和亮点。
- 保留原始文本。
- 标记缺失信息。

边界：

- 不评价岗位匹配度。
- 不改写简历。
- 不补充简历中不存在的信息。

## 5. JDAnalysisAgent

职责：

- 将 JD 解析为岗位职责、必备技能、加分技能、经验要求、学历要求、软技能和关键词。
- 区分必备项和加分项。
- 保留 JD 原文。

边界：

- 不自动搜索岗位。
- 不补充 JD 中没有的公司或待遇信息。
- 不做简历匹配评分。

## 6. MatchAgent

职责：

- 比较简历和 JD。
- 输出总分、技能分、项目分、经验分和关键词覆盖率。
- 列出匹配优势、缺失能力、风险和证据。
- 给出是否建议投递。

边界：

- 不改写简历。
- 不生成面试问题。
- 不为了鼓励用户而盲目给高分。

## 7. ResumeOptimizeAgent

职责：

- 根据 JD 和匹配报告提出简历优化建议。
- 生成更岗位相关的表达建议。
- 标记不可夸大的内容和需要用户补充的信息。

边界：

- 不编造用户没有提供的经历、公司、项目、数据或技术栈。
- 不覆盖原始简历。
- 不负责最终报告排版。

## 8. ProjectInterviewAgent

职责：

- 针对简历项目和目标岗位生成技术追问。
- 输出考察点、面试官可能质疑点、回答框架和补强建议。

边界：

- 不问泛泛问题。
- 不攻击用户。
- 不编造项目细节。

## 9. ReportAgent

职责：

- 汇总用户画像、简历分析、JD 分析、匹配报告、优化建议和项目追问。
- 生成可读的 Markdown 报告。
- 给出一周行动计划。

边界：

- 不重新做上游 Agent 的分析。
- 不添加上游结果没有支持的事实。
- 不输出空泛鸡汤。
