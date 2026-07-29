# JobAgent × Modular RAG MCP 正式集成开发计划

## 1. 文档目的

本文定义 JobAgent 与 `MODULAR-RAG-MCP-SERVER` 的正式集成目标、数据所有权、
权限边界、同步协议、索引生命周期、实施顺序和验收标准。

目标不是把 RAG 合并进 JobAgent 的职位网络搜索，也不是仅证明 MCP 端口可调用，
而是把 Modular RAG 建设为 JobAgent 的独立知识检索服务：

```text
JobAgent
  - 业务事实
  - 用户认证与授权
  - 决定哪些资源需要索引
  - 组织回答与引用
        |
        | 受认证的管理请求和 MCP 检索请求
        v
Modular RAG MCP Server
  - 文档规范化后的摄取
  - 文本切块和 embedding
  - Chroma 向量检索
  - BM25 关键词检索
  - 索引目录、版本、删除和重建
```

“一步到位”在本文中的含义是：先固定最终数据契约和安全边界，再分阶段实现；
不先建设一个无权限、无版本、无法删除的临时知识库，然后重新推倒。

---

## 2. 已确认的架构决策

### 2.1 服务边界

1. Modular RAG 保持独立进程和独立仓库。
2. JobAgent 通过 MCP Streamable HTTP 使用检索工具。
3. 数据摄取、删除、重建、状态查询属于 RAG 管理面，不应交给 LLM 自由调用。
4. RAG 不属于 Search V2 的职位来源检索阶段。
5. RAG 暂时不由 JobAgent 自动启动或停止。

### 2.2 数据所有权

1. JobAgent 数据库是用户、简历、画像、职位、分析和对话的业务事实来源。
2. RAG 保存的文本块、向量、BM25 索引和图片均为可重建派生数据。
3. JobAgent 决定资源是否应该被索引、更新或删除。
4. RAG 决定如何切块、生成向量、建立索引和执行混合检索。
5. RAG 不直接读取 JobAgent 的 SQLite 或未来的 PostgreSQL 业务表。
6. RAG 索引不能反向覆盖 JobAgent 业务数据。

### 2.3 权限边界

1. 用户身份只能来自 JobAgent 已认证会话，不能来自 LLM 生成的工具参数。
2. JobAgent 在发起请求前校验资源所有权。
3. RAG 必须再次强制执行租户、用户和可见性过滤。
4. 权限过滤必须同时应用于 Chroma、BM25、摘要、图片和管理接口。
5. 缺少可信权限上下文时，私有检索必须拒绝，不能降级为全库检索。
6. 日志、trace、错误信息和缓存不得泄露其他用户的内容或资源标识。

### 2.4 存储边界

第一阶段保留现有技术：

| 所属服务 | 存储 | 职责 |
|---|---|---|
| JobAgent | SQLite，未来可迁移 PostgreSQL | 业务事实、用户权限、同步任务 |
| Modular RAG | RAG catalog SQLite | 文档归属、版本、索引状态、操作历史 |
| Modular RAG | Chroma | 文本块、embedding、向量检索 metadata |
| Modular RAG | tenant-aware BM25 | 关键词倒排索引 |
| Modular RAG | ingestion/image SQLite | 文件摄取和图片辅助索引 |
| Modular RAG | 文件系统 | 图片、可控 trace 和运行日志 |

数据库可以物理隔离，但所有私有 RAG 数据必须继承 JobAgent 用户权限。

---

## 3. 当前状态

### 3.1 已完成

JobAgent 已具备：

- 可配置的 Streamable HTTP MCP 客户端；
- MCP `initialize` 和 `tools/list` 协议检查；
- 工具调用 allowlist；
- 超时和响应大小限制；
- Modular RAG 的 typed adapter；
- 基础公共查询和 `search_authorized_knowledge` 私有查询；
- 短期 HMAC 用户 scope token；
- Resume Profile、Saved Job 的确定性安全 formatter；
- 与业务写入同事务的 durable outbox 和资源同步状态；
- 带重试、指数退避、处理租约和空闲退避的独立 worker；
- Career Assistant 的 bounded `search_personal_knowledge` 工具；
- 精确 Repository 读取与 RAG 语义发现的路由边界；
- MCP 不可用、无命中和过期结果的数据库回退；
- RAG 结果的用户、类型、可见性和索引版本二次校验；
- 复用现有 Chat 证据预算、引用和提示注入隔离；
- fake session 单元测试和真实服务诊断脚本；
- RAG 不可用时不阻止 JobAgent 启动的可选服务边界。

