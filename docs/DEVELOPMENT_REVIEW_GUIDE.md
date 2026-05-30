# JobAgent Development Review Guide

> 用途：作为项目开发、复盘、自查、面试准备和毕业设计答辩的总指导文档。它不只记录“做了什么”，还记录每个阶段为什么这样做、难在哪里、学什么、面试官可能怎么追问，以及开发时应该形成什么思维。

## 1. 总体学习目标

JobAgent 不只是一个能跑的项目，它要帮你建立完整的开发思维：

- 从需求边界出发，而不是一上来写代码。
- 先跑通最小闭环，再逐步引入复杂技术。
- 用 schema 稳定数据流，而不是随手传 dict。
- 用 service、agent、tool、storage 分层管理复杂度。
- 用测试和复盘保证项目可解释、可维护、可答辩。
- 面对面试追问时，能讲清楚取舍、难点、风险和改进方向。

第一阶段核心闭环：

```text
简历文本 + JD 文本 -> 结构化分析 -> 匹配报告 -> 简历优化 -> 项目追问 -> Markdown 报告
```

## 2. 开发者思维框架

每做一个功能，都按这个顺序想：

1. 用户输入是什么。
2. 系统输出是什么。
3. 中间需要哪些结构化数据。
4. 哪些逻辑属于 UI，哪些属于 service，哪些属于 agent。
5. 最小可运行版本是什么。
6. 如何证明它真的工作。
7. 面试官会质疑哪里。

不要先追求“功能多”，要先追求“链路清楚”。

## 3. 阶段 0：文档层和 AI 辅助开发层

### 阶段重点

- 固定项目边界。
- 明确 v0.1 只做 mock MVP。
- 写清楚不做自动投递、登录、验证码、复杂爬虫。
- 建立 `.ai/skills/` 和 `.ai/prompts/`，让后续 AI coding 不乱扩展。

### 开发难点

- 初学者容易把“想做的完整系统”和“第一版应该做的系统”混在一起。
- 容易为了看起来高级，过早加入 LangGraph、RAG、MCP、数据库。
- 文档容易写成空泛口号，而不是能指导代码的边界。

### 关键知识点

- PRD：定义做什么和不做什么。
- Architecture：定义系统怎么分层。
- Data Schema：定义数据如何流动。
- Roadmap：定义阶段性交付。
- Technical Decisions：记录为什么这么选型。

### 面试官可能追问

- 为什么第一版不用 LangGraph？
- 为什么不用数据库也能先做 MVP？
- 为什么要先写文档和 schema？
- 你的项目和普通简历优化工具有什么区别？
- 你如何防止 AI 编造简历经历？

### 自查问题

- 读完 PRD 后，别人是否知道 v0.1 只做什么？
- 架构文档是否能指导文件放在哪里？
- 数据模型是否能支撑后续 Agent 输出？
- 是否明确写了非 MVP 范围？

## 4. 阶段 1：Mock MVP

### 阶段重点

- 不接真实 LLM，也能端到端跑通。
- 用 mock pipeline 模拟 Agent 工作流。
- Streamlit 页面可以输入简历和 JD。
- 输出完整 Markdown 报告。
- 用测试保证核心 pipeline 不断。

### 开发难点

- mock 不能太假，必须遵守真实 schema。
- UI 不能堆业务逻辑。
- 报告不能只是字符串拼接，要来源于结构化数据。
- 初学者容易把所有东西写在 `streamlit_app.py` 里。

### 关键知识点

- Streamlit 基础。
- Pydantic schema。
- service layer。
- Markdown report generation。
- pytest 最小测试。
- 端到端数据流设计。

### 面试官可能追问

- 为什么先写 mock，而不是直接接大模型？
- mock pipeline 和真实 Agent 之间如何替换？
- 你的 schema 如何保证后续扩展？
- 如果用户输入很短或很乱，系统如何处理？
- 你的报告如何保证不是空泛模板？

### 自查问题

- 是否可以一条命令启动页面？
- 是否可以输入简历和 JD，看到完整报告？
- mock 输出是否符合 Pydantic schema？
- 业务逻辑是否放在 `app/services/`？
- 是否有至少一个测试覆盖主流程？

## 5. 阶段 2：接入真实 LLM

### 阶段重点

- 只先替换一个 Agent，建议从 JDAnalysisAgent 开始。
- LLM 输出必须走 schema 校验。
- 调用失败时回退 mock。
- 不影响现有 Streamlit 页面。

### 开发难点

- LLM 输出不稳定，可能不是合法 JSON。
- prompt 设计过宽会导致模型编造。
- schema 校验失败后要有 fallback。
- API key、模型配置、错误处理要和业务逻辑解耦。

### 关键知识点

- OpenAI-compatible API。
- prompt engineering。
- structured output。
- JSON parsing。
- Pydantic validation。
- retry and fallback。
- environment variables。

### 面试官可能追问

