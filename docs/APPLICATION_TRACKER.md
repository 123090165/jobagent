# Application Tracker

> 用途：记录 JobAgent 的投递跟进最小状态机。当前 tracker 只管理本地岗位的求职状态，不做自动投递。

## 1. 当前目标

把岗位库中的岗位推进到求职跟进流程：

```text
job_posting -> application_record -> status / notes / next_action
```

如果已经保存了简历版本，也可以形成更完整的链路：

```text
job_posting + resume_version -> application_record
```

当前不做：

- 不做自动投递。
- 不做招聘网站登录。
- 不做验证码处理。
- 不做日历提醒。
- 不做多用户权限。

## 2. 状态定义

当前支持 6 个状态：

- `interested`：感兴趣，准备评估或定制简历。
- `applied`：已投递。
- `interviewing`：面试中。
- `rejected`：已拒绝。
- `offer`：已拿 offer。
- `archived`：归档，不再跟进。

## 3. 数据字段

每条跟进记录包含：

- `job_id`
- `status`
- `notes`
- `next_action`
- `resume_version_id`
- `resume_version_label`
- `created_at`
- `updated_at`

当前一个岗位只保留一条 tracker 记录。重复保存同一 `job_id` 会更新原记录。

`resume_version_id` 用于关联真实简历版本；`resume_version_label` 保留为轻量标签和旧数据兼容字段。

## 4. API

创建或更新跟进记录：

```json
POST /applications
{
  "job_id": 1,
  "status": "interested",
  "notes": "岗位匹配度不错",
  "next_action": "定制简历",
  "resume_version_id": 1,
  "resume_version_label": "v1-fastapi-backend"
}
```

更新跟进状态：

```json
PATCH /applications/1
{
  "status": "applied",
  "next_action": "等待反馈"
}
```

列表：

```text
GET /applications
GET /applications?status=applied
GET /applications?keyword=FastAPI
```

详情：

```text
GET /applications/1
```

## 5. 开发难点

- tracker 要依附岗位库，不能凭空创建岗位。
- 状态要有明确枚举，不要随手写自由字符串。
- 简历版本应该通过 `resume_version_id` 结构化关联，不能只靠备注文本。
- route 只负责请求响应，状态保存逻辑放 service/repository。
- 当前不做复杂状态转移限制，先保证本地跟进闭环。

## 6. 面试官可能追问

- 为什么 tracker 依赖 `job_posting_id`？
- 当前状态机为什么只有 6 个状态？
- 为什么一个岗位只保留一条 tracker 记录？
- 如果未来多用户，表结构要怎么改？
- 为什么不做自动投递？
- 为什么既保留 `resume_version_id`，又保留 `resume_version_label`？
