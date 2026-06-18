# JobAgent 开发准备包 v2

这一版目标：不要把项目准备成一堆空泛文档，而是整理成一个真正能放进 GitHub 仓库、能辅助 vibe coding、能支撑毕业设计和简历展示的开发准备包。

---

# 0. 项目定位

## 项目名称

**JobAgent**

## 一句话定义

JobAgent 是一个面向求职者的多智能体求职工作台，基于用户画像、岗位 JD 数据库和简历内容，帮助用户完成岗位搜集、JD 分析、简历优化、项目追问、模拟面试和求职计划管理。

## 项目核心闭环

```text
用户画像 → 岗位搜集/JD 入库 → JD 分析 → 简历分析 → 匹配度判断 → 简历优化 → 项目拷打 → 面试准备 → 求职记录
```

## 第一阶段核心目标

先跑通：

```text
用户输入简历 + JD → 系统输出匹配报告 + 简历优化建议 + 项目追问问题
```

---

# 1. 推荐仓库结构

```text
jobagent/
├── app/
│   ├── main.py
│   ├── api/
│   ├── agents/
│   ├── schemas/
│   ├── services/
│   ├── tools/
│   ├── storage/
│   └── evaluation/
│
├── frontend/
│   └── streamlit_app.py
│
├── docs/
│   ├── PRD.md
│   ├── ARCHITECTURE.md
│   ├── DATA_SCHEMA.md
│   ├── AGENTS.md
│   ├── ROADMAP.md
│   ├── REFERENCES.md
│   ├── HELLO_AGENTS_NOTES.md
│   ├── EXAMPLE_PROJECTS.md
│   └── DECISIONS.md
│
├── .ai/
│   ├── skills/
│   │   ├── project_rules.md
│   │   ├── python_backend.md
│   │   ├── agent_workflow.md
│   │   └── evaluation.md
│   └── prompts/
│       ├── bootstrap.md
│       ├── implement_feature.md
│       ├── add_agent.md
│       ├── debug.md
│       └── review.md
│
├── tests/
├── data/
│   ├── samples/
│   └── jd_examples/
│
├── README.md
├── requirements.txt
└── pyproject.toml
```

重点：

```text
docs/：放项目设计、参考项目、课程辅助、技术决策
.ai/skills/：放稳定开发规则
.ai/prompts/：放可复用开发提示词
data/samples/：放测试简历、测试 JD、golden cases
```

---

# 2. docs 需要准备什么

## 2.1 docs/PRD.md

作用：定义 JobAgent 到底做什么，不做什么。

建议内容：

```markdown
# JobAgent PRD

## 1. 项目背景
求职者在找 AI Agent / LLM 应用开发 / Python 后端等岗位时，常常不知道：
- 市场岗位真正需要什么能力
- 自己的简历和岗位 JD 差在哪里
- 项目经历怎么写得更有竞争力
- 项目是否经得住技术面试追问
- 如何系统记录投递和补强计划

## 2. 项目目标
构建一个多智能体求职工作台，支持：
- 用户画像构建
- 岗位 JD 搜集与入库
- 岗位 JD 结构化分析
- 简历解析
- 简历-JD 匹配度分析
- 简历优化建议生成
- 项目拷打问题生成
- 模拟面试与求职计划

## 3. MVP 范围
v0.1 只做：
- 用户输入简历文本或上传简历
- 用户粘贴 JD
- 系统解析简历和 JD
- 系统输出匹配度报告
- 系统输出简历优化建议
- 系统输出项目追问问题
- 系统生成 Markdown 报告

## 4. 非 MVP 范围
第一阶段不做：
- 自动投递
- 自动登录招聘网站
- 验证码处理
- 大规模爬虫
- 多用户权限系统
- 商业级推荐算法

## 5. 核心用户流程
1. 用户填写求职目标
2. 用户上传或粘贴简历
3. 用户粘贴 JD 或添加 URL
4. 系统解析并结构化信息
5. 系统进行匹配度分析
6. 系统给出简历优化建议
7. 系统生成项目拷打问题
8. 用户保存报告和岗位记录

## 6. 成功标准
- 流程能端到端跑通
- 输出结构化、可复用
- 建议具体，不空泛
- 简历优化不编造经历
- 项目追问能暴露真实短板
```

---

## 2.2 docs/ARCHITECTURE.md

作用：告诉 AI 和开发者系统怎么组织。

建议内容：

```markdown
# JobAgent Architecture

## 总体架构

JobAgent 采用分层架构：

```text
Frontend Streamlit
       ↓
FastAPI Backend
       ↓
LangGraph Orchestrator
       ↓
Specialized Agents
       ↓
Tools / Storage / LLM / RAG
```

## 核心层次

### Frontend
第一版使用 Streamlit，用于快速展示 Demo。

### Backend
使用 FastAPI，提供简历解析、JD 分析、匹配报告、项目追问等 API。

### Agent Orchestration
使用 LangGraph 管理多 Agent 工作流。

### Agents
- ProfileAgent
- ResumeParseAgent
- JDAnalysisAgent
- MatchAgent
- ResumeOptimizeAgent
- ProjectInterviewAgent
- ReportAgent

### Tools
- 文件读取
- JD 解析
- URL 抓取
- 报告生成
- 数据库存储

### Storage
- SQLite 起步
- 后期 PostgreSQL
- Chroma 用于岗位知识库和历史报告检索

## 第一阶段架构

第一阶段允许 mock LLM 和 mock 数据库，先保证流程跑通。

## 第二阶段架构

接入真实 LLM、SQLite、LangGraph、岗位数据库。

## 第三阶段架构

加入 RAG、MCP、岗位搜索、投递 tracker。
```

