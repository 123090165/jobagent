# JobAgent Architecture

> 用途：说明系统分层、目录职责和阶段性架构，防止后续代码散落或过度设计。

## 1. 总体架构

JobAgent 采用分层架构，第一阶段先用 mock 跑通闭环，后续再逐步替换为真实 Agent、后端服务和存储。

```text
Frontend Streamlit
       |
Service Layer
       |
Mock / LLM Agents
       |
Schemas / Tools / Report
       |
Storage later
```

后续完整形态：

```text
Frontend Streamlit or Web UI
       |
FastAPI Backend
       |
LangGraph Workflow
       |
Specialized Agents
       |
Tools / Storage / LLM / RAG / MCP
```

## 2. 目录职责

```text
app/
  api/          FastAPI routes，只处理请求和响应
  agents/       Agent 节点、prompt 和 LLM 调用包装
  schemas/      Pydantic 数据模型
  services/     业务编排和核心流程
  tools/        可复用工具函数
  storage/      数据库连接、模型和仓储
  evaluation/   评估规则和测试辅助
frontend/       Streamlit MVP 页面
docs/           项目设计、架构、路线图和决策
.ai/skills/     AI coding 稳定规则
.ai/prompts/    可复用开发提示词
tests/          单元测试和集成测试
data/           样例简历、样例 JD 和 golden cases
```

## 3. Frontend 层

第一版使用 Streamlit 快速展示 Demo。

职责：

- 输入简历文本和 JD 文本。
- 调用 service 层的 mock pipeline。
- 展示结构化结果和 Markdown 报告。

边界：

- 不在 UI 中写复杂业务逻辑。
- 不直接调用 LLM。
- 不直接处理数据库细节。

## 4. FastAPI Backend 层

后续接入 FastAPI，提供稳定 API。

第一批 API：

- `POST /analyze/full`
- `POST /resume/parse`
- `POST /jobs/analyze`
- `POST /match/analyze`
- `POST /reports/generate`

原则：

- route 只负责请求校验、调用 service、返回响应。
- 复杂流程放在 `app/services/`。
- Agent 逻辑放在 `app/agents/`。

## 5. Agent Workflow 层

后续使用 LangGraph 编排多 Agent。

推荐流程：

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

第一版可以由普通 service 模拟这个流程，等数据结构稳定后再迁移到 LangGraph。

## 6. Tools 层

工具层封装可复用能力：

- 简历文本读取。
- JD 文本清洗。
- URL 抓取。
- Markdown 报告写入。
- 数据库存取。
- 关键词统计。

原则：

- 工具函数保持小而清晰。
- 不在工具层做完整业务决策。

## 7. Storage 层

存储分阶段实现：

- v0.1：不接数据库，必要时使用内存对象。
- v0.3：SQLite 保存 JD、简历版本、报告和项目追问。
- 后期：PostgreSQL 支持更完整的用户和投递数据。
- 后期：Chroma 或其他向量库支持 RAG。

第一批表：

- `job_postings`
- `resume_records`
- `match_reports`
- `resume_versions`
- `project_challenges`

## 8. Evaluation 层

评估重点：

- Schema 是否正确。
- 输出是否基于用户简历和 JD。
- 是否编造简历经历。
- 匹配分是否有证据。
- 建议是否具体可执行。
- 端到端流程是否能跑通。

## 9. 阶段性架构

### 第一阶段：Mock MVP

- Streamlit 页面。
- Pydantic schema。
- Mock pipeline。
- Markdown 报告。
- 不接 LLM、数据库、LangGraph。

### 第二阶段：LLM MVP

- 接入 OpenAI-compatible API。
- 先替换 JDAnalysisAgent。
- 使用 schema 校验 LLM 输出。
- 调用失败时回退 mock。

### 第三阶段：Backend + Storage

- 接入 FastAPI。
- 接入 SQLite。
- 保存 JD、简历版本、匹配报告和项目追问。

### 第四阶段：LangGraph + RAG + MCP

- 使用 LangGraph 管理多 Agent 状态流转。
- 建立岗位知识库和历史报告检索。
- 将文件读取、岗位检索、报告生成等能力封装为 MCP tools。
