# JobAgent

JobAgent 是一个面向求职者的多智能体求职工作台。当前版本是 v0.1 Mock MVP，目标是先跑通：

```text
简历文本 + JD 文本 -> 匹配报告 + 简历优化建议 + 项目追问 + Markdown 报告
```

## 当前状态

已完成第一轮最小代码骨架：

- Streamlit 页面。
- Pydantic schema。
- mock 简历解析。
- mock JD 分析。
- mock 匹配报告。
- mock 简历优化建议。
- mock 项目追问。
- Markdown 报告生成。
- 最小测试。

当前不做：

- 真实 LLM。
- 数据库。
- LangGraph。
- 自动投递。
- 招聘网站登录和验证码处理。

## 安装

```bash
pip install -r requirements.txt
```

## 运行 Streamlit Demo

```bash
streamlit run frontend/streamlit_app.py
```

## 运行测试

```bash
pytest
```

## 目录结构

```text
app/
  main.py
  schemas/
    resume.py
    job.py
    match.py
    report.py
  services/
    mock_pipeline.py
    report_service.py
frontend/
  streamlit_app.py
tests/
  test_mock_pipeline.py
data/
  samples/
  jd_examples/
docs/
.ai/
```

## 第一轮开发重点

第一轮不是为了让分析结果特别智能，而是为了稳定工程骨架：

1. 输入输出先结构化。
2. 业务逻辑从 UI 中拆出来。
3. mock 输出和未来 LLM 输出使用同一套 schema。
4. 报告由结构化对象生成，不直接写死在页面里。
5. 用测试保护核心流程。

## 后续路线

1. 替换 JDAnalysisAgent 为真实 LLM 输出。
2. 增加 FastAPI 后端。
3. 接入 SQLite 保存 JD、简历版本和报告。
4. 使用 LangGraph 编排多 Agent。
5. 扩展岗位数据库、RAG、MCP 和 tracker。