---

## 2.3 docs/DATA_SCHEMA.md

作用：稳定数据结构，防止 vibe coding 后期混乱。

建议内容：

```markdown
# JobAgent Data Schema

## 核心对象

- UserProfile
- Resume
- ResumeProfile
- JobPosting
- JobAnalysis
- MatchReport
- ResumeOptimizationResult
- ProjectChallengeReport
- InterviewSession
- ApplicationRecord

## 原则

1. 所有 Agent 输入输出尽量使用 Pydantic。
2. 原始文本和结构化结果都要保留。
3. 简历优化结果必须保留 original 和 optimized。
4. 匹配报告必须包含评分和证据。
5. 项目拷打必须包含问题、考察点、参考回答框架和暴露短板。
```

核心字段示例：

```python
class MatchReport(BaseModel):
    overall_score: float
    skill_score: float
    project_score: float
    experience_score: float
    keyword_coverage: float
    matched_points: list[str]
    missing_points: list[str]
    risks: list[str]
    evidence: list[str]
    apply_recommendation: str
    short_term_suggestions: list[str]
    long_term_suggestions: list[str]
```

---

## 2.4 docs/AGENTS.md

作用：明确每个 Agent 的职责边界。

建议内容：

```markdown
# JobAgent Agents

## 设计原则

1. 一个 Agent 只做一类任务。
2. Agent 输出必须能被下游消费。
3. 不要做超级 Agent。
4. 第一版可以 mock，每个 Agent 后续再接真实 LLM。
5. 不允许在简历优化中编造用户经历。

## Agent 列表

| Agent | 职责 | 输入 | 输出 |
|---|---|---|---|
| ProfileAgent | 构建用户画像 | 用户信息、简历 | UserProfile |
| ResumeParseAgent | 解析简历 | 简历文本/文件 | ResumeProfile |
| JDAnalysisAgent | 分析 JD | 原始 JD | JobAnalysis |
| MatchAgent | 匹配分析 | ResumeProfile + JobAnalysis | MatchReport |
| ResumeOptimizeAgent | 优化简历 | Resume + MatchReport + JD | ResumeOptimizationResult |
| ProjectInterviewAgent | 项目拷打 | 项目经历 + JD | ProjectChallengeReport |
| ReportAgent | 汇总报告 | 上游结果 | Markdown Report |

## 推荐主流程

```text
START
→ ResumeParseAgent
→ JDAnalysisAgent
→ MatchAgent
→ ResumeOptimizeAgent
→ ProjectInterviewAgent
→ ReportAgent
→ END
```
```

---

## 2.5 docs/ROADMAP.md

作用：把开发拆成可执行阶段。

```markdown
# JobAgent Roadmap

## v0.1 Mock MVP
- Streamlit 页面
- 简历文本输入
- JD 文本输入
- mock 简历解析
- mock JD 分析
- mock 匹配报告
- mock 简历优化
- mock 项目拷打
- Markdown 报告

## v0.2 LLM MVP
- 接入 OpenAI-compatible API
- Agent prompt 模板
- JSON structured output
- 基础错误重试

## v0.3 Backend + Storage
- FastAPI
- SQLite
- 保存 JD
- 保存简历版本
- 保存报告

## v0.4 LangGraph Workflow
- JobAgentState
- 多 Agent 节点
- 状态流转
- 日志和错误处理

## v0.5 Job Database
- URL 添加 JD
- 岗位去重
- 岗位标签
- 岗位搜索接口

## v0.6 Advanced Features
- 项目拷打增强
- 模拟面试
- 投递 tracker
- 市场分析

## v1.0 Portfolio Version
- README
- Demo 截图
- 架构图
- 测试样例
- Docker
- 部署说明
```

---

## 2.6 docs/REFERENCES.md

作用：放参考资料，不只是链接，还要写“借鉴什么，不借鉴什么”。

建议内容：

```markdown
# References

## Hello-Agents Course

项目参考课程：Datawhale Hello-Agents

重点参考内容：
- Agent 基本范式
- 工具调用
- 多 Agent 协作
- MCP
- Agent 评估
- 毕业设计项目组织方式

本项目如何使用：
- 不直接复制课程代码
- 参考其 Agent 架构思想
- 将课程概念落地到 JobAgent 场景

## Reference Projects

### Resume2Job
借鉴：
- 简历 + JD 匹配的 MVP 形态
- 简历解析与岗位分析流程
- 清晰的输入输出边界

不借鉴：
- 不只做简单问答
- 不停留在单次分析工具

### langgraph_jobsearch_assistant
借鉴：
- LangGraph 工作流
- 简历解析 → 岗位搜索 → 报告生成
- 结构化输出

不借鉴：
- 不完全依赖外部搜索 API
- 第一版不强制实时岗位搜索

### career-ops
借鉴：
- 求职操作系统思路
- profile.yml / 用户画像
- tracker
- AI coding friendly 的项目结构

不借鉴：
- 不做过重的配置系统
- 不把项目变成纯 CLI 工具

### AIHawk / ApplyPilot / Job-Agent 自动投递类项目
借鉴：
- 求职流程分阶段设计
- Discover → Score → Tailor → Apply 的思路
- 浏览器自动化作为后期扩展

不借鉴：
- 第一版不做自动投递
- 不处理验证码和平台登录
- 不把风控高的功能作为核心卖点
```

