# JobAgent 代码链路说明（中文）

本文帮助开发者快速定位一次请求从哪里进入、经过哪些层、最终写到哪里。
只记录当前主链路和容易误判的兼容边界，不逐函数复述代码。

## 文件内注释约定

每个脚本使用自然中文说明本文件实际处理的动作。主链路文件还在对应函数或分支旁
解释状态失效、异步调度、部分失败、回退、持久化和安全边界。注释描述代码没有直接
表达的意图，不逐行翻译函数名、字段赋值或明显的 CRUD 操作。

## 1. 分层规则

```text
Vue 页面
-> web/src/stores（页面共享状态）
-> web/src/api（HTTP 契约）
-> app/api/v1（路由、身份注入）
-> app/application（用例编排、所有权和状态检查）
-> app/services（解析、搜索、LLM、MCP 等领域逻辑）
-> app/repositories（SQLite 读写）
-> app/storage/database.py（建表与兼容迁移）
```

- `app/schemas` 是前后端交互和持久化快照的结构约束。
- `app/main.py` 只装配中间件、统一异常处理和 `/api/v1` 路由。
- 外部 Provider、LLM、MCP 必须经过 `app/services` 中已有接口，不能从页面或
  Repository 直接调用。
- 用户身份在 API 层注入，资源归属在 Application 和 Repository 层再次校验。

## 2. 主业务链路

### 2.1 登录

```text
LoginPage
-> stores/auth.ts
-> api/auth.ts
-> api/v1/auth.py
-> application/auth_usecases.py
-> user_repository + auth_session_repository
```

登录成功后，前端 HTTP 客户端统一附加 bearer token。无 token 自动映射
`local-user` 是本地开发兼容行为，不是生产鉴权方案。

### 2.2 简历到确认画像

```text
HomePage
-> 创建 ProfileSession
-> 提交文本或文件
-> resume_intake_usecases
-> ResumeDocument

ProfileReviewPage
-> resume_review_usecases
-> resume_section_parser / 可选 LLM 增强
-> ParsedResumeReview

ProfileDraftPage
-> profile_draft_usecases
-> ProfileDraft（可编辑）

ProfileConfirmedPage
-> confirmed_profile_usecases
-> ConfirmedProfile
-> 同步为可复用 ResumeProfile
```

`ProfileSession.current_step` 是流程真相源。替换上游简历会使当前 review、
draft、confirmed profile 和 search 引用失效；历史数据可保留，但不能继续作为
当前链路输入。

### 2.3 搜索设置与职位搜索

```text
SearchPreviewPage + SearchIntentForm
-> 保存、解释并确认 SearchMission
-> 选择搜索来源
-> POST /job-search-runs 或 /job-search-runs/browser-helper
-> job_search_usecases.create_job_search_run
-> 持久化 pending run + trace steps
-> FastAPI BackgroundTasks
-> execute_job_search_run
   -> 搜索计划
   -> Provider 召回
   -> 候选过滤
   -> JD 分析
   -> 画像匹配
   -> 结果组装
-> JobSearchRun completed/failed
-> JobSearchPage 轮询 run、steps、items
```

普通 Provider 在后端执行；BOSS 候选由浏览器扩展利用用户现有登录态抓取，再回到
同一后端分析链路。单个 Provider 失败允许保留其他来源的有效结果。后台任务是
本地 MVP 的进程内任务，进程退出后不会自动恢复。

`Search Mission` 仍是有效的内部结构和持久化资源。独立
`SearchMissionPage.vue` 已合并进 Search Preview；旧 URL 只做重定向，不能据此
删除后端 mission 表、Repository 或 API。

### 2.4 保存职位、Job Brief 与准备工作

```text
JobSearchPage
-> POST /saved-jobs/from-search-result
-> saved_job_usecases
-> 保存 JD 快照、分析快照和来源关系

SavedJobDetailPage
-> 生成 Job Brief
-> job_brief_generator
-> 版本化 JobBrief

SavedJobDetailPage
-> 生成/继续 Preparation
-> interview_preparation_generator + PreparationAgent
-> 可选 learning resource / MCP 检索
-> 保存答案、暂停或完成
```

重复保存同一职位会复用用户名下的 SavedJob，但追加新的分析和来源上下文。较短的
JD 摘要不能覆盖已保存的完整 JD。

### 2.5 Career Assistant

```text
ChatPage
-> api/chat.ts
-> api/v1/chat.py
-> chat_usecases
-> 构建有限上下文清单
-> chat agent 决定是否调用只读工具
-> Repository 再校验 user_id
-> 生成带引用的回答
-> 持久化 turn 和可重建摘要
```

Assistant 只读消费画像、搜索和收藏数据，不修改搜索结果，也不是搜索流水线的一个
阶段。原始简历文本不会进入 Assistant 上下文。

### 2.6 Browser Helper

```text
Vue
<-> browser-helper/bridge.js（网页与扩展消息桥）
<-> browser-helper/background.js（登录探测、BOSS 搜索、当前页提取）
-> browser helper token / capture API
-> 正常搜索、收藏或 Assistant 链路
```

Cookie 只留在浏览器扩展中。扩展只能关闭自己创建的标签页，并必须返回成功或失败的
终态。

### 2.7 RAG 与 MCP

```text
业务数据变更
-> rag_index_outbox
-> scripts/run_rag_sync.py
-> 外部 Modular RAG

Assistant / Preparation
-> app/services/mcp 客户端
-> 有限工具白名单、超时和响应预算
-> 外部 MCP 服务
```

MCP 不可用不能阻止 FastAPI 启动；调用方应走已有 fallback。`mcp_servers` 和
`scripts` 下的模块可能没有 Python 入站 import，因为它们是命令行启动入口，
不能按“零引用”直接删除。

## 3. 旧代码与旧说明标注

本轮只标注，不删除。后续清理前还要检查现有 SQLite 数据和外部调用方。

| 标记 | 位置 | 依据与处理建议 |
| --- | --- | --- |
| 兼容保留 | 前端 `/profile/:sessionId/search-mission` 路由 | 只把旧书签重定向到统一 Search Preview；有明确兼容价值。 |
| 兼容保留 | `/browser/job-captures/analyze` | 合并“保存并分析”的旧调用方式，API 文档已明确标为 compatibility。 |
| 兼容保留 | `get_current_user` 的匿名 `local-user` | 本地模式需要，公网部署前必须改为显式开发开关。 |
| 兼容保留 | `legacySelectedSearchSources` | 读取旧版前端持久化字段；清理前需考虑用户浏览器内已有状态。 |
| 旧说明待更新 | `docs/BROWSER_HELPER.md` 的手工检查步骤 | 当前统一 Search Setup 在用户点击 Start 后自动检查 Helper/BOSS 登录态。 |
| 旧说明待补全 | `docs/API_CONTRACT_V1.md` 的 Job Search 路由清单 | 未列出已存在的 `GET /job-search-runs/{run_id}/items`。 |
| 旧说明待补全 | `web/README.md` 的 Current Views | 未覆盖 Assistant、Knowledge Status、Job Brief 和 Preparation。 |
| 独立入口，勿误删 | `mcp_servers/learning_search/server.py`、`scripts/*.py` | 通过 `python -m` 或脚本启动，静态 import 扫描会产生假阳性。 |

## 4. 后续清理顺序

1. 先确认零引用类型和前端导出是否有仓库外调用方，再做小范围删除。
2. 补齐旧说明，并为兼容入口记录明确的下线条件。
3. 最后盘点真实 SQLite 文件中的旧表数据，设计可回滚迁移；不要直接从
   `init_database()` 删除表定义。
