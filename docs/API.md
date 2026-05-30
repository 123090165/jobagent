# JobAgent API

> 用途：记录 FastAPI 后端层的接口。当前 API 只是薄封装，核心业务逻辑仍然放在 `app/services/` 和 `app/agents/`。

## 1. 启动方式

```powershell
.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

默认访问：

```text
http://127.0.0.1:8000
```

交互式文档：

```text
http://127.0.0.1:8000/docs
```

## 2. 当前接口

### GET /health

用途：健康检查。

返回：

```json
{
  "status": "ok",
  "version": "0.3.0"
}
```

### POST /analyze/full

用途：端到端分析。

请求：

```json
{
  "resume_text": "简历文本",
  "jd_text": "JD 文本",
  "use_llm_jd": false,
  "save_result": false
}
```

返回：

- `resume_profile`
- `job_analysis`
- `match_report`
- `optimization_result`
- `project_challenge_report`
- `markdown_report`
- `workflow_steps`：本次 workflow 的步骤轨迹，每步包含 `name`、`status`、`mode`、`summary`、`fallback_reason` 和 `guardrails`
- `record_id`：当 `save_result` 为 `true` 时返回保存记录 ID，否则为 `null`

示例：

```json
{
  "record_id": 1,
  "workflow_steps": [
    {
      "name": "JDAnalysisAgent",
      "status": "completed",
      "mode": "fallback",
      "summary": "识别岗位 Python 后端开发，必备技能 4 个。",
      "fallback_reason": "llm_service_error",
      "guardrails": ["不编造 JD 中不存在的信息"]
    }
  ]
}
```

### GET /records/{record_id}

用途：读取已保存的完整分析记录。

返回：

- `id`
- `created_at`
- `resume_profile`
- `job_analysis`
- `match_report`
- `optimization_result`
- `project_challenge_report`
- `markdown_report`
- `workflow_steps`：保存分析时写入的 workflow step trace；旧记录可能为空列表。

### GET /records

用途：列出已保存的分析记录摘要。

查询参数：

- `limit`：最多返回多少条，默认 20，最大 100。
- `keyword`：按岗位标题、公司、JD 原文或结构化分析 JSON 搜索。

返回：

- `id`
- `created_at`
- `job_title`
- `company`
- `overall_score`

### POST /resume/parse

用途：单独解析简历。

请求：

```json
{
  "resume_text": "简历文本"
}
```

返回：`ResumeProfile`

### POST /jobs/analyze

用途：单独分析 JD。

请求：

```json
{
  "jd_text": "JD 文本",
  "use_llm": false
}
```

返回：`JobAnalysis`

### GET /jobs

用途：列出已保存的岗位 JD 摘要。

查询参数：

- `limit`：最多返回多少条，默认 20，最大 100。
- `keyword`：按岗位标题、公司、JD 原文或结构化分析 JSON 搜索。

返回：

- `id`
- `created_at`
- `job_title`
- `company`
- `keyword_text`
- `analysis_count`

### GET /jobs/{job_id}

用途：读取已保存的岗位 JD 详情。

返回：

- `id`
- `created_at`
- `raw_jd`
- `job_analysis`
- `analysis_count`

### GET /applications

用途：列出投递跟进记录。

查询参数：

- `limit`：最多返回多少条，默认 20，最大 100。
- `status`：按状态筛选。
- `keyword`：按岗位、公司、JD、备注或下一步行动搜索。

### POST /applications

用途：为岗位创建或更新投递跟进记录。

请求：

```json
{
  "job_id": 1,
  "status": "interested",
  "notes": "岗位匹配度不错",
  "next_action": "定制简历",
  "resume_version_id": 1,
  "resume_version_label": "v1"
}
```

### GET /applications/{application_id}

用途：读取单条投递跟进记录。

### PATCH /applications/{application_id}

用途：更新投递状态、备注、下一步行动或简历版本。

### GET /resume-versions

用途：列出已保存的简历版本。

查询参数：

- `limit`：最多返回多少条，默认 20，最大 100。
- `keyword`：按版本标签、简历文本、备注、岗位标题或公司搜索。
- `target_job_id`：按关联岗位筛选。

### POST /resume-versions

用途：创建简历版本。

请求：

```json
{
  "label": "v1-fastapi-backend",
  "base_resume_text": "原始简历文本",
  "tailored_resume_text": "针对目标 JD 调整后的简历文本",
  "target_job_id": 1,
  "source_analysis_record_id": 1,
  "notes": "突出 FastAPI、SQL 和 API 设计经验"
}
```

当前约束：

- `base_resume_text` 保存原始简历，不会被覆盖。
- `tailored_resume_text` 保存用户确认后的定制版本，可以为空。
- `target_job_id` 和 `source_analysis_record_id` 都是可选关联。
- 不自动生成或编造简历经历。

### GET /resume-versions/{resume_version_id}

用途：读取单条简历版本详情。

返回：

- `id`
- `label`
- `base_resume_text`
- `tailored_resume_text`
- `target_job_id`
- `target_job_title`
- `target_company`
- `source_analysis_record_id`
- `notes`
- `created_at`
- `updated_at`

### POST /match/analyze

用途：根据结构化简历和 JD 生成匹配报告。

请求：

```json
{
  "resume_profile": {},
  "job_analysis": {}
}
```

返回：`MatchReport`

### POST /reports/generate

用途：根据上游结构化结果生成 Markdown 报告。

请求：

```json
{
  "resume_profile": {},
  "job_analysis": {},
  "match_report": {},
  "optimization_result": {},
  "project_challenge_report": {}
}
```

返回：

```json
{
  "markdown_report": "# JobAgent 求职分析报告..."
}
```

## 3. 当前边界

- API 层不写复杂业务逻辑。
- `/analyze/full` 必须走 `run_job_analysis_workflow`，由 workflow 产生 `workflow_steps`。
- 保存分析记录时，API 只把 `workflow_steps` 交给 storage service，不直接写 SQL。
- 当前提供本地 SQLite 保存能力，不做用户系统。
- `GET /jobs` 只查询已保存 JD，不抓取外部网站。
- `/applications` 只做本地 tracker，不执行自动投递。
- `/resume-versions` 只保存用户提供的原始简历和定制文本，不自动编造经历。
- 暂不做用户系统。
- 暂不做自动投递。
- `use_llm_jd` 只影响 JDAnalysisAgent，失败时回退 mock。

## 4. 开发难点

这一阶段的重点不是“接口越多越好”，而是：

- 保持 API route 很薄。
- 保持 schema 和 service 可复用。
- 保持 workflow trace 可观察，但不把底层异常原文暴露给用户。
- 错误输入要返回清晰 HTTP 状态码。
- 未来前端、测试、自动化流程都能复用 API。

## 5. 面试官可能追问

- 为什么要在 Streamlit 之外再加 FastAPI？
- API route 和 service 的边界是什么？
- 为什么 `/analyze/full` 和拆步骤接口都需要？
- 如果 LLM 调用失败，API 怎么处理？
- `workflow_steps` 为什么放在完整分析响应和历史记录详情里，而不是列表接口里？
- 后续接数据库时，哪些接口需要变化？