---

## 2.7 docs/HELLO_AGENTS_NOTES.md

作用：把课程和本项目对应起来，方便毕业设计答辩/README 使用。

建议内容：

```markdown
# Hello-Agents Notes for JobAgent

## 本项目对应课程知识点

### ReAct / Agent Loop
JobAgent 中的 MatchAgent、ResumeOptimizeAgent、ProjectInterviewAgent 都可以理解为具备推理和工具调用能力的 Agent。

### Tool Calling
JobAgent 的工具包括：
- resume_parser
- jd_parser
- url_fetcher
- report_writer
- database_tool

### Multi-Agent
JobAgent 将求职任务拆分为多个专用 Agent，而不是使用一个大模型完成所有任务。

### RAG
后期将岗位 JD 数据库、历史报告、面试题库放入向量数据库，用于个性化检索。

### MCP
后期可以将文件读取、岗位搜索、报告生成、tracker 查询封装成 MCP tools。

### Evaluation
JobAgent 会评估：
- 输出格式是否正确
- 是否编造简历经历
- JD 匹配是否合理
- 建议是否可执行
- 项目追问是否有深度

## 本项目为什么适合作为毕业设计

1. 有明确实际场景。
2. 能覆盖 Agent、工具调用、RAG、MCP、评估等课程知识点。
3. 可以从 MVP 逐步扩展到完整系统。
4. 最终结果可以放进简历和 GitHub 展示。
```

---

## 2.8 docs/EXAMPLE_PROJECTS.md

作用：专门记录竞品/参考项目分析。

建议内容：

```markdown
# Example Projects Analysis

## 分类

### 1. Resume-JD Matching
典型功能：上传简历、输入 JD、生成匹配建议。

我们吸收：
- 简历/JD 双输入
- 结构化分析报告
- 简历优化建议

### 2. LangGraph Job Search Assistant
典型功能：简历解析、岗位搜索、推荐报告。

我们吸收：
- 多步骤 Agent workflow
- 岗位推荐报告
- Pydantic structured output

### 3. Resume Screener / RAG 系统
典型功能：使用向量数据库匹配简历和岗位。

我们吸收：
- JD 入库
- 历史岗位检索
- 技能关键词统计

### 4. Auto Apply Agent
典型功能：自动搜索、自动填表、自动投递。

我们吸收：
- 求职流程阶段划分
- 后期可以考虑半自动投递

我们暂不做：
- 自动登录
- 自动提交申请
- 验证码处理
```

---

## 2.9 docs/DECISIONS.md

作用：记录技术决策，避免后期来回摇摆。

建议内容：

```markdown
# Technical Decisions

## Decision 1: 第一版使用 Streamlit

原因：
- 快速做 Demo
- 降低前端复杂度
- 重点放在 Agent 和后端逻辑

后续：
- 如果需要更完整产品体验，再迁移 Next.js

## Decision 2: 第一版不做自动投递

原因：
- 涉及平台风控和验证码
- 工程不稳定
- 不是毕业设计核心

后续：
- 可以做半自动投递助手

## Decision 3: 先 mock，再接 LLM

原因：
- 先稳定数据流
- 避免开发早期被 API 调用和 JSON 解析问题拖慢

## Decision 4: 使用 LangGraph 作为多 Agent 编排

原因：
- 更适合展示 Agent 工作流
- 状态管理清晰
- 和当前主流 Agent 工程实践接近

## Decision 5: 所有核心输出使用结构化 schema

原因：
- 方便测试
- 方便前端展示
- 方便后续入库和评估
```

---

# 3. 精简后的 Skills

Skill 不要太多。真正有用的是少量稳定规则，帮助 AI 不乱改、不乱扩展、不编造、不重构过度。

建议只保留 4 个。

---

## 3.1 .ai/skills/project_rules.md

```markdown
# JobAgent Project Rules

你是 JobAgent 项目的开发助手。无论执行什么任务，都必须遵守以下规则。

## 项目定位
JobAgent 是一个面向求职者的多智能体求职工作台。核心流程是：用户画像、岗位 JD 数据库、简历解析、JD 分析、匹配度分析、简历优化、项目拷打、模拟面试和求职管理。

## 当前优先级
优先完成 v0.1：
- 简历输入
- JD 输入
- 简历解析
- JD 分析
- 匹配报告
- 简历优化建议
- 项目拷打问题
- Markdown 报告

## 开发原则
1. 先保证最小闭环可运行。
2. 不要过早实现自动投递、复杂爬虫、登录、验证码、多用户权限。
3. 不要大规模重构，除非用户明确要求。
4. 每次修改前，先说明要改哪些文件和为什么。
5. 每次修改后，说明如何运行和测试。
6. 所有核心数据使用 Pydantic schema。
7. 业务逻辑不要堆在 UI 或 API route 里。
8. 简历优化不能编造经历、公司、项目、数据、技术栈。
9. 遇到需求不明确时，采用有利于 MVP 的最小默认方案。
10. 代码要可读、可测试、可逐步扩展。
```

---

## 3.2 .ai/skills/python_backend.md

```markdown
# Python Backend Skill

你是 JobAgent 的 Python 后端工程师。

## 技术栈
- Python 3.11+
- FastAPI
- Pydantic
- SQLite first, PostgreSQL later
- pytest

## 目录约定
- app/api：API routes
- app/schemas：Pydantic models
- app/services：业务逻辑
- app/agents：Agent 节点和 prompt
- app/tools：工具函数
- app/storage：数据库相关
- tests：测试

## 编码规则
1. API route 只负责请求响应，不写复杂业务逻辑。
2. services 负责业务编排。
3. agents 负责 LLM/Agent 逻辑。
4. tools 负责可复用工具。
5. schemas 定义所有核心输入输出。
6. 函数必须有类型标注。
7. 对外接口要有清晰错误处理。
8. 新功能尽量配一个最小测试。
9. 不引入重型依赖，除非确实必要。
```

