# Resume Versioning

> 用途：记录 JobAgent 的简历版本管理设计。它把“针对某个 JD 定制过的简历”从普通备注升级为可追踪数据，方便后续投递跟进、版本对比和面试复盘。

## 1. 当前目标

当前阶段做最小但真实的简历版本闭环：

```text
base_resume_text + target_job -> resume_version -> application_record
```

也就是说：

- 原始简历文本继续保留。
- 针对目标岗位定制后的文本单独保存。
- 简历版本可以关联岗位。
- 简历版本可以关联一次分析记录。
- 投递 tracker 可以通过 `resume_version_id` 关联到具体版本。

## 2. 当前不做

- 不自动改写简历。
- 不编造经历、公司、项目、数据或技术栈。
- 不覆盖原始简历。
- 不做复杂版本 diff。
- 不做多人协作和权限系统。

## 3. 数据字段

`resume_versions` 当前包含：

- `label`：版本标签，例如 `v1-fastapi-backend`。
- `base_resume_text`：原始简历文本。
- `tailored_resume_text`：针对目标岗位调整后的简历文本。
- `target_job_posting_id`：可选关联岗位。
- `source_analysis_record_id`：可选关联分析记录。
- `notes`：版本备注。
- `created_at`
- `updated_at`

## 4. API

创建简历版本：

```json
POST /resume-versions
{
  "label": "v1-fastapi-backend",
  "base_resume_text": "原始简历文本",
  "tailored_resume_text": "针对目标 JD 调整后的简历文本",
  "target_job_id": 1,
  "source_analysis_record_id": 1,
  "notes": "突出 FastAPI、SQL 和 API 设计经验"
}
```

列表：

```text
GET /resume-versions
GET /resume-versions?keyword=FastAPI
GET /resume-versions?target_job_id=1
```

详情：

```text
GET /resume-versions/1
```

投递 tracker 关联简历版本：

```json
POST /applications
{
  "job_id": 1,
  "status": "interested",
  "resume_version_id": 1,
  "next_action": "使用该版本投递"
}
```

## 5. 开发难点

- 简历版本不能覆盖原始简历，必须保留来源。
- 定制版本可以为空，因为用户可能先建标签，再逐步完善文本。
- `resume_version_id` 是结构化关联，`resume_version_label` 保留为兼容旧 tracker 的轻量备注。
- 版本可以关联岗位和分析记录，但这两个关联都是可选的，方便用户先保存通用版本。
- 当前不做 diff，否则会把版本管理复杂度提前放大。

## 6. 面试官可能追问

- 为什么需要独立 `resume_versions` 表，而不是只在 tracker 里写标签？
- 为什么保存原始简历和定制后简历两份文本？
- 如何防止优化后的版本编造经历？
- 如果用户针对同一个岗位做多个版本，怎么区分？
- 后续如果做版本对比，当前结构能否支撑？
- 多用户场景下需要加哪些字段？

## 7. 后续方向

- 从分析记录中一键生成初始简历版本。
- 支持版本对比和修改摘要。
- 把简历版本和投递结果关联，用于复盘哪些表达更有效。
- 在引入 LLM 优化 Agent 后，把建议和用户确认后的版本分开保存。