Modular RAG 已具备：

- stdio 和 Streamable HTTP 两种运行模式；
- Chroma dense retrieval；
- BM25 sparse retrieval；
- 混合召回、融合和可选 rerank；
- 文档摄取、摘要、图片索引和 trace 基础能力。
- JobAgent 资源目录、版本管理和幂等管理接口；
- Chroma 与 BM25 的检索前权限过滤；
- 私有资源删除和旧版本替换；
- 签名 scope 验证及授权混合检索。

### 3.2 尚未完成

- 历史存量资源的一次性 backfill/rebuild 管理命令；
- 用户注销后的按用户批量清理流程；
- worker 健康指标、积压告警和部署级进程监督配置；
- 密钥轮换、备份恢复和索引全量重建演练；
- 前端对“语义知识检索/数据库回退”状态的可选展示；
- 招聘领域离线检索质量基线。

因此当前状态是“首个 Chat 业务闭环完成，进入真实数据质量验收与生产运维准备”，
不再只是协议通信基础；但在完成 Phase 5 前仍不应宣称已达到生产就绪。

---

## 4. 目标运行架构

```text
Browser / Vue
      |
      v
JobAgent FastAPI
  [认证会话]
      |
      +--> Application Use Case
      |      - 校验 user_id 和资源所有权
      |      - 确定允许的资源范围
      |
      +--> JobAgent Business DB
      |      - users/auth_sessions
      |      - resume_profiles
      |      - saved_jobs
      |      - analyses
      |      - rag_index_outbox
      |      - rag_resource_status
      |
      +--> RAG Sync Worker
      |      - 读取 outbox
      |      - 构造 ResourceEnvelope
      |      - 调用 RAG 管理面
      |
      +--> Authorized RAG Adapter
             - 注入可信 RetrievalContext
             - 调用 allowlisted MCP tools
                    |
                    v
Modular RAG Service
  [服务身份验证]
      |
      +--> Authorization Guard
      |      - public OR owned private resource
      |
      +--> RAG Catalog
      |      - documents
      |      - chunks
      |      - index operations
      |
      +--> Chroma
      |      - tenant/user metadata pre-filter
      |
      +--> BM25
             - tenant-aware candidate generation
```

JobAgent 与 RAG 之间分为两条逻辑通道：

### 管理面

仅由 JobAgent 后端或受控 worker 调用：

- upsert resource；
- delete resource；
- reindex resource；
- get operation status；
- reconcile/rebuild。

### 检索面

由 JobAgent 后端的 typed adapter 调用：

- authorized hybrid search；
- authorized document summary；
- authorized source/citation lookup。

LLM 不获得管理面工具，也不能构造任意用户过滤条件。

---

## 5. 数据分类与首批索引范围

### 5.1 可以进入私有 RAG

第一批建议只包含稳定、用户确认或主动保存的资源：

| JobAgent 资源 | 索引内容 | 初始优先级 |
|---|---|---|
| `resume_profile` | 确认画像、工作经历、项目、技能、教育、目标方向 | P0 |
| `saved_job` | 职位标题、公司、地点、完整 JD、结构化要求 | P0 |
| `saved_job_analysis` | 匹配证据、缺口、风险、关键要求 | P1 |
| `browser_job_capture` | 用户主动保存的页面职位和 JD | P1 |
| `job_brief` | 已生成的职位研究和行动建议 | P2 |
| `interview_preparation` | 面试主题、证据和准备材料 | P2 |

### 5.2 可以进入公共 RAG

- 审核后的公共学习资源；
- 招聘术语、技能说明等公共知识；
- 明确标记为 `visibility=public` 的运营资料。

公共资料和私有资料必须有明确可见性，不通过“缺少 user_id”隐式判断公共。

### 5.3 默认禁止索引

- `users` 中的密码哈希、盐和认证字段；
- `auth_sessions` 和任何 token；
- 未确认的简历草稿；
- 原始系统提示词和密钥；
- 全量运行日志；
- 未保存的临时职位搜索结果；
- 默认情况下的完整聊天历史；
- 与检索目的无关的个人敏感字段。

原始简历文本是否索引应作为后续独立产品决策。第一版优先索引确认后的结构化画像，
降低过度采集和提示注入风险。

---

## 6. 统一资源数据契约

### 6.1 ResourceEnvelope

JobAgent 向 RAG 管理面发送的资源使用版本化信封：

