# Portfolio Pitch

> 用途：准备作品集、面试自我介绍和答辩讲述。

## 1 分钟项目介绍

JobAgent 是一个面向求职准备的本地工作台。它不是自动投递工具，而是帮助求职者把“简历和目标 JD 是否匹配、应该怎么优化、面试可能追问什么、投递进展到哪一步”结构化记录下来。

技术上，我用 Streamlit 做 Demo 页面，FastAPI 提供后端接口，Pydantic 固定 Agent 之间的数据结构，SQLite 保存分析记录、岗位库、简历版本和投递 tracker。主流程由 ResumeParse、JDAnalysis、Match、ResumeOptimize、ProjectChallenge 和 Report 六个 Agent 组成，并保存 workflow trace，方便复盘每次分析用了 mock、LLM 还是 fallback。

项目边界很明确：不做自动投递、招聘网站登录、验证码处理、复杂爬虫，也不让系统编造简历经历、公司、项目、数据或技术栈。

## 3 分钟项目介绍

JobAgent 的出发点是：求职者经常能写简历、看 JD，但很难稳定判断两者的差距，也很难把每次优化和投递动作沉淀下来。所以我没有从自动投递入手，而是先做一个本地求职准备工作台。

第一层是数据结构。我用 Pydantic 定义 `ResumeProfile`、`JobAnalysis`、`MatchReport`、优化建议、项目追问和最终报告，保证 UI、API、service、agent 之间传递的是稳定结构，而不是随手传 dict。

第二层是 Agent 边界。ResumeParseAgent 负责把简历文本结构化，JDAnalysisAgent 负责解析岗位，MatchAgent 负责评分，ResumeOptimizeAgent 只基于已有内容给优化建议，ProjectChallengeAgent 生成面试追问，ReportAgent 汇总 Markdown 报告。当前 JDAnalysisAgent 和 ResumeOptimizeAgent 支持可选 LLM，并且失败会 fallback 到 mock，避免模型不稳定影响主流程。

第三层是工程闭环。FastAPI route 保持薄封装，业务逻辑放在 service、agent、workflow、storage。Streamlit 只做展示和触发。SQLite 保存分析记录、岗位库、workflow trace、简历版本和投递 tracker。每次端到端分析都会生成 workflow trace，包括 run id、步骤、执行模式、耗时、fallback 原因和 guardrails。

最近我补了 txt/md 简历文件解析和稳定性增强。文件解析只把 UTF-8 `.txt` / `.md` 转成纯文本，再复用 ResumeParseAgent；默认最大 1MB，可通过环境变量调整。API 业务错误统一返回 `detail` 和 `error_code`，方便前端展示和调用方处理。

这个项目的重点不是堆技术名词，而是展示一个 AI 应用从需求边界、结构化数据流、可替换 Agent、fallback、存储复盘到测试验证的完整工程过程。

## 面试官可能追问与回答

### 为什么不做自动投递？

自动投递会碰到平台规则、登录、验证码、反爬和误投风险。这个项目的核心价值是求职准备和复盘，所以我把边界放在分析、记录和辅助决策，不替用户执行平台动作。

### 为什么第一版不直接上 LangGraph？

我先用显式 workflow 和 `WorkflowGraphSpec` 固定步骤、状态读写和 trace 契约。这样能先把业务边界和数据流跑稳，再考虑替换运行时框架，避免为了用框架而把业务逻辑写散。

### 为什么先只让 JDAnalysisAgent 和 ResumeOptimizeAgent 接 LLM？

JD 解析和简历优化的输入输出都比较清晰，适合逐步替换成可选 LLM。其他 Agent 先用 mock 跑稳数据流，能降低调试变量。LLM 失败时 fallback 到 mock，不影响主链路。

### 如何防止简历优化编造经历？

ResumeOptimizeAgent 的职责是基于已有简历和 JD 给表达优化建议，而不是生成不存在的经历。项目文档、guardrails 和版本管理都强调不编造公司、项目、数据或技术栈，定制版本也保存用户确认后的文本。

### 为什么文件上传只支持 txt/md？

txt/md 可以稳定按 UTF-8 转纯文本，依赖小、行为可控。PDF/DOCX 的提取质量、依赖体积和隐私风险都需要单独评估，所以放到后续计划。

### API route 和 service 的边界是什么？

route 只处理请求、响应和 HTTP 错误映射。文件校验、大小限制、文本提取放在 service；结构化解析放在 Agent；完整分析编排放在 workflow；持久化放在 storage。

### 为什么要保存 workflow trace？

trace 能解释一次结果是怎么来的。它记录每个 Agent 的执行模式、耗时、fallback 和 guardrails，方便排查问题，也方便在面试或答辩中说明系统不是一个黑盒 prompt demo。

### 后续如何扩展？

短期可以补截图、部署说明和更完整的错误码文档。中期再做 LangGraph 原型、历史报告检索或更完整的评估体系。扩展时仍然保持边界：不做自动投递、登录、验证码和复杂爬虫。
