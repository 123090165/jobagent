# JobAgent Demo Guide

> 用途：把 JobAgent 演示讲成一个完整工程故事，而不是只展示页面按钮。适合 GitHub 展示、面试讲解、毕业设计答辩和阶段复盘。

## 1. 当前阶段目标

这一阶段的目标是增强 README 和 Demo 展示材料，让外部读者能快速理解：

- JobAgent 解决什么问题。
- 当前已经能跑哪些功能。
- 系统如何分层。
- 为什么先做本地求职准备工作台，而不是自动投递工具。
- 如何通过测试证明核心流程可用。

## 2. 演示前准备

确认依赖已经安装：

```powershell
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

运行测试：

```powershell
.venv\Scripts\python.exe -m pytest
```

启动 Streamlit：

```powershell
.venv\Scripts\python.exe -m streamlit run frontend/streamlit_app.py
```

可选启动 FastAPI：

```powershell
.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

样例数据：

- `data/samples/sample_resume.md`
- `data/jd_examples/sample_jd.md`

## 3. 推荐演示路径

### Step 1：生成报告

操作：

- 打开 Streamlit 的“生成报告”页面。
- 粘贴样例简历和样例 JD。
- 保持 LLM 关闭，先展示 mock pipeline 的稳定闭环。
- 勾选“保存本次分析”。
- 点击生成报告。

讲解重点：

- 第一版先追求结构化闭环，不追求模型效果。
- mock 输出也走同一套 Pydantic schema，后续替换 LLM 不影响下游。
- 报告来自结构化对象，而不是直接在页面里拼一段文本。

### Step 2：查看历史记录

操作：

- 切到“历史记录”页面。
- 查看刚保存的分析记录。
- 展开 Markdown 报告和结构化详情。

讲解重点：

- 保存原始文本和结构化结果，方便复盘。
- 列表页只展示摘要，详情页再展示完整内容。
- 测试使用临时数据库，不污染真实本地数据。

### Step 3：查看岗位库

操作：

- 切到“岗位库”页面。
- 搜索样例 JD 的关键词。
- 查看岗位原始 JD、结构化分析和分析次数。

讲解重点：

- 岗位库来自用户保存过的 JD，不做外部招聘站抓取。
- 当前去重规则是 `raw_jd` 完全一致则复用岗位记录。
- 语义去重、标签和 URL 提取属于后续阶段。

### Step 4：创建投递跟进

操作：

- 切到“投递跟进”页面。
- 从岗位库选择目标岗位。
- 设置状态为 `interested` 或 `applied`。
- 填写备注、下一步行动和简历版本标签。

讲解重点：

- tracker 只记录本地求职状态，不执行自动投递。
- 状态是明确枚举，而不是任意字符串。
- 当前一个岗位对应一条 tracker 记录，重复保存同一岗位会更新原记录。

### Step 5：展示 FastAPI

操作：

- 打开 `http://127.0.0.1:8000/docs`。
- 展示 `/analyze/full`、`/jobs`、`/applications` 等接口。

讲解重点：

- Streamlit 是 Demo 层，FastAPI 是可复用后端边界。
- route 保持很薄，核心逻辑在 service。
- 后续迁移到 Web 前端时，service 和 API 可以继续复用。

### Step 6：展示测试

操作：

- 在终端运行 `pytest`。
- 说明当前覆盖的测试模块。

讲解重点：

- 不是只靠手动点页面证明功能可用。
- API、存储、LLM fallback、tracker 都有最小测试保护。
- deprecation warning 来自依赖链，不影响当前功能正确性。

## 4. 面试讲述版

可以这样讲：

```text
我把 JobAgent 定位为求职准备工作台，而不是自动投递工具。
第一阶段先用 mock pipeline 跑通简历、JD、匹配、优化、追问和报告生成。
这样做的好处是先稳定 schema 和数据流，再逐步替换真实 LLM。

后续我接入了 FastAPI 和 SQLite，把一次性页面工具升级成可复盘的本地系统。
用户可以保存分析记录、沉淀岗位库，并用 tracker 管理投递进展。
整个过程中我保持边界清晰：不登录招聘网站，不处理验证码，不做自动投递，也不允许简历优化编造经历。
```

## 5. 当前开发重点

- README 要能让别人快速跑起来。
- 架构图要能说明 UI、API、service、agent、storage 的边界。
- Demo 路径要展示完整闭环，而不是只展示一个页面。
- 面试介绍要讲清取舍，不只罗列技术名词。
- 测试结果要作为演示证据。

## 6. 难点和取舍

- README 不能只写命令，还要解释项目边界和工程价值。
- Demo 不能依赖真实隐私数据，应使用样例简历和样例 JD。
- 当前 LLM 只替换 JDAnalysisAgent，是为了降低不稳定输出对主链路的影响。
- tracker 不做自动投递，是为了规避平台风险和合规问题。
- SQLite 足够支撑本地 MVP，多用户和权限系统放到后续阶段。

## 7. 关键知识点

- 技术叙事：把需求、边界、架构、验证串成故事。
- 分层架构：UI、API、service、agent、storage 分工清晰。
- Schema-first：先稳定结构化数据，再替换模型能力。
- Fallback：LLM 失败时回退 mock，保证可用性。
- Repository pattern：集中管理 SQLite 访问。
- 状态机：用枚举管理投递状态。

## 8. 面试官可能追问

- 为什么不直接做自动投递？
- 为什么第一版先 mock，而不是直接接 LLM？
- LLM 输出不符合 schema 怎么处理？
- 为什么 tracker 依赖岗位库？
- 岗位去重为什么先用完全匹配？
- 后续如果做多用户，需要改哪些表结构？
- 如何证明系统不是 prompt demo？
- 如果要迁移到 LangGraph，当前哪些模块可以复用？

## 9. 验收清单

- README 包含架构图。
- README 包含运行说明。
- README 包含阶段路线。
- README 包含面试讲述版项目介绍。
- Demo Guide 包含演示路径和讲解重点。
- `pytest` 通过。
- 不新增自动投递、招聘网站登录、验证码处理、复杂爬虫或多用户权限能力。