```json
{
  "schema_version": "1",
  "operation_id": "8a45d0bd-...",
  "operation": "upsert",
  "resource": {
    "tenant_id": "default",
    "owner_user_id": "b6d7f1b5-...",
    "resource_type": "resume_profile",
    "resource_id": "240d8e86-...",
    "resource_version": 4,
    "visibility": "private",
    "source_updated_at": "2026-07-28T03:00:00Z"
  },
  "content": {
    "content_type": "text/plain",
    "text": "规范化后的可检索文本",
    "content_hash": "sha256:..."
  },
  "metadata": {
    "title": "确认画像",
    "language": "zh-CN",
    "source_kind": "jobagent"
  }
}
```

约束：

- `schema_version` 必填，未知版本拒绝处理；
- `operation_id` 全局唯一，用于幂等；
- `resource_version` 单调递增；
- `visibility` 只能是受控枚举；
- `content_hash` 由规范化内容计算；
- `owner_user_id` 必须与服务端授权上下文匹配；
- metadata 采用 allowlist，不透传任意业务对象；
- 单个资源和单次请求必须有大小限制。

### 6.2 资源类型

第一版固定：

```text
resume_profile
saved_job
saved_job_analysis
browser_job_capture
public_knowledge
```

增加资源类型必须同时提供：

- JobAgent formatter；
- 字段级数据分类；
- chunk 策略；
- 引用解析器；
- 删除和重建测试。

### 6.3 可见性

第一版固定：

```text
private  - 仅资源所有者
public   - 所有已授权 JobAgent 用户
```

暂不实现 team、organization、shared-with-user 等共享模型。未来增加时扩展 ACL，
不能复用任意 metadata filter 代替授权。

---

## 7. 可检索文本规范

### 7.1 不直接 embedding 原始 JSON

每种资源由 JobAgent formatter 转换为稳定、可读、可引用的文本。例如：

```text
[资源] 用户画像
[姓名] 张三
[目标职位] Python 后端工程师

[项目经历 1]
项目名称：JobAgent
角色：后端开发
技术：Python、FastAPI、SQLite
成果：实现职位采集、匹配分析和面试准备工作流。
```

这样可以：

- 保留字段语义；
- 提高 embedding 和 BM25 效果；
- 避免 JSON 标点成为噪声；
- 让检索结果可以直接作为证据；
- 通过字段路径生成稳定引用。

### 7.2 ChunkMetadata

每个 chunk 至少包含：

```json
{
  "schema_version": "1",
  "tenant_id": "default",
  "owner_user_id": "b6d7f1b5-...",
  "visibility": "private",
  "resource_type": "resume_profile",
  "resource_id": "240d8e86-...",
  "resource_version": 4,
  "document_id": "doc-...",
  "chunk_id": "chunk-...",
  "chunk_index": 3,
  "field_path": "projects[0]",
  "content_hash": "sha256:...",
  "index_schema_version": 1
}
```

这些字段必须同时出现在 Chroma 和 BM25 的可过滤 metadata 中。

### 7.3 确定性 ID

建议使用以下输入计算稳定 chunk ID：

```text
tenant_id
+ owner_user_id
+ resource_type
+ resource_id
+ resource_version
+ chunk_index
+ content_hash
```

同一内容重复摄取应得到相同结果，版本变化必须能与旧版本区分。

### 7.4 引用

检索结果不能只返回自由文本，应返回可解析引用：

```json
{
  "resource_type": "saved_job",
  "resource_id": "...",
  "resource_version": 2,
  "field_path": "structured_jd.requirements[3]",
  "chunk_id": "...",
  "score": 0.82,
  "retrieval_sources": ["dense", "sparse"]
}
```

JobAgent 使用当前用户身份重新加载业务资源并验证版本。RAG 返回的文本是证据候选，
不是绕过 JobAgent Repository 的直接业务读取凭证。

---

## 8. RAG Catalog 设计

建议在 Modular RAG 中新增 `rag_catalog.db`。第一版可使用 SQLite，
但 Repository 接口不得依赖 SQLite 特有调用方式，以便未来替换。

### 8.1 `rag_documents`

```text
document_id             TEXT PRIMARY KEY
tenant_id               TEXT NOT NULL
owner_user_id           TEXT NULL
resource_type           TEXT NOT NULL
resource_id             TEXT NOT NULL
resource_version        INTEGER NOT NULL
visibility              TEXT NOT NULL
content_hash            TEXT NOT NULL
index_schema_version    INTEGER NOT NULL
status                  TEXT NOT NULL
chunk_count             INTEGER NOT NULL DEFAULT 0
source_updated_at       TEXT NOT NULL
created_at              TEXT NOT NULL
updated_at              TEXT NOT NULL
deleted_at              TEXT NULL
```