---

## 3.3 .ai/skills/agent_workflow.md

```markdown
# Agent Workflow Skill

你是 JobAgent 的 Agent 工程师。

## Agent 设计规则
1. 每个 Agent 只负责一个明确任务。
2. Agent 输入输出必须结构化。
3. 不要让一个 Agent 同时做解析、评分、优化和报告。
4. 每个 Agent 都应该可以被单独测试。
5. Agent 输出必须能被下游 Agent 使用。
6. 第一版可以 mock，后续再替换为真实 LLM。
7. 真实 LLM 输出必须有 JSON/schema 校验和失败回退。

## 推荐 Agent
- ResumeParseAgent
- JDAnalysisAgent
- MatchAgent
- ResumeOptimizeAgent
- ProjectInterviewAgent
- ReportAgent

## 推荐工作流
START
→ ResumeParseAgent
→ JDAnalysisAgent
→ MatchAgent
→ ResumeOptimizeAgent
→ ProjectInterviewAgent
→ ReportAgent
→ END

## 约束
- 简历优化不得编造事实。
- 匹配分析必须给出证据。
- 项目拷打必须具体，不能泛泛提问。
- 报告必须给出可执行建议。
```

---

## 3.4 .ai/skills/evaluation.md

```markdown
# Evaluation Skill

你是 JobAgent 的评估工程师。

## 评估目标
确保 JobAgent 的输出可靠、结构化、真实、可执行。

## 核心检查项
1. Schema 是否正确。
2. 输出是否基于用户简历和 JD。
3. 是否编造了用户经历。
4. 匹配分是否有证据支撑。
5. 建议是否具体可执行。
6. 简历优化是否比原文更清晰、更岗位相关。
7. 项目追问是否能暴露真实短板。
8. 端到端流程是否能跑通。

## 推荐测试
- 单元测试：schema、parser、service
- 集成测试：简历 + JD → 报告
- Golden cases：固定样例对比输出质量
- LLM-as-judge：评估建议质量和事实一致性
```

---

# 4. Prompts：限定范围，但不锁死实现

Prompt 不要写死太多技术细节。它应该告诉 AI：目标是什么、边界是什么、不要做什么、交付什么。

---

## 4.1 .ai/prompts/bootstrap.md

```markdown
你现在是 JobAgent 项目的开发助手。

项目定位：
JobAgent 是一个面向求职者的多智能体求职工作台，围绕用户画像、岗位 JD 数据库、简历解析、JD 分析、匹配度分析、简历优化、项目拷打、模拟面试和求职管理展开。

当前阶段：
优先完成 v0.1 MVP：输入简历和 JD，输出匹配报告、简历优化建议和项目拷打问题。

开发边界：
- 不做自动投递
- 不做招聘网站登录
- 不做验证码处理
- 不做复杂爬虫
- 不做多用户权限系统
- 不做大规模重构

技术方向：
- Python 3.11+
- Streamlit for MVP UI
- FastAPI for backend
- Pydantic for schema
- LangGraph later for workflow
- SQLite later for storage
- LLM service should be replaceable

工作方式：
1. 先阅读当前项目结构。
2. 给出最小可行开发计划。
3. 修改前说明涉及文件。
4. 修改后说明如何运行和测试。
5. 优先保证端到端流程跑通。
```

---

## 4.2 .ai/prompts/implement_feature.md

```markdown
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
   - 不引入不必要依赖
   - 不大规模重构
   - 不做自动投递相关内容
   - 不破坏现有流程

4. 实现时优先保持结构清晰：
   - schema 放 app/schemas
   - 业务逻辑放 app/services
   - Agent 逻辑放 app/agents
   - 工具函数放 app/tools
   - API 放 app/api

5. 输出：
   - 修改文件列表
   - 关键代码
   - 如何运行
   - 如何测试
   - 后续可扩展点
```

---

## 4.3 .ai/prompts/add_agent.md

```markdown
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
- 如果信息不足，应返回 missing_info 或 suggestions，而不是假设事实。
- 不要为了新增 Agent 大规模改动项目结构。
```

---

## 4.4 .ai/prompts/debug.md

```markdown
JobAgent 出现了 bug。

请你按照以下流程调试：

1. 根据错误信息判断问题类型。
2. 定位最可能出错的文件和函数。
3. 给出最小修复方案。
4. 不要顺手重构无关代码。
5. 修复后给出验证方法。
6. 如果需要改多个文件，按优先级列出。

错误信息：
[粘贴错误]

相关代码：
[粘贴代码]
```

---

## 4.5 .ai/prompts/review.md

```markdown
请审查当前 JobAgent 项目。

重点检查：
1. 是否符合当前 MVP 范围。
2. 是否存在过度设计。
3. 项目结构是否清晰。
4. schema 是否稳定。
5. API、service、agent、tool 是否解耦。
6. Agent 输出是否结构化。
7. 是否存在简历优化编造事实的风险。
8. 是否容易扩展到 LangGraph、RAG、MCP。
9. 是否有必要的测试。

请输出：
- 总体评价
- 主要问题
- 建议修改顺序
- 文件级修改建议
- 暂时不建议修改的内容
```

