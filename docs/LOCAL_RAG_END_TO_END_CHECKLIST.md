# JobAgent × Modular RAG 本地验收状态

## 结论

截至 2026-07-29，本地真实技术链路已经完成自动化验收：

~~~text
JobAgent business write
-> durable outbox
-> RAG sync worker
-> authenticated management API
-> Chroma and BM25 derived indexes
-> authorized MCP retrieval
-> JobAgent ownership and version validation
-> update, retry, and delete lifecycle
~~~

当前状态可以描述为：

- Modular RAG MCP、管理面和私有索引链路可用；
- JobAgent 现有 Resume Profile 和 Saved Job 已完成首次同步；
- RAG 故障不会破坏 JobAgent 业务写入，恢复后可以重试；
- 技术链路已通过，但使用真实业务问题的语义相关性仍需用户判断。

本次验收结束时，本地运行状态为：

| 服务 | 地址 | 状态 |
|---|---|---|
| JobAgent API | `http://127.0.0.1:8000` | running，HTTP 200 |
| JobAgent Web | `http://127.0.0.1:5173` | running，HTTP 200 |
| Modular RAG | `http://127.0.0.1:8002/mcp` | running，MCP inspection passed |
| RAG Sync Worker | 独立 watch 进程 | running |

## 已由 Codex 完成

### 配置与自动化

- 新增 `scripts/verify-rag-live.ps1`，统一加载 `.env.deepseek.local`。
- 脚本自动补齐本地 MCP 和管理端点、隐藏服务令牌并检查必需工具。
- `rag_admin`、`run_rag_sync` 和 `evaluate_rag_quality` 会自动加载本地环境文件。
- Live 测试使用唯一检索标记，避免历史测试数据影响结果。
- Live 测试在后续断言失败时自动删除本次已建立的测试索引。
- 已清理早期失败运行遗留的一条测试索引。

### 数据安全

- JobAgent SQLite 已备份到：

~~~text
D:\projects\jobagent\data\backups\jobagent-20260729-210848.sqlite3
~~~

- 备份大小为 `2,605,056` bytes。
- 自动化 Live 测试使用临时 JobAgent 数据库和隔离测试资源。
- 测试输出不打印服务令牌、用户标识、简历正文或 JD 正文。

### MCP 与生命周期

统一验证命令：

~~~powershell
Set-Location 'D:\projects\jobagent'
.\scripts\verify-rag-live.ps1
~~~

2026-07-29 实际结果：

~~~text
MCP inspection passed.
2 passed in 9.39s
Live RAG verification passed.
~~~

两项 Live 测试覆盖：

1. Saved Job 写入、Outbox、Worker、真实 RAG 管理面、授权 MCP 检索和删除；
2. 不可达管理端点、JobAgent 写入继续成功、失败事件持久化、恢复后重试、检索和清理。

### 检索质量与权限

隔离的 `career-private-v1` Live fixture 结果：

| 指标 | 结果 |
|---|---:|
| Case count | 4 |
| Hit Rate | 1.0 |
| Recall@K | 1.0 |
| Precision@K | 0.3333 |
| MRR | 1.0 |
| Forbidden hits | 0 |
| Mean latency | 187.82 ms |

这些指标证明当前固定样本可以被召回，且另一用户拥有的同查询资源不会泄漏。它们不代表大规模真实岗位上的最终语义准确率。

### 现有开发数据同步

本地 JobAgent 数据库扫描结果：

| 项目 | 数量 |
|---|---:|
| Active users | 3 |
| Active Resume Profiles | 4 |
| Active Saved Jobs | 6 |
| Indexed resources | 10 |
| Ready | 10 |
| Pending | 0 |
| Failed | 0 |

首次 backfill 实际结果：

~~~text
resources_scanned=10
events_enqueued=10
claimed=10
completed=10
failed=0
~~~

随后执行 reconcile：

~~~text
resources_scanned=10
upserts_enqueued=0
deletes_enqueued=0
resources_skipped=10
~~~

这表示 JobAgent 当前业务资源与同步状态没有发现漂移。RAG 保存的是可重建派生副本，JobAgent SQLite 仍是事实来源。

### 自动化回归

- RAG admin、sync、status API 和 quality tests：`16 passed`。
- 前端生产构建：通过，`2906 modules transformed`。
- 前端仍有一个非阻塞的 bundle size 警告，当前主 JS 约 `771.24 kB`。

## 当前 embedding 状态

Modular RAG 的本地 `.env` 同时包含两组 embedding 配置。配置解析采用最后一个同名键，因此当前实际生效的是：

~~~text
EMBEDDING_PROVIDER=local_hash
EMBEDDING_MODEL=local-hash-v1
EMBEDDING_DIMENSIONS=384
~~~

文件中较早出现的 `ollama / bge-m3 / 1024` 当前不会生效。

`local_hash` 足以验证协议、权限、同步和生命周期，但不能作为最终语义质量结论。切换到 `bge-m3` 会改变向量维度，需要使用新的兼容 Chroma namespace 或重建派生索引，因此本次没有擅自切换。

## 只需要用户确认的事项

以下项目无法由技术断言替代，其他搭建、同步和自动验证步骤不需要用户重复执行。

### 1. 判断真实回答是否有帮助

登录 JobAgent，打开：

~~~text
http://localhost:5173/assistant
~~~

用自己的实际资料提出 2–3 个需要跨资源发现的问题，例如：

~~~text
我保存的哪些岗位同时要求 Python 和 Kubernetes？
我的哪些经历最能支持平台工程岗位？
对比我保存的两个目标岗位，它们的核心能力差异是什么？
~~~

只需确认：

- 引用是否指向正确的个人 Resume Profile 或 Saved Job；
- 证据是否真正回答了问题；
- 没有证据时是否明确说明，而不是编造。

将结论告诉 Codex：`可用`、`部分可用` 或 `不可用`，并提供一个失败问题即可。不要发送简历原文、JD 全文或服务令牌。

### 2. 决定何时切换真实 embedding

如果当前只继续开发业务流程，保持 `local_hash` 即可。

如果下一步要评价真实中文简历和中英文 JD 的语义准确率，需要确认切换到 `bge-m3`。确认后由 Codex 完成：

- 清理重复 embedding 配置；
- 创建兼容的 Chroma namespace；
- 重建 10 个派生资源；
- 重跑 Live fixture；
- 记录切换前后的检索指标。

## 后续复验

配置、索引代码或 MCP 契约改变后，由 Codex 运行：

~~~powershell
.\scripts\verify-rag-live.ps1
.\.venv\Scripts\python.exe -m scripts.evaluate_rag_quality --mode live
.\.venv\Scripts\python.exe -m scripts.rag_admin reconcile
~~~

用户不需要手工逐个设置环境变量、运行 pytest、执行 backfill 或处理测试索引。