关键约束：

```text
UNIQUE (
  tenant_id,
  owner_user_id,
  resource_type,
  resource_id,
  resource_version
)
```

状态建议：

```text
pending
indexing
ready
delete_pending
deleted
failed
```

### 8.2 `rag_chunks`

```text
chunk_id                TEXT PRIMARY KEY
document_id             TEXT NOT NULL
chunk_index             INTEGER NOT NULL
field_path              TEXT NULL
content_hash            TEXT NOT NULL
token_count             INTEGER NULL
vector_indexed          INTEGER NOT NULL
sparse_indexed          INTEGER NOT NULL
created_at              TEXT NOT NULL
```

该表用于跨索引删除、诊断和修复。完整 chunk 文本可以保存在检索存储中，
目录库只保留管理所需信息，避免产生不必要的第三份私有正文。

### 8.3 `rag_index_operations`

```text
operation_id            TEXT PRIMARY KEY
operation_type          TEXT NOT NULL
document_id             TEXT NULL
request_hash            TEXT NOT NULL
status                  TEXT NOT NULL
attempts                INTEGER NOT NULL
error_code              TEXT NULL
error_message           TEXT NULL
created_at              TEXT NOT NULL
started_at              TEXT NULL
completed_at            TEXT NULL
```

同一 `operation_id` 配合不同 `request_hash` 必须拒绝，防止错误复用幂等键。

---

## 9. JobAgent 同步状态设计

### 9.1 `rag_index_outbox`

JobAgent 在业务事务中写入同步事件：

```text
event_id                TEXT PRIMARY KEY
user_id                 TEXT NOT NULL
resource_type           TEXT NOT NULL
resource_id             TEXT NOT NULL
resource_version        INTEGER NOT NULL
operation               TEXT NOT NULL
status                  TEXT NOT NULL
attempt_count           INTEGER NOT NULL
next_attempt_at         TEXT NULL
last_error_code         TEXT NULL
last_error_message      TEXT NULL
created_at              TEXT NOT NULL
completed_at            TEXT NULL
```

第一版可由本地 worker 轮询；生产方向应使用 durable worker。

### 9.2 `rag_resource_status`

```text
user_id
resource_type
resource_id
desired_version
indexed_version
sync_status
last_operation_id
last_synced_at
last_error_code
```

用途：

- UI 或管理员查看是否已完成索引；
- 避免业务表增加 RAG 专用字段；
- 检测 JobAgent 与 RAG 版本漂移；
- 驱动重试和重建。

### 9.3 Outbox payload

优先在 worker 执行时通过 JobAgent Repository 重新加载当前资源并格式化，
不要默认把完整简历/JD 长期复制到 outbox。

删除事件只需保留定位信息；如果资源已被业务数据库物理删除，仍能通知 RAG 清理。

---

## 10. 服务间认证与授权

### 10.1 服务身份

开发环境可使用固定 bearer token；正式环境使用可轮换的服务凭据。

最低要求：

- 凭据只存在服务端环境变量；
- 不出现在 URL、日志或前端；
- RAG 仅监听 loopback 或受信任内网；
- 所有管理接口都要求服务认证；
- 检索 MCP 端点也必须在多用户上线前启用认证。

### 10.2 用户委托上下文

JobAgent 生成短时、签名的委托上下文，或在受认证请求中发送由服务端校验的结构化
claim：

```json
{
  "issuer": "jobagent",
  "audience": "modular-rag",
  "tenant_id": "default",
  "subject_user_id": "...",
  "allowed_visibility": ["private", "public"],
  "allowed_resource_types": ["resume_profile", "saved_job"],
  "expires_at": "..."
}
```

RAG 必须验证：

- issuer/audience；
- 签名或受信任服务会话；
- 过期时间；
- tenant 和 subject；
- 请求范围不超过 claim。

### 10.3 不可信输入

以下内容不构成授权：

- MCP tool argument 中的任意 `user_id`；
- LLM 生成的 metadata filter；
- `collection` 名称；
- 文档路径；
- `resource_id` 本身；
- 前端传入但未经过 Repository 校验的 ID。

---

## 11. 检索授权模型

### 11.1 RetrievalContext

JobAgent 内部 typed adapter 接收：

```text
RetrievalContext
  tenant_id
  authenticated_user_id
  allowed_resource_types
  allowed_resource_ids (optional)
  include_public
```

