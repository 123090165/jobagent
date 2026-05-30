# Agent Boundaries

> 用途：记录 JobAgent 当前 Agent 层的职责边界。它让 workflow 调用稳定的 Agent 接口，而不是直接调用底层 mock 函数，为后续替换 LLM Agent 或迁移 LangGraph 做准备。

## 1. 当前目标

当前阶段补齐 mock Agent 外壳：

```text
ResumeParseAgent
JDAnalysisAgent
MatchAgent
ResumeOptimizeAgent
ProjectChallengeAgent
ReportAgent
```

workflow 只关心这些 Agent 的结构化输入输出，不关心底层是 mock 规则还是 LLM。

## 2. 代码位置

```text
app/agents/
  resume_parse_agent.py
  jd_analysis_agent.py
  match_agent.py
  resume_optimize_agent.py
  project_challenge_agent.py
  report_agent.py
```

## 3. Agent 职责

### ResumeParseAgent

入口：

```python
parse_resume(resume_text: str) -> ResumeProfile
```

职责：

- 清理简历输入。
- 返回 `ResumeProfile`。
- 空输入直接报错。

### JDAnalysisAgent

入口：

```python
analyze_jd(jd_text: str, use_llm: bool = False) -> JobAnalysis
```

职责：

- 分析 JD。
- 可选调用 LLM。
- LLM 失败时回退 mock。
- 不把加分项误判成必备项。

### MatchAgent

入口：

```python
analyze_match(resume_profile: ResumeProfile, job_analysis: JobAnalysis) -> MatchReport
```

职责：

- 比较简历和 JD。
- 输出匹配分、证据、风险和建议。

### ResumeOptimizeAgent

入口：

```python
optimize_resume(...) -> ResumeOptimizationResult
```

职责：

- 给出简历优化建议。
- 不编造经历、公司、项目、数据或技术栈。
- 信息不足时提示用户补充。

### ProjectChallengeAgent

入口：

```python
generate_project_challenges(...) -> ProjectChallengeReport
```

职责：

- 生成项目面试追问。
- 覆盖基础问题、技术细节、架构和取舍。

### ReportAgent

入口：

```python
generate_report(...) -> str
```

职责：

- 把结构化结果聚合成 Markdown 报告。
- 不重新做业务分析。

## 4. 当前边界

- Agent 外壳已经独立。
- 底层 mock 启发式暂时复用 `app/services/mock_pipeline.py` 中的函数。
- workflow 不再直接调用 mock service 函数。
- API 和 Streamlit 入口不变。
- 暂不把所有实现迁移进 agent 文件，避免一次性大改。

## 5. 为什么这样做

如果 workflow 直接调用底层 mock 函数，后续迁移 LangGraph 时每个 node 的边界会不清楚。

现在先让 workflow 调 Agent：

- 后续替换单个 Agent 更容易。
- 每个 Agent 的输入输出可以独立测试。
- workflow 更像编排层，而不是业务逻辑堆叠。
- LangGraph node 可以直接映射到 Agent 调用。

## 6. 测试重点

当前测试覆盖：

- 每个 mock Agent 返回共享 Pydantic schema。
- ResumeParseAgent 拒绝空简历。
- workflow 仍然按 6 个 Agent 步骤执行。
- `run_mock_pipeline` 外部契约不变。

## 7. 面试官可能追问

- Agent 和 service 的边界是什么？
- 为什么现在只是 mock Agent 外壳，不直接全接 LLM？
- 为什么 ReportAgent 不重新分析业务？
- ResumeOptimizeAgent 如何防止编造经历？
- 后续迁移 LangGraph 时，每个 Agent 如何对应 node？

## 8. 下一步

- 把更多 mock 实现逐步从 `mock_pipeline.py` 搬到对应 Agent。
- 给 Agent 增加错误和 fallback 元信息。
- 让 workflow step trace 记录每个 Agent 的 fallback 来源。
- 再考虑将 workflow 映射成 LangGraph。