---

# 5. Agent Prompt 模板

下面这些 prompt 只作为模板，不要把实现卡死。后续可以根据实际输出效果迭代。

---

## 5.1 ResumeParseAgent Prompt

```text
你是 JobAgent 的 ResumeParseAgent。

任务：从用户简历中提取结构化信息。

输入：
- resume_text

请提取：
- 基本信息
- 教育经历
- 技能栈
- 项目经历
- 实习/工作经历
- 证书/奖项
- 其他亮点

约束：
1. 不要编造简历中不存在的信息。
2. 信息缺失时返回 null 或空列表。
3. 保留关键技术名词。
4. 项目经历尽量保留原始表达。
5. 输出 JSON。
```

---

## 5.2 JDAnalysisAgent Prompt

```text
你是 JobAgent 的 JDAnalysisAgent。

任务：把岗位 JD 解析为结构化岗位画像。

输入：
- raw_jd
- optional: job_title, company, url

请提取：
- 岗位名称
- 公司
- 城市
- 岗位职责
- 必备技能
- 加分技能
- 经验要求
- 学历要求
- 软技能要求
- 隐含要求
- 技术关键词
- 岗位类别

约束：
1. 不要把加分项误判成必备项。
2. 不要补充 JD 中没有的信息。
3. 信息缺失时返回 null 或空列表。
4. 技术关键词要尽量标准化。
5. 输出 JSON。
```

---

## 5.3 MatchAgent Prompt

```text
你是 JobAgent 的 MatchAgent。

任务：比较用户简历、用户画像和目标岗位 JD，生成匹配度报告。

输入：
- user_profile
- resume_profile
- job_analysis

请输出：
- 总匹配分
- 技能匹配分
- 项目匹配分
- 经验匹配分
- 关键词覆盖率
- 已匹配优势
- 缺失能力
- 简历风险点
- 是否建议投递
- 短期优化建议
- 长期补强建议
- 证据

约束：
1. 必须给出评分理由。
2. 必须引用简历和 JD 中的具体证据。
3. 不要盲目给高分。
4. 不要编造用户没有的技能。
5. 输出 JSON。
```

---

## 5.4 ResumeOptimizeAgent Prompt

```text
你是 JobAgent 的 ResumeOptimizeAgent。

任务：根据目标 JD 和匹配报告，优化用户简历表达。

输入：
- original_resume
- resume_profile
- job_analysis
- match_report

请输出：
- 简历整体问题
- 需要强化的关键词
- 技能栏优化建议
- 项目经历改写建议
- 针对该 JD 的简历 bullet
- 不能夸大的部分
- 需要用户补充的信息

硬性约束：
1. 不能编造用户不存在的经历、公司、项目、数据和技术。
2. 如果需要量化但用户没提供数据，只能提示用户补充。
3. 优化表达要更具体、更岗位相关、更面向结果。
4. 输出 JSON。
```

---

## 5.5 ProjectInterviewAgent Prompt

```text
你是 JobAgent 的 ProjectInterviewAgent。

任务：模拟真实技术面试官，对用户简历中的项目进行深度追问。

输入：
- project_experience
- target_job_analysis
- optional: user_profile

请输出：
- 基础问题
- 技术细节追问
- 架构设计追问
- 难点与取舍追问
- 数据与评估追问
- 可扩展性追问
- 面试官可能质疑点
- 推荐回答框架
- 项目需要补强的地方

风格：
- 像真实面试官
- 有压力，但不攻击用户
- 问题具体
- 能暴露项目短板

约束：
1. 不问泛泛问题。
2. 每个问题说明考察点。
3. 回答建议不能编造用户经历。
4. 输出 JSON。
```

---

## 5.6 ReportAgent Prompt

```text
你是 JobAgent 的 ReportAgent。

任务：把多个 Agent 的输出整合成一份清晰的求职分析报告。

输入：
- user_profile
- resume_profile
- job_analysis
- match_report
- resume_optimization_result
- project_challenge_report

报告包含：
1. 用户画像摘要
2. 目标岗位摘要
3. 匹配度总览
4. 优势分析
5. 短板分析
6. 简历优化建议
7. 项目拷打问题
8. 面试准备建议
9. 一周行动计划
10. 是否建议投递

约束：
1. 输出 Markdown。
2. 不要空泛鸡汤。
3. 建议必须可执行。
4. 区分马上能做和长期补强。
```

---

# 6. 第一阶段执行顺序

## Step 1：先建文档

先创建：

```text
docs/PRD.md
docs/ARCHITECTURE.md
docs/DATA_SCHEMA.md
docs/AGENTS.md
docs/ROADMAP.md
docs/REFERENCES.md
docs/HELLO_AGENTS_NOTES.md
docs/EXAMPLE_PROJECTS.md
docs/DECISIONS.md
```

## Step 2：再建 AI 辅助开发文件

创建：

```text
.ai/skills/project_rules.md
.ai/skills/python_backend.md
.ai/skills/agent_workflow.md
.ai/skills/evaluation.md
.ai/prompts/bootstrap.md
.ai/prompts/implement_feature.md
.ai/prompts/add_agent.md
.ai/prompts/debug.md
.ai/prompts/review.md
```

## Step 3：再初始化项目骨架

先做：

```text
Streamlit MVP
Pydantic schema
Mock services
Markdown report
```

## Step 4：再接 LLM

替换 mock：

```text
LLM service
Agent prompts
JSON parser
schema validation
fallback
```