适配器负责把它转换为 RAG 能验证的请求。业务调用方不直接构造底层 filters。

### 11.2 强制范围

私有检索的逻辑范围：

```text
(
  tenant_id = current_tenant
  AND owner_user_id = current_user
  AND visibility = private
)
OR
(
  tenant_id = current_tenant
  AND visibility = public
)
```

若当前 Chroma 版本难以安全表达 OR 条件，可将公共与私有数据分开查询后融合，
但两个查询都必须由服务端构造。

### 11.3 Chroma

要求：

- 在向量候选生成前执行 metadata filter；
- 只允许预定义标量字段；
- 禁止客户端覆盖强制权限字段；
- 返回后进行第二次防御性校验；
- 删除按完整资源身份和版本定位。

### 11.4 BM25

当前“全局 top_k 后再过滤”不满足正式要求。必须选择并实现一种方案：

#### 推荐第一版：逻辑分区

按以下 scope 建立可寻址分区：

```text
tenant/public
tenant/user/<opaque-user-id>
```

查询时只读取当前用户私有分区和公共分区，再进行融合。

优点：

- 权限边界清晰；
- 不会被其他用户候选挤占；
- 容易做跨用户泄漏测试；
- 适合现有文件型 BM25 实现。

缺点：

- 用户数量增加后文件和加载管理需要优化；
- 公共与私有结果需二次融合。

未来如果替换为支持过滤的全文检索引擎，保持上层契约不变。

### 11.5 摘要与管理查询

`get_document_summary` 必须通过 `document_id + RetrievalContext` 精确查询。
禁止在私有数据场景中：

- 无过滤列出全部记录；
- 根据用户输入对子串全库匹配；
- 因直接查询失败而回退到全库扫描。

---

## 12. 索引生命周期

### 12.1 新增

```text
JobAgent 写业务资源
-> 同事务写 outbox(upsert, version=N)
-> worker 加载已授权资源
-> formatter 生成标准文本
-> RAG 记录 operation
-> 切块和 embedding
-> 写 Chroma
-> 写 BM25
-> catalog 标记 ready
-> JobAgent 标记 indexed_version=N
```

### 12.2 更新

采用版本替换：

1. 新版本先进入 `indexing`；
2. 新版本 Chroma 和 BM25 都成功后标记 `ready`；
3. 查询只使用当前 ready 版本；
4. 清理旧版本；
5. 清理失败进入 reconciliation，不把半成品暴露给检索。

### 12.3 删除

```text
JobAgent 记录 delete outbox
-> RAG 标记 delete_pending
-> 删除 Chroma chunks
-> 删除 BM25 chunks/partition entries
-> 删除关联图片
-> catalog 标记 deleted
-> JobAgent 确认完成
```

删除操作必须幂等。任一存储失败时记录具体阶段并继续重试。

### 12.4 用户删除

必须提供按 `tenant_id + owner_user_id` 的受控批量清理流程，并验证：

- catalog 无 active document；
- Chroma 无该用户 metadata；
- BM25 无该用户分区或条目；
- 图片文件和 image index 已清理；
- trace 不保留正文；
- JobAgent outbox 和状态记录符合保留政策。

### 12.5 重建

RAG 索引是派生数据，应支持：

- 单资源重建；
- 单用户重建；
- 单资源类型重建；
- 全量重建；
- index schema 或 embedding 模型升级后的新版本重建。

全量重建不得要求 RAG 直接扫描 JobAgent 数据库，由 JobAgent 枚举已授权、
应索引资源并重新发送。

---

## 13. 故障、一致性与恢复

SQLite、Chroma 和 BM25 无法共享单一事务，因此采用状态机和补偿，而不是假装存在
跨存储 ACID 事务。

### 13.1 失败原则

- JobAgent 业务写入不因可选 RAG 暂时不可用而失败；
- 同步失败进入 outbox 重试；
- RAG 半完成操作不得成为可查询的 ready 版本；
- 重试使用相同 operation ID；
- 错误分为可重试和不可重试；
- 连续失败提供明确诊断，不无限高频重试。

### 13.2 建议错误码

```text
AUTH_INVALID
AUTH_SCOPE_DENIED
SCHEMA_UNSUPPORTED
RESOURCE_VERSION_STALE
CONTENT_TOO_LARGE
EMBEDDING_UNAVAILABLE
VECTOR_WRITE_FAILED
SPARSE_WRITE_FAILED
CATALOG_WRITE_FAILED
DELETE_INCOMPLETE
CONTRACT_INVALID
```

