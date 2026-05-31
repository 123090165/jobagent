# Demo Script

> 用途：本地演示 JobAgent 时的顺序脚本，适合录屏、答辩或面试现场展示。

## 1. 启动 Streamlit

```powershell
.venv\Scripts\python.exe -m streamlit run frontend/streamlit_app.py
```

打开页面后先说明：JobAgent 是本地求职准备工作台，核心是简历和 JD 匹配、优化建议、项目追问、历史复盘和投递跟进，不做自动投递。

## 2. 上传 txt/md 简历

在“生成报告”页点击“上传简历文件（.txt / .md）”，选择 `data/samples/sample_resume.md` 或自备 UTF-8 txt/md 文件。

演示点：

- 上传成功后，文件内容会填入“简历文本”输入区。
- 当前默认限制文件最大 1MB，可通过 `JOBAGENT_MAX_RESUME_FILE_BYTES` 调整。
- PDF/DOCX 暂不支持，后续再评估轻量文本提取方案。

## 3. 粘贴 JD

把目标岗位 JD 粘贴到右侧“目标岗位 JD”文本框。可以使用 `data/jd_examples/sample_jd.md`。

演示点：

- JD 原文会作为后续 JDAnalysisAgent 的输入。
- 可选 LLM 只影响 JDAnalysisAgent，失败时会 fallback 到 mock。

## 4. 生成报告

保留“保存本次分析”勾选，点击“生成分析报告”。

演示点：

- 生成匹配分数、Markdown 报告、结构化结果和项目追问。
- 文本输入流程仍然可用，不依赖文件上传。

## 5. 查看 workflow trace

切到“结构化结果”，先看“执行轨迹”。

演示点：

- 展示 6 个 Agent 步骤：ResumeParse、JDAnalysis、Match、ResumeOptimize、ProjectChallenge、Report。
- 展示 `workflow_run_id`、每步耗时、执行模式和 fallback 原因。
- 说明 trace 用于复盘，不是页面临时猜测。

## 6. 查看历史记录

进入“历史记录”页，选择刚保存的分析记录。

演示点：

- 历史记录可复看 Markdown 报告。
- 已保存的 workflow trace 可以在详情页复盘。

## 7. 查看岗位库

进入“岗位库”页，打开刚才的岗位。

演示点：

- 岗位库保存原始 JD 和结构化 JD 分析。
- 当前不抓取外部招聘网站，只保存用户输入或分析产生的 JD。

## 8. 保存简历版本

进入“简历版本”页，填写版本标签，粘贴原始简历和定制后简历文本，可选关联目标岗位。

演示点：

- 简历版本保存用户确认的内容。
- 不自动编造经历、公司、项目、数据或技术栈。

## 9. 创建投递 tracker

进入“投递跟进”页，选择岗位，设置状态、下一步行动和可选简历版本。

演示点：

- tracker 只记录本地求职状态。
- 不做自动投递、招聘网站登录或验证码处理。

## 10. 打开 FastAPI docs

```powershell
.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

访问：

```text
http://127.0.0.1:8000/docs
```

演示点：

- 展示 `/resume/parse-file`、`/analyze/full`、`/records`、`/jobs` 等 API。
- 文件上传错误会返回统一格式：`detail` + `error_code`。
- API route 保持薄封装，核心逻辑在 service、agent、workflow、storage。