## Step 5：再接 FastAPI / LangGraph / SQLite

按顺序来：

```text
FastAPI → SQLite → LangGraph → JD database → RAG → MCP
```

---

# 7. 最小可执行起点

最小版本只要完成这个：

```text
输入：
- 用户简历文本
- 目标岗位 JD 文本

输出：
- JD 结构化分析
- 简历结构化分析
- 匹配度报告
- 简历优化建议
- 项目拷打问题
- Markdown 报告
```

这个版本跑通后，再逐步加入：

```text
岗位 URL 添加
岗位数据库
用户画像
模拟面试
投递 tracker
RAG
MCP
```

---

# 8. 当前结论

准备工作不需要堆很多花哨文档。真正关键的是：

```text
1. docs/ 里写清楚项目边界、架构、参考项目、课程对应关系。
2. .ai/skills/ 里保留少量稳定规则，防止 vibe coding 乱改。
3. .ai/prompts/ 里放通用开发提示词，限定范围但不锁死实现。
4. 先 mock 跑通核心闭环，再接 LLM、LangGraph、数据库、RAG、MCP。
```

JobAgent 的第一阶段，不追求功能多，而是追求：

```text
端到端能跑通
输出结构化
建议可执行
项目架构清晰
能逐步扩展
适合写进简历
```

---

# 9. 下一步拆解：从准备包到真实项目

现在不要急着写 Agent 逻辑。下一步要把项目拆成三层：

```text
文档层 → AI 辅助开发层 → 代码层
```

也就是：

```text
docs/        让人和 AI 知道项目要做什么
.ai/         让 AI 稳定开发，不乱扩展
app/         真正的后端、Agent、工具、数据库代码
frontend/    最小可运行前端 Demo
```

---

## 9.1 第一轮：建立 docs 文档层

目标：让项目边界稳定。

需要创建这些文件：

```text
docs/PRD.md
docs/ARCHITECTURE.md
docs/DATA_SCHEMA.md
docs/AGENTS.md
docs/ROADMAP.md
docs/REFERENCES.md
docs/HELLO_AGENTS_NOTES.md
docs/EXAMPLE_PROJECTS.md
docs/DECISIONS.md
```

### 任务 1：创建 docs/PRD.md

目的：说明 JobAgent 是什么、做什么、不做什么。

必须包含：

```text
项目背景
目标用户
用户痛点
核心功能
MVP 范围
非 MVP 范围
用户流程
验收标准
```

产出标准：

```text
读完 PRD 后，任何 AI coding 工具都应该知道第一版只做：
简历 + JD → 匹配报告 + 简历优化 + 项目拷打
```

---

### 任务 2：创建 docs/ARCHITECTURE.md

目的：说明系统结构，防止后续乱写代码。

必须包含：

```text
整体架构
Frontend 层
FastAPI Backend 层
Agent Workflow 层
Tools 层
Storage 层
Evaluation 层
第一阶段架构
第二阶段架构
```

产出标准：

```text
AI 后续写代码时，知道 UI、API、service、agent、tool、storage 分别放在哪里。
```

---

### 任务 3：创建 docs/DATA_SCHEMA.md

目的：先稳定数据结构。

必须定义：

```text
UserProfile
ResumeProfile
JobPosting
JobAnalysis
MatchReport
ResumeOptimizationResult
ProjectChallengeReport
FinalReport
```

产出标准：

```text
后续所有 Agent 输入输出都围绕这些 schema，不要随手传 dict。
```

---

### 任务 4：创建 docs/AGENTS.md

目的：明确 Agent 分工。

必须说明：

```text
ResumeParseAgent 做什么
JDAnalysisAgent 做什么
MatchAgent 做什么
ResumeOptimizeAgent 做什么
ProjectInterviewAgent 做什么
ReportAgent 做什么
```

产出标准：

```text
每个 Agent 都有明确输入、输出、职责边界。
```

---

### 任务 5：创建 docs/ROADMAP.md

目的：把开发拆成版本。

建议版本：

```text
v0.1 Mock MVP
v0.2 LLM MVP
v0.3 FastAPI + SQLite
v0.4 LangGraph Workflow
v0.5 Job Database
v0.6 Interview + Tracker
v1.0 Portfolio Version
```

产出标准：

```text
每个版本都有明确交付物，不会一上来做大而全。
```

---

### 任务 6：创建 docs/REFERENCES.md

目的：记录参考资料和借鉴点。

必须包含：

```text
Hello-Agents Course
Resume2Job
langgraph_jobsearch_assistant
career-ops
AIHawk / ApplyPilot / 自动投递类项目
```

每个参考项目写清楚：

```text
借鉴什么
不借鉴什么
为什么
```

产出标准：

```text
README 和答辩时能说明项目不是凭空设计，而是参考了成熟模式并做了取舍。
```

---

### 任务 7：创建 docs/HELLO_AGENTS_NOTES.md

目的：把课程知识点映射到 JobAgent。

必须包含：

```text
ReAct / Agent Loop 对应哪里
Tool Calling 对应哪里
Multi-Agent 对应哪里
RAG 对应哪里
MCP 后期怎么接
Evaluation 怎么做
```

产出标准：

```text
能说明 JobAgent 是 Hello-Agents 学习后的落地毕业设计。
```

---

### 任务 8：创建 docs/EXAMPLE_PROJECTS.md

目的：整理竞品/参考项目分析。

分类：

```text
Resume-JD Matching
LangGraph Job Search Assistant
Resume Screener / RAG
Auto Apply Agent
CareerOps
```