### 13.3 Reconciler

定期检查：

- catalog `indexing` 超时；
- `ready` 文档缺少 Chroma/BM25 chunk；
- `deleted` 文档仍残留索引；
- JobAgent desired version 与 indexed version 不同；
- 重复 chunk 或孤立图片。

修复动作必须有审计记录和上限。

---

## 14. Product Consumer 设计

第一位正式消费者建议是 Career Assistant 的“用户资料和收藏职位证据补充”，
而不是 Search V2 provider pipeline。

建议顺序：

1. 用户询问其确认画像中的经历、技能和项目；
2. 用户询问某个收藏职位的要求；
3. 用户比较自己的画像与一个或多个收藏职位；
4. 后续再考虑跨资源长期知识检索。

使用原则：

- 现有 Repository 精确读取仍优先用于已知资源 ID；
- RAG 用于“不知道具体在哪份资源或哪个字段”的语义发现；
- RAG 返回引用后，JobAgent 可按需重新加载当前业务资源确认版本；
- 无可靠证据时明确说明，不让模型补造用户经历；
- RAG 不可用时，助手可回退到现有 bounded repository retrieval；
- 检索结果必须经过证据预算和提示注入防护。

---

## 15. 实施阶段

### Phase 0：架构和契约冻结

目标：在写入真实用户数据前固定跨仓库合同。

JobAgent：

- 定义 `ResourceEnvelope`、`RetrievalContext` 和 typed response；
- 确定首批资源类型和 formatter 输入；
- 定义 outbox 与 resource status schema；
- 记录数据分类和禁止索引字段。

Modular RAG：

- 定义 catalog Repository 接口；
- 定义管理面请求和状态返回；
- 定义强制授权接口；
- 定义 Chroma/BM25 metadata schema。

交付物：

- 两仓库契约文档；
- JSON/Pydantic schema；
- 固定的契约测试 fixtures；
- 威胁模型和错误码。

退出条件：

- 两边对同一 fixture 序列化结果一致；
- 未知 schema version 明确失败；
- 没有真实用户数据写入 RAG。

### Phase 1：RAG Catalog 与安全索引核心

目标：让 RAG 自己具备可管理、可版本化、可删除的索引能力。

Modular RAG：

- 新增 catalog migration 和 Repository；
- 实现 deterministic document/chunk identity；
- ingestion pipeline 写入强制 metadata；
- Chroma 支持严格范围查询和删除；
- BM25 改造为 tenant/user 分区；
- 禁止无上下文私有查询；
- 移除摘要全库扫描 fallback；
- 增加 upsert/delete/status/reindex service API；
- 增加跨存储补偿状态。

验证：

- catalog 单元测试；
- Chroma 和 BM25 同一权限语义测试；
- 两用户隔离测试；
- 版本替换、删除和幂等测试；
- 服务重启后状态恢复测试。

退出条件：

- 用户 A 的任何工具调用均无法返回用户 B 的正文或 metadata；
- 旧版本不会出现在查询结果；
- 删除后所有派生存储无残留。

### Phase 2：JobAgent Outbox 与资源 Formatter

目标：让 JobAgent 可靠地把已授权业务资源同步为检索副本。

JobAgent：

- 新增 outbox 和 resource status migrations/repositories；
- 为 `resume_profile` 实现 formatter；
- 为 `saved_job` 实现 formatter；
- 在确认/更新/删除用例事务中写 outbox；
- 实现 bounded sync worker；
- 实现指数退避、重试上限和错误记录；
- 增加管理员诊断或 CLI；
- RAG 不可用时保持业务流程成功。

验证：

- formatter golden tests；
- 事务内业务写入与 outbox 一致性；
- 重复事件幂等；
- 服务中断与恢复；
- 删除前业务行不可读时仍能清理 RAG。

退出条件：

- 两种 P0 资源能够自动同步、更新和删除；
- JobAgent 可以显示 desired/indexed version；
- RAG 停机不会破坏核心 JobAgent 写入。

### Phase 3：授权 MCP 检索

目标：把当前基础 MCP 调用升级为正式、不可绕过的用户检索适配器。

JobAgent：

- typed adapter 接收 `RetrievalContext` 而非任意 filters；
- 注入服务认证与用户委托上下文；
- 静态 allowlist 增加正式授权工具；
- 验证响应中的 tenant、owner、resource type 和版本；
- 增加 evidence/citation response budget；
- 记录不包含正文的诊断指标。

Modular RAG：

