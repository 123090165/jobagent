# SQLite Storage

> 用途：记录 JobAgent 的本地 SQLite 存储设计。当前只保存完整分析记录，为后续 JD 库、简历版本、报告历史和 tracker 打基础。

## 1. 当前目标

这一阶段只做最小存储闭环：

```text
简历 + JD -> 分析报告 -> 可选保存到 SQLite -> 按 record_id 读取
```

当前不做：

- 不做用户系统。
- 不做登录权限。
- 不做复杂数据库迁移。
- 不做 PostgreSQL。
- 不做投递 tracker。

## 2. 数据库位置

默认数据库文件：

```text
data/jobagent.sqlite3
```

可以用环境变量覆盖：

```powershell
$env:JOBAGENT_DB_PATH="data/dev.sqlite3"
```

数据库文件已经被 `.gitignore` 忽略，不会提交到 Git。

## 3. 当前数据表

- `resume_records`：保存原始简历文本和结构化简历。
- `job_postings`：保存原始 JD 和结构化 JD 分析。
- `match_reports`：保存匹配报告和总分。
- `project_challenges`：保存项目追问。
- `analysis_records`：把一次完整分析串起来，并保存 Markdown 报告。

## 4. API 用法

保存完整分析：

```json
POST /analyze/full
{
  "resume_text": "简历文本",
  "jd_text": "JD 文本",
  "save_result": true
}
```

返回中会包含：

```json
{
  "record_id": 1
}
```

读取保存记录：

```text
GET /records/1
```

列出保存记录：

```text
GET /records?keyword=Python&limit=20
```

列出岗位库：

```text
GET /jobs?keyword=FastAPI&limit=20
```

读取岗位详情：

```text
GET /jobs/1
```

## 5. 简单去重策略

当前去重规则：

```text
raw_jd 完全相同 -> 复用同一条 job_posting
```

这意味着：

- 同一份 JD 被多次分析，只会保存一条岗位记录。
- 每次分析仍会生成新的 resume、match_report、project_challenge 和 analysis_record。
- 暂不做语义去重，例如“同一岗位但 JD 文案略有不同”不会合并。

语义去重需要 embedding、相似度阈值或人工确认，放到后续 RAG / Job Database 增强阶段。

## 6. 开发难点

SQLite 这一阶段的重点不是表很多，而是：

- 原始文本和结构化结果都要保存。
- 保存逻辑不要写进 API route。
- 测试必须使用临时数据库，不能污染本地真实数据。
- 数据库文件不能提交到 Git。
- 先保存完整分析记录，再逐步扩展成 JD 库和 tracker。
- 列表接口返回摘要，详情接口返回完整 JSON，避免列表过重。

## 7. 面试官可能追问

- 为什么 SQLite 起步，而不是直接 PostgreSQL？
- 为什么既保存原始文本，又保存结构化 JSON？
- 数据库表为什么这样拆？
- 如何保证测试不污染真实数据库？
- 后续做多用户时需要改哪里？
- 现在的 JD 去重为什么只做完全匹配？