产出标准：

```text
能反推 JobAgent 的需求边界和功能优先级。
```

---

### 任务 9：创建 docs/DECISIONS.md

目的：记录技术决策。

必须记录：

```text
为什么第一版用 Streamlit
为什么第一版不做自动投递
为什么先 mock 后 LLM
为什么使用 Pydantic
为什么后续用 LangGraph
为什么 SQLite 起步
为什么 MCP 放后期
```

产出标准：

```text
避免后续反复摇摆技术选型。
```

---

## 9.2 第二轮：建立 .ai 辅助开发层

目标：让 AI coding 稳定，不乱加功能。

需要创建：

```text
.ai/skills/project_rules.md
.ai/skills/python_backend.md
.ai/skills/agent_workflow.md
.ai/skills/evaluation.md
.ai/prompts/bootstrap.md
.ai/prompts/implement_feature.md
.ai/prompts/add_agent.md
.ai/prompts/debug.md
.ai/prompts/review.md
```

---

### Skill 文件拆解

#### 1. project_rules.md

作用：项目总规则。

必须强调：

```text
先做 MVP
不做自动投递
不大规模重构
核心输出结构化
简历优化不编造
```

#### 2. python_backend.md

作用：后端代码规则。

必须强调：

```text
API route 不写复杂业务逻辑
schema 放 schemas
业务逻辑放 services
Agent 逻辑放 agents
工具放 tools
函数要类型标注
```

#### 3. agent_workflow.md

作用：Agent 设计规则。

必须强调：

```text
一个 Agent 一个职责
输入输出结构化
先 mock 后 LLM
输出能被下游消费
真实 LLM 要做 schema 校验
```

#### 4. evaluation.md

作用：评估规则。

必须强调：

```text
格式正确性
事实一致性
不编造经历
建议可执行
端到端流程能跑通
```

---

### Prompt 文件拆解

#### 1. bootstrap.md

什么时候用：

```text
每次开启新的 AI coding 会话时先贴。
```

作用：

```text
让 AI 先理解项目定位、阶段目标和边界。
```

#### 2. implement_feature.md

什么时候用：

```text
实现一个具体功能时。
```

例如：

```text
实现简历解析
实现 JD 分析
实现匹配报告
实现 Markdown 报告生成
```

#### 3. add_agent.md

什么时候用：

```text
新增一个 Agent 时。
```

例如：

```text
新增 MatchAgent
新增 ProjectInterviewAgent
新增 ReportAgent
```

#### 4. debug.md

什么时候用：

```text
报错时。
```

#### 5. review.md

什么时候用：

```text
每完成一个版本后，让 AI 审查项目结构。
```

---

## 9.3 第三轮：初始化代码骨架

目标：项目能启动。

创建目录：

```text
app/
frontend/
tests/
data/samples/
```

第一轮代码不要复杂，先做 mock。

### 必须有的文件

```text
app/main.py
frontend/streamlit_app.py
app/schemas/resume.py
app/schemas/job.py
app/schemas/match.py
app/schemas/report.py
app/services/mock_pipeline.py
app/services/report_service.py
README.md
requirements.txt
```

---

## 9.4 第四轮：实现 v0.1 Mock MVP

目标：不用 LLM，也能端到端跑通。

输入：

```text
简历文本
JD 文本
```

处理流程：

```text
mock_resume_parse
mock_jd_analysis
mock_match_analysis
mock_resume_optimization
mock_project_challenge
generate_markdown_report
```

输出：

```text
匹配分
匹配优势
缺失技能
简历优化建议
项目追问问题
Markdown 报告
```

产出标准：

```text
streamlit run frontend/streamlit_app.py
```

可以打开页面，输入简历和 JD，点击按钮，看到完整报告。

---

## 9.5 第五轮：接入真实 LLM

目标：把 mock 替换成真实 Agent 输出。

新增文件：

```text
app/services/llm_service.py
app/agents/resume_parse_agent.py
app/agents/jd_analysis_agent.py
app/agents/match_agent.py
app/agents/resume_optimize_agent.py
app/agents/project_interview_agent.py
app/agents/report_agent.py
```

实现顺序：

```text
1. LLM service
2. JDAnalysisAgent
3. ResumeParseAgent
4. MatchAgent
5. ResumeOptimizeAgent
6. ProjectInterviewAgent
7. ReportAgent
```

为什么先 JDAnalysisAgent：

```text
JD 文本通常比简历更标准，结构化更容易，适合作为第一个真实 LLM Agent。
```

---

## 9.6 第六轮：接入 FastAPI

目标：把流程变成后端服务。

新增：

```text
app/api/routes_analyze.py
app/api/routes_resume.py
app/api/routes_jobs.py
app/api/routes_reports.py
```

第一批 API：

```text
POST /analyze/full
POST /resume/parse
POST /jobs/analyze
POST /match/analyze
POST /reports/generate
```

原则：

```text
API 只收请求和返回结果
核心逻辑仍然放 services / agents
```

---

## 9.7 第七轮：接入 SQLite

目标：能保存岗位、报告、简历版本。

新增：

```text
app/storage/database.py
app/storage/models.py
app/storage/repositories.py
```

第一批数据表：

```text
job_postings
resume_records
match_reports
resume_versions
project_challenges
```

不要一开始做完整用户系统。

---

## 9.8 第八轮：接入 LangGraph

目标：把流程从普通 service 变成多 Agent 工作流。

新增：

```text
app/agents/state.py
app/agents/workflow.py
```

定义：