- MCP handler 验证服务身份和委托上下文；
- 服务端组合强制权限范围；
- dense/sparse 分别召回后执行安全融合；
- 返回稳定引用和检索来源；
- 缺少/无效权限上下文时 fail closed。

退出条件：

- 不能通过 MCP 参数覆盖当前用户；
- 不能省略过滤条件读取私有全库；
- dense、sparse、summary 的权限行为完全一致。

### Phase 4：Career Assistant 首个产品接入

目标：在不改变 Search V2 的情况下，让用户实际使用私有 RAG。

JobAgent：

- 定义何时使用 RAG、何时精确读 Repository；
- 增加 bounded RAG retrieval tool；
- 将引用映射到用户拥有的业务资源；
- 处理 RAG unavailable/timeout/empty；
- 增加提示注入隔离和证据预算；
- 在回答中呈现可理解的来源。

验证：

- 简历技能、项目和收藏 JD 问答 fixtures；
- 无证据问题不得生成虚构个人经历；
- RAG 关闭时回退行为；
- 引用资源被删除/更新后的行为；
- 对话不能通过提示要求读取其他用户。

退出条件：

- 一条真实用户路径完成端到端验收；
- 回答可以定位回当前 JobAgent 资源；
- 失败不会导致跨用户或全库降级。

### Phase 5：质量评估、运维和生产准备

目标：证明不只是“能搜”，而是“搜得准、可维护、可恢复”。

- 建立招聘领域离线检索数据集；
- 对 dense、BM25、hybrid、rerank 分别测量；
- 记录 Recall@K、MRR、nDCG、空结果率和引用正确率；
- 记录索引延迟、查询延迟、失败率和索引大小；
- 执行备份与全量重建演练；
- 增加凭据轮换和数据保留策略；
- 定义 SQLite/Chroma 容量边界和升级条件；
- 决定是否迁移 PostgreSQL、pgvector、Qdrant 或全文检索服务。

退出条件：

- 达到确定的质量和延迟阈值；
- 用户删除和灾难恢复演练通过；
- 运维人员能够定位跨存储不一致。

---

## 16. 测试矩阵

### 16.1 权限测试

| 场景 | 预期 |
|---|---|
| A 查询 A 私有资源 | 返回 |
| A 查询 B 私有资源 ID | 拒绝或空结果 |
| A 使用 filter 声称自己是 B | 拒绝 |
| 不带用户上下文查询私有 collection | 拒绝 |
| A 查询公共知识 | 返回 |
| B 的高分 BM25 文档存在 | 不影响 A 的候选召回 |
| 摘要直接查询 B document ID | 拒绝 |
| list/debug/trace 接口 | 不泄露 B metadata |

### 16.2 生命周期测试

| 场景 | 预期 |
|---|---|
| 相同 upsert 重放 | 不产生重复 chunk |
| 相同 operation ID、不同 payload | 拒绝 |
| version 4 后收到 version 3 | 标记 stale，不覆盖 |
| Chroma 成功、BM25 失败 | 不发布 ready，支持补偿 |
| 删除请求重放 | 成功且无副作用 |
| 用户删除 | 所有派生数据清理 |
| 全部索引丢失 | 可从 JobAgent 重建 |

### 16.3 质量测试

至少覆盖：

- 中英文混合技术词；
- 同义表达；
- 精确公司名、技术名和职位名；
- 多份简历项目之间的区分；
- 多个相似 JD；
- 无答案问题；
- chunk 边界问题；
- 新旧资源版本；
- public/private 混合查询。

---

## 17. 可观测性与隐私

允许记录：

- operation ID；
- 资源类型；
- opaque resource/document ID；
- 版本；
- chunk 数量；
- 检索阶段耗时；
- dense/sparse 候选数量；
- 错误码；
- 使用的模型和 index schema version。

默认禁止记录：

- 完整简历；
- 完整 JD；
- 用户问题全文长期日志；
- embedding；
- bearer token；
- 委托 claim 原文；
- 其他用户资源 metadata。

如需调试正文，必须有显式开发开关、内容截断和本地保留期限。

---

## 18. 配置建议

JobAgent：

```text
JOBAGENT_RAG_MCP_URL
JOBAGENT_RAG_MCP_TIMEOUT_SECONDS
JOBAGENT_RAG_MCP_MAX_RESPONSE_CHARS
JOBAGENT_RAG_SERVICE_TOKEN
JOBAGENT_RAG_SYNC_ENABLED
JOBAGENT_RAG_SYNC_BATCH_SIZE
JOBAGENT_RAG_SYNC_MAX_ATTEMPTS
```