- 你如何保证 LLM 输出可被程序消费？
- LLM 返回非法 JSON 怎么办？
- 为什么第一个替换 JDAnalysisAgent？
- 如何避免模型把加分项误判成必备项？
- 你如何评估 LLM 分析质量？

### 自查问题

- LLM service 是否独立于 Agent？
- Agent 是否有 mock fallback？
- 输出是否必须经过 schema 校验？
- API key 是否没有写死在代码里？
- 失败时用户是否仍能得到可用结果？

## 6. 阶段 3：FastAPI 后端

### 阶段重点

- 把核心流程从本地页面变成后端 API。
- route 只负责请求响应。
- service 继续负责业务编排。
- 前端可以选择调用 API 或本地 service。

### 开发难点

- 初学者容易把业务逻辑写进 route。
- 请求 schema、响应 schema 和内部 schema 容易混乱。
- 错误处理不清晰会导致前端难以展示问题。
- API 粒度过细或过粗都会影响后续扩展。

### 关键知识点

- FastAPI route。
- request / response schema。
- dependency injection。
- HTTP status code。
- API error handling。
- frontend and backend separation。

### 面试官可能追问

- 为什么需要 FastAPI，Streamlit 不够吗？
- API route 和 service 的边界是什么？
- 如果 LLM 调用超时，API 如何返回？
- 如何设计 `/analyze/full` 这种端到端接口？
- 未来多用户时需要改哪些地方？

### 自查问题

- API 是否只做薄封装？
- service 是否可以被 API 和 Streamlit 共同复用？
- 错误响应是否清晰？
- 是否能用测试直接调用 API？

## 7. 阶段 4：SQLite 存储

### 阶段重点

- 保存岗位 JD、简历版本、匹配报告、项目追问。
- 从“一次性工具”升级到“可持续求职工作台”。
- 先做单用户或本地数据，不做复杂权限系统。

### 开发难点

- 数据库表和 Pydantic schema 之间容易混淆。
- 简历版本管理需要保留原始内容和优化内容。
- 报告内容既要能展示，也要能追溯来源。
- 不要一开始做完整用户系统。

### 关键知识点

- SQLite。
- ORM 或轻量 repository。
- migration 基本概念。
- data persistence。
- versioning。
- repository pattern。

### 面试官可能追问

- 为什么 SQLite 起步？
- 简历版本如何设计？
- 报告如何和 JD、简历关联？
- 如果用户重复上传同一 JD，如何去重？
- 后续迁移 PostgreSQL 难点在哪里？

### 自查问题

- 是否保存原始 JD 和结构化结果？
- 是否保存原始简历和优化建议？
- 数据访问是否集中在 `app/storage/`？
- 是否避免在 service 中直接散写 SQL？

## 8. 阶段 5：LangGraph 工作流

### 阶段重点

- 把普通 service pipeline 升级为显式多 Agent 工作流。
- 用 state 管理 Agent 之间的数据传递。
- 让流程更容易展示、调试和扩展。

### 开发难点

- 初学者容易为了用 LangGraph 而用 LangGraph。
- state 设计不清晰会让工作流变复杂。
- Agent 节点失败时需要错误处理和回退。
- 不要在 LangGraph 节点里塞太多业务逻辑。

### 关键知识点

- LangGraph state。
- node。
- edge。
- conditional routing。
- workflow orchestration。
- observability。

### 面试官可能追问

- 为什么后期才引入 LangGraph？
- 普通 pipeline 和 LangGraph 的区别是什么？
- state 里应该放什么，不应该放什么？
- 某个 Agent 失败后如何恢复？
- 你的 Agent 是否真的职责单一？

### 自查问题

- LangGraph 是否解决了真实复杂度？
- 每个 node 是否只做一件事？
- state 是否和 schema 对齐？
- 是否保留了 mock 或 fallback 路径？

## 9. 阶段 6：岗位数据库和 URL 添加

### 阶段重点

- 支持粘贴岗位 URL。
- 抓取简单网页文本。
- 提取 JD 并结构化入库。
- 支持岗位去重、标签和检索。

### 开发难点

- 网页结构不稳定。
- 不同招聘网站可能需要登录或反爬。
- 简单抓取和复杂爬虫边界要明确。
- URL 内容提取失败时要允许用户手动粘贴 JD。

### 关键知识点

- HTTP request。
- HTML parsing。
- text extraction。
- deduplication。
- job tagging。
- graceful degradation。

### 面试官可能追问

- 为什么不做复杂爬虫？
- URL 抓取失败怎么办？
- 如何判断两个 JD 是重复的？
- 岗位标签如何生成？
- 如何规避登录和验证码风险？

### 自查问题

- 是否明确不处理登录和验证码？
- 是否提供手动粘贴 JD 的 fallback？
- 岗位去重是否有可解释规则？
- 抓取逻辑是否在 tools 层？

