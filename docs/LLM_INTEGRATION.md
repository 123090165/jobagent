# LLM Integration

> 用途：记录 JobAgent 第二轮开发的 LLM 接入方式。当前只允许 JDAnalysisAgent 使用真实 LLM，其他 Agent 仍然保持 mock。

## 1. 当前接入范围

当前只接入：

```text
JDAnalysisAgent
```

目标：

- 把 JD 文本解析为结构化 `JobAnalysis`。
- 使用 Pydantic 校验 LLM 输出。
- LLM 失败时自动回退到 mock JD 分析。

当前不做：

- 不替换 ResumeParseAgent。
- 不替换 MatchAgent。
- 不引入 LangGraph。
- 不引入数据库。
- 不要求 Streamlit 必须依赖 LLM 才能运行。

## 2. 配置方式

复制 `.env.example` 中的变量到当前 shell 环境。

PowerShell 示例：

```powershell
$env:JOBAGENT_LLM_API_KEY="your-api-key"
$env:JOBAGENT_LLM_BASE_URL="https://api.openai.com/v1"
$env:JOBAGENT_LLM_MODEL="gpt-4o-mini"
$env:JOBAGENT_LLM_TIMEOUT="60"
$env:JOBAGENT_LLM_TEMPERATURE="0.1"
```

然后启动：

```powershell
.venv\Scripts\python.exe -m streamlit run frontend/streamlit_app.py
```

在页面侧边栏勾选：

```text
启用 LLM JD 分析
```

## 3. 回退策略

以下情况会自动回退到 mock：

- 没有配置 `JOBAGENT_LLM_API_KEY`。
- LLM 请求失败。
- LLM 返回内容不是 JSON。
- JSON 无法通过 `JobAnalysis` schema 校验。

回退的意义：

- 没有 API key 也能继续开发。
- LLM 不稳定时不影响 MVP 主流程。
- 后续可以逐个替换 Agent，而不是一次性重写系统。

## 4. 开发难点

这一轮的核心难点不是“调用模型”，而是：

- LLM 输出必须可被程序消费。
- prompt 不能鼓励模型编造 JD 中没有的信息。
- 必备技能和加分技能不能混淆。
- 失败时必须有可用 fallback。
- 现有 Streamlit 页面和测试不能被破坏。

## 5. 面试官可能追问

- 为什么只先替换 JDAnalysisAgent？
- LLM 输出不是合法 JSON 怎么办？
- Pydantic 校验失败后怎么处理？
- 为什么不用 SDK，而先用标准库封装 OpenAI-compatible API？
- 如何避免模型把 JD 中没有的内容补出来？
- 为什么不一次性把所有 Agent 都接 LLM？