Modular RAG：

```text
RAG_SERVICE_TOKEN
RAG_CATALOG_DB_PATH
RAG_CHROMA_PATH
RAG_BM25_PATH
RAG_AUTH_REQUIRED
RAG_MAX_RESOURCE_CHARS
RAG_INDEX_SCHEMA_VERSION
RAG_TRACE_CONTENT_ENABLED
```

生产中 secret 不进入 `.env.example` 的真实值、不进入日志、不传到浏览器。

---

## 19. API 和工具命名建议

管理面可以使用内部 HTTP API，或使用不暴露给 LLM 的独立 MCP 管理工具。
优先建议内部 HTTP API，避免管理能力与模型工具发现混在一起：

```text
POST   /internal/v1/resources:upsert
POST   /internal/v1/resources:delete
POST   /internal/v1/resources:reindex
GET    /internal/v1/operations/{operation_id}
POST   /internal/v1/reconcile
```

检索面保留 MCP，并演进为明确授权语义：

```text
search_authorized_knowledge
get_authorized_document_summary
```

不建议继续把任意 `filters` 作为正式业务接口。底层存储 filters 只存在于 RAG
服务内部。

---

## 20. 迁移和兼容策略

1. 保留现有三个基础工具用于诊断，但不得用于私有用户数据。
2. 新授权工具和 catalog 先在独立测试 collection/index namespace 验证。
3. 旧测试 PDF 和开发知识库标记为 `public` 或迁移到开发专用 namespace。
4. 私有数据接入前启用 `RAG_AUTH_REQUIRED=true`。
5. JobAgent 在正式消费者完成前保持 RAG integration disabled by default。
6. 新旧索引通过 `index_schema_version` 区分，不原地猜测 metadata。
7. embedding 模型变化视为索引版本升级并触发重建。

---

## 21. 明确非目标

本计划第一阶段不包含：

- 把 RAG 合并进 Search V2；
- 让 RAG 成为职位网络 Provider；
- 让前端直接连接 MCP；
- 让 LLM 自由浏览所有 MCP 工具；
- 将所有 JobAgent 表复制进 RAG；
- 将认证记录、密码或 token 向量化；
- 实现组织共享、多人协作 ACL；
- 为了集成立即更换所有数据库；
- 让 JobAgent 与 RAG 共享同一个数据库账号；
- 用 RAG 索引替代 JobAgent 业务 Repository。

---

## 22. 推荐的首个开发切片

第一个可独立验收的切片应为：

> 在 Modular RAG 中实现版本化 `rag_documents` catalog、强制
> `tenant_id/owner_user_id/visibility` metadata，以及两个测试用户的
> Chroma/BM25 隔离测试；暂不接入真实 JobAgent 用户数据。

原因：

- 它先建立安全地基；
- 不修改 JobAgent 业务流程；
- 可以用合成数据验证；
- 能暴露 BM25 分区和跨存储删除问题；
- 完成后才适合实现 JobAgent outbox。

该切片验收标准：

1. 合成用户 A、B 分别写入一份文档；
2. A 的 authorized query 只能得到 A 和公共文档；
3. B 的高分关键词文档不能挤掉 A 的 BM25 结果；
4. 缺少授权上下文时私有查询失败；
5. 更新 A 文档后旧版本不可检索；
6. 删除 A 文档后 catalog、Chroma、BM25 均无残留；
7. 服务重启后上述状态保持；
8. 所有测试网络无关且确定性通过。

---

## 23. 完成定义

只有同时满足以下条件，才能称为“JobAgent 已正式接入 Modular RAG”：

- JobAgent 业务数据库仍是事实来源；
- RAG 有正式 catalog 和可重建索引；
- P0 资源自动完成新增、更新和删除同步；
- 服务间认证启用；
- 用户身份不可由 LLM 或客户端伪造；
- Chroma 和 BM25 都在授权范围内召回；
- 摘要、图片、debug、trace 不绕过权限；
- 多用户隔离测试通过；
- RAG 故障不破坏 JobAgent 核心业务；
- 索引版本漂移可检测和修复；
- 用户删除能清除所有派生副本；
- Career Assistant 至少有一条真实、带引用的端到端使用路径；
- 有离线质量基线和灾难恢复验证。

在此之前，应使用“基础 MCP 已连接”“安全索引已完成”或“业务同步已完成”等
更准确的阶段描述，避免把协议连通误认为完整产品能力。
