# Streamlit App

> 用途：记录 JobAgent 当前 Streamlit 页面能力和使用边界。Streamlit 仍然是 MVP 展示层，核心业务逻辑仍然放在 service、agent 和 storage 中。

## 1. 启动方式

```powershell
.venv\Scripts\python.exe -m streamlit run frontend/streamlit_app.py
```

## 2. 当前页面

### 生成报告

用途：

- 输入简历文本。
- 可上传 `.txt` / `.md` 简历文件，并把提取出的文本填入简历输入区；默认文件大小限制为 1MB。
- 输入目标岗位 JD。
- 可选启用 LLM JD 分析。
- 可选启用 LLM 简历优化；失败时自动回退 mock。
- 可选保存本次分析到 SQLite。
- 展示 Markdown 报告、结构化结果、项目追问和 workflow 执行轨迹。
- 执行轨迹包含步骤数、总耗时、fallback 数、`workflow_run_id` 和每步摘要。

### 历史记录

用途：

- 查看已保存的分析记录。
- 按关键词搜索历史记录。
- 查看某条记录的 Markdown 报告、workflow 执行轨迹和结构化详情。
- 执行轨迹来自已保存的 SQLite 记录，不在页面端重新计算。

### 岗位库

用途：

- 查看已保存的岗位 JD。
- 按关键词搜索岗位。
- 查看岗位原始 JD 和结构化分析。
- 查看同一 JD 被分析过多少次。

### 简历版本

用途：

- 保存原始简历文本。
- 保存针对目标岗位定制后的简历版本。
- 可选关联岗位库中的岗位。
- 查看版本列表和版本详情。

### 投递跟进

用途：

- 从岗位库中选择岗位。
- 标记求职状态。
- 记录备注、下一步行动和简历版本。
- 可选择已保存的简历版本，也可以继续手动填写轻量标签。
- 查看当前 tracker 列表。

## 3. 当前边界

- 不做 URL 抓取。
- 不做招聘网站登录。
- 不做验证码处理。
- 不做自动投递。
- 不做 PDF/DOCX 简历解析。
- 不做复杂前端路由。
- 不做多用户权限。

## 4. 开发难点

这一阶段的重点是：

- 页面只展示和触发已有服务，不重新写业务逻辑。
- 简历文件上传只调用 `resume_file_service` 提取纯文本，不在页面里实现解析规则。
- 文件大小限制也由 `resume_file_service` 统一校验，页面只展示错误 message。
- 保存能力调用 `storage_service`，不在页面里写 SQL。
- 简历版本能力调用 `resume_version_service`，不在页面里直接操作 SQLite。
- 生成报告页必须通过 `run_job_analysis_workflow` 拿到 `workflow_steps`，不能绕回旧的底层 mock 函数。
- LLM JD 分析和 LLM 简历优化都只通过 workflow 参数触发，页面不直接调用 LLM。
- 历史记录页只展示 storage 返回的 trace，不自行推断某次分析用了 mock、LLM 还是 fallback。
- 页面只负责把 `duration_ms` 做摘要展示，不负责计时。
- 历史记录和岗位库列表只展示摘要，详情再展示完整内容。
- 用户没有配置 LLM API key 时，页面仍然可用。

## 5. 面试官可能追问

- 为什么 MVP 前端使用 Streamlit？
- Streamlit 页面和 FastAPI API 的关系是什么？
- 为什么页面不直接操作 SQLite？
- 为什么文件上传逻辑放在 service，而不是写在 Streamlit 页面里？
- 历史记录和岗位库为什么分开？
- 为什么执行轨迹放在历史记录详情，而不是放在列表里？
- 为什么耗时统计应该由 workflow 产生，而不是页面产生？
- 后续迁移到 Next.js 时，哪些逻辑可以复用？
- 为什么投递跟进依赖岗位库，而不是直接手填岗位？
- 为什么简历版本要单独成页，而不是只放在 tracker 表单中？
