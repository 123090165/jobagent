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
  "use_llm_jd": false
}
```

返回：

- `resume_profile`
- `job_analysis`
- `match_report`
- `optimization_result`
- `project_challenge_report`
- `markdown_report`

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
- 暂不接数据库。
- 暂不做用户系统。
- 暂不做自动投递。
- `use_llm_jd` 只影响 JDAnalysisAgent，失败时回退 mock。

## 4. 开发难点

这一阶段的重点不是“接口越多越好”，而是：

- 保持 API route 很薄。
- 保持 schema 和 service 可复用。
- 错误输入要返回清晰 HTTP 状态码。
- 未来前端、测试、自动化流程都能复用 API。

## 5. 面试官可能追问

- 为什么要在 Streamlit 之外再加 FastAPI？
- API route 和 service 的边界是什么？
- 为什么 `/analyze/full` 和拆步骤接口都需要？
- 如果 LLM 调用失败，API 怎么处理？
- 后续接数据库时，哪些接口需要变化？
