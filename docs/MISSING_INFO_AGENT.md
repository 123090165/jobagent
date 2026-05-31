# MissingInfoQuestionAgent

## 功能用途

`MissingInfoQuestionAgent` 用来识别“当前简历还缺哪些可澄清的信息”，帮助用户补充真实内容，而不是直接改写或编造简历。

当前它只接入在 LangGraph prototype 中，不影响默认 Python workflow。

## 输入

- `ResumeProfile`
- `JobAnalysis`
- `MatchReport`

## 输出

- `MissingInfoReport`
  - `questions`
  - `summary`

每个问题都带：

- `question`
- `reason`
- `related_skill`
- `priority`

## 当前检测规则

当前版本是 mock / rule-based，不接 LLM。

主要检测：

1. JD required skills 未在简历技能栏中出现
2. JD required skills 未在项目证据中体现
3. 项目描述过短
4. 缺少量化指标
5. 缺少部署 / 测试 / 数据库 / API 等工程证据

## 在 LangGraph 中的位置

当前节点位置：

```text
ResumeParse
-> JDAnalysis
-> Match
-> MissingInfoCheck
-> route_by_match_score
```

也就是说：

- 先得到 `MatchReport`
- 再检查“还缺什么信息”
- 再走 `route_by_match_score`

因此无论是标准路径还是低匹配路径，`missing_info_report` 都会保留在 LangGraph state 中。

## 当前边界

这个 agent 只做缺失信息检测，不做：

- 编造经历
- 编造项目
- 编造公司
- 编造量化数据
- 编造技能使用场景

它只负责告诉用户：

- 哪些信息没写清楚
- 为什么这些信息重要
- 建议优先补什么

## Trace

LangGraph prototype 里会新增一个 trace step：

- `MissingInfoAgent`

它当前固定是：

- `mode = mock`

## 当前限制

- 只接在 LangGraph prototype 中
- 默认 Python workflow 暂时不接入
- 只做规则检测，不做 LLM 追问扩展
- 结果目前只保存在 LangGraph state 和 trace 中
- 不进入 `FinalReport`

## 后续可扩展方向

后续可以考虑：

1. 按岗位类型细化缺失信息模板
2. 按 `priority` 做 UI 排序展示
3. 把问题映射到简历版本修改建议
4. 未来在明确边界下加入可选 LLM clarification mode