## 10. 阶段 7：RAG、MCP、Tracker

### 阶段重点

- RAG 用于历史 JD、历史报告、面试题库检索。
- MCP 用于封装稳定工具能力。
- Tracker 用于管理投递状态、简历版本和下一步行动。

### 开发难点

- RAG 不是“接个向量库”就结束，关键是检索内容和评价指标。
- MCP 适合稳定工具，不适合过早封装变化中的逻辑。
- tracker 需要清晰状态机，否则会变成普通表格。

### 关键知识点

- embedding。
- vector database。
- retrieval quality。
- MCP tool design。
- application tracking。
- state machine。

### 面试官可能追问

- RAG 检索什么内容？
- 如何评估检索是否有帮助？
- MCP 封装哪些工具最合适？
- tracker 的状态有哪些？
- 如何把历史报告用于下一次优化？

### 自查问题

- RAG 是否有明确使用场景？
- MCP 是否封装了稳定能力？
- tracker 是否能指导下一步行动？
- 是否避免为了概念而堆技术？

## 11. 阶段 8：作品集和答辩版本

### 阶段重点

- 完善 README、架构图、Demo 截图、运行说明。
- 准备测试样例和演示脚本。
- 整理技术决策和复盘总结。
- 把项目讲成一个完整工程故事。

### 开发难点

- 初学者容易只展示页面，不会讲设计取舍。
- Demo 数据需要真实但不能泄露隐私。
- README 要突出边界、亮点和可运行性。
- 面试答辩要能承认不足并说明改进计划。

### 关键知识点

- technical storytelling。
- README writing。
- demo script。
- architecture diagram。
- project retrospective。

### 面试官可能追问

- 这个项目最难的部分是什么？
- 如果让你重构一次，你会先改哪里？
- 你如何证明这个项目不是 prompt demo？
- 你在项目中学到了什么工程能力？
- 未来如何产品化？

### 自查问题

- README 是否能让别人跑起来？
- 是否有清晰架构图？
- 是否有端到端 Demo 截图？
- 是否有测试和样例数据？
- 是否能讲清楚每个阶段的取舍？

## 12. 面试官拷打总清单

每完成一个阶段，都用这些维度自问：

### 需求和边界

- 这个功能解决了什么用户问题？
- 为什么现在做它？
- 为什么不做另一个看起来更高级的功能？
- MVP 边界是什么？

### 架构和分层

- 这段逻辑应该放 UI、service、agent、tool 还是 storage？
- 未来要替换 LLM 或数据库，会影响哪些层？
- 是否存在单文件过重或职责混乱？

### 数据和 schema

- 输入输出是否结构化？
- schema 是否保留原始文本？
- 数据是否能追溯来源？
- 信息缺失时如何表达？

### 可靠性

- 失败时如何回退？
- 用户输入异常时怎么办？
- LLM 输出不稳定怎么办？
- 有哪些最小测试？
- Agent trace 是否记录了 `mock`、`llm` 或 `fallback`？
- fallback 是否记录了原因类型，同时避免把底层异常原文暴露给用户？

### 真实性和伦理

- 是否编造简历经历？
- 是否误导用户投递？
- 是否处理了隐私数据？
- 自动化是否涉及平台风险？
- ResumeOptimizeAgent 是否明确保留“不编造经历、公司、项目、数据或技术栈”的 guardrail？

### 扩展性

- 后续接 FastAPI、SQLite、LangGraph 是否自然？
- 现在的设计哪里可能成为瓶颈？
- 哪些地方应该先保持简单？

## 13. 每次开发后的复盘模板

每完成一次开发，写 5 到 8 行即可：

```markdown
## 本轮复盘

- 本轮目标：
- 修改文件：
- 核心数据流：
- 遇到的难点：
- 学到的知识点：
- 面试官可能追问：
- 当前不足：
- 下一步：
```

## 14. 初学者最容易踩的坑

- 一上来接 LLM，结果数据流不稳定。
- 所有代码都写进 UI 文件。
- 没有 schema，导致后续 Agent 输出互相接不上。
- 为了高级感过早上 LangGraph、RAG、MCP。
- 简历优化时让 AI 编造经历。
- 不写测试，只靠手动点页面。
- README 只写运行命令，不写项目取舍。
- 面试时只说“用了什么技术”，说不清“为什么这样做”。

## 15. 本项目的讲述主线

面试或答辩时，可以按这条线讲：

```text
我发现求职者很难判断简历和 JD 的差距。
所以我先把问题拆成简历解析、JD 分析、匹配评分、简历优化和项目追问。
第一版没有直接接 LLM，而是先用 mock 跑通结构化数据流。
然后逐步把单个 Agent 替换为真实 LLM，并用 Pydantic 校验输出。
后续再接 FastAPI、SQLite、LangGraph、RAG 和 MCP。
整个项目的重点不是自动投递，而是让求职准备过程结构化、可复盘、可扩展。
```