```text
JobAgentState
ResumeParseNode
JDAnalysisNode
MatchNode
ResumeOptimizeNode
ProjectInterviewNode
ReportNode
```

流程：

```text
START
→ ResumeParseAgent
→ JDAnalysisAgent
→ MatchAgent
→ ResumeOptimizeAgent
→ ProjectInterviewAgent
→ ReportAgent
→ END
```

---

## 9.9 第九轮：岗位数据库和 URL 添加

目标：从“单次 JD 分析”升级成“岗位库”。

新增功能：

```text
用户粘贴 URL
系统抓取网页文本
提取 JD
结构化入库
岗位去重
岗位标签分类
```

注意：

```text
第一版 URL 抓取只做简单网页，不处理登录、验证码和复杂反爬。
```

---

## 9.10 第十轮：RAG / MCP / Tracker

这些放后期。

### RAG

用途：

```text
检索历史 JD
检索历史报告
岗位技能趋势
个性化建议
```

### MCP

适合封装：

```text
resume_reader
jd_fetcher
job_database_query
report_writer
tracker_query
```

### Tracker

记录：

```text
公司
岗位
JD
匹配分
投递状态
简历版本
面试状态
下一步行动
```

---

# 10. 立刻可以执行的最小任务清单

现在下一步只做这些，不写复杂 Agent：

```text
[ ] 创建 docs/PRD.md
[ ] 创建 docs/ARCHITECTURE.md
[ ] 创建 docs/DATA_SCHEMA.md
[ ] 创建 docs/AGENTS.md
[ ] 创建 docs/ROADMAP.md
[ ] 创建 docs/REFERENCES.md
[ ] 创建 docs/HELLO_AGENTS_NOTES.md
[ ] 创建 docs/EXAMPLE_PROJECTS.md
[ ] 创建 docs/DECISIONS.md

[ ] 创建 .ai/skills/project_rules.md
[ ] 创建 .ai/skills/python_backend.md
[ ] 创建 .ai/skills/agent_workflow.md
[ ] 创建 .ai/skills/evaluation.md

[ ] 创建 .ai/prompts/bootstrap.md
[ ] 创建 .ai/prompts/implement_feature.md
[ ] 创建 .ai/prompts/add_agent.md
[ ] 创建 .ai/prompts/debug.md
[ ] 创建 .ai/prompts/review.md
```

完成后，再进入代码阶段：

```text
[ ] 初始化 app/ frontend/ tests/ data/
[ ] 写 Pydantic schema
[ ] 写 mock pipeline
[ ] 写 Streamlit Demo
[ ] 输出 Markdown 报告
```

---

# 11. 第一条 vibe coding 指令

当你进入 Cursor / Codex / Claude Code 时，第一条可以直接使用：

```text
请基于当前 JobAgent 项目准备包，先创建文档层和 AI 辅助开发层。

第一阶段只创建以下文件，不写业务代码：

docs/PRD.md
docs/ARCHITECTURE.md
docs/DATA_SCHEMA.md
docs/AGENTS.md
docs/ROADMAP.md
docs/REFERENCES.md
docs/HELLO_AGENTS_NOTES.md
docs/EXAMPLE_PROJECTS.md
docs/DECISIONS.md

.ai/skills/project_rules.md
.ai/skills/python_backend.md
.ai/skills/agent_workflow.md
.ai/skills/evaluation.md

.ai/prompts/bootstrap.md
.ai/prompts/implement_feature.md
.ai/prompts/add_agent.md
.ai/prompts/debug.md
.ai/prompts/review.md

要求：
1. 内容简洁但完整。
2. 不要生成业务代码。
3. 不要引入自动投递、登录、验证码处理等功能。
4. 文档要服务于后续 vibe coding。
5. 每个文件都要说明它的用途。
6. 最后输出创建的文件列表和下一步建议。
```

---

# 12. 第二条 vibe coding 指令

文档和 .ai 文件创建完成后，第二条使用：

```text
现在请初始化 JobAgent 的最小代码骨架。

目标：先跑通 mock MVP，不接真实 LLM。

请创建：
- app/main.py
- frontend/streamlit_app.py
- app/schemas/resume.py
- app/schemas/job.py
- app/schemas/match.py
- app/schemas/report.py
- app/services/mock_pipeline.py
- app/services/report_service.py
- tests/test_mock_pipeline.py
- README.md
- requirements.txt

功能要求：
1. Streamlit 页面可以输入简历文本和 JD 文本。
2. mock_pipeline 返回结构化的简历分析、JD 分析、匹配报告、简历优化建议和项目追问。
3. report_service 生成 Markdown 报告。
4. 页面展示报告。
5. 提供运行命令。
6. 提供最小测试。

边界：
- 不接真实 LLM。
- 不接数据库。
- 不接 LangGraph。
- 不做自动投递。
```

---

# 13. 第三条 vibe coding 指令

mock MVP 跑通后，再使用：

```text
现在请为 JobAgent 接入真实 LLM，但只替换 JDAnalysisAgent 一个模块。

目标：先让 JDAnalysisAgent 从 mock 变成真实 LLM 结构化输出。

要求：
1. 新增 app/services/llm_service.py。
2. 新增 app/agents/jd_analysis_agent.py。
3. 使用 Pydantic schema 校验输出。
4. LLM 调用失败时回退到 mock。
5. 不影响现有 Streamlit 页面。
6. 给出测试方式。

边界：
- 不要一次性替换所有 Agent。
- 不要引入 LangGraph。
- 不要引入数据库。
```

