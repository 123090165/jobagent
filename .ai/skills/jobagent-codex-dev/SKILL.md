---
name: jobagent-codex-dev
description: 约束 Codex 在 jobagent 项目中的开发流程。用于后续 Codex 执行 jobagent 开发任务时，确保每轮开发小步、精准、可测试、可 review，并按固定极简格式交付。
---

# jobagent-codex-dev

约束 Codex 在 jobagent 项目中的开发流程，确保每轮开发小步、精准、可测试、可 review。

## 角色分工

网页端 ChatGPT：
- 负责需求澄清
- 负责功能取舍
- 负责架构方案
- 负责给 Codex 精准任务 prompt
- 负责 GitHub diff review

Codex：
- 负责读代码
- 负责按 prompt 改代码
- 负责跑指定测试
- 负责修复测试失败
- 负责 commit / push
- 负责极简交付汇报

## 每轮开发原则

- 一轮只做一个小功能。
- 不主动扩展范围。
- 不主动重构无关模块。
- 不主动加 UI。
- 不主动加 LLM。
- 不主动加新依赖。
- 不主动改数据库大结构。
- 不主动做未来规划。
- 如果发现 prompt 不清楚，优先做最小合理实现，并在 notes 中说明假设。
- 所有行为必须可测试。

## Git 工作流

后续默认流程：

1. 从最新 main 新建功能分支。
2. 分支命名使用 `codex/<feature-name>`。
3. 不直接改 main。
4. 不 force push。
5. 不自行 merge。
6. 不自行 tag。
7. 完成后 push 当前功能分支。
8. merge / tag 由用户确认后再执行。

如果任务 prompt 明确要求先合并旧分支，则按 prompt 执行；否则不要自行 merge。

## 测试规则

- 只运行 prompt 指定的测试。
- 如果相关测试失败，先修到通过。
- 如果发现必须跑额外测试，可以补跑，但最终汇报中只简要列出。
- 不要为了测试通过删除测试。
- 不要跳过失败测试。
- 不要把“未运行测试”说成“通过”。

## 最终输出格式

每轮完成后只输出下面 6 项，不要长篇总结：

```text
branch:
commit:
changed files:
tests:
status:
notes:
```

每项含义：

- branch: 当前分支名
- commit: 最新 commit hash
- changed files: 本轮修改文件列表
- tests: 实际运行的测试命令和结果
- status: pushed / not pushed / blocked
- notes: 1-3 句说明关键行为、假设或阻塞

明确禁止输出：

- 长篇架构解释。
- 长篇复盘。
- 未来路线规划。
- 大段代码 diff。
- 与本轮无关的建议。

## 默认禁止事项

- 不做 Streamlit UI，除非 prompt 明确要求。
- 不做 AI Interview，除非 prompt 明确要求。
- 不做 RAG，除非 prompt 明确要求。
- 不做 GenericHtmlParser，除非 prompt 明确要求。
- 不做新爬虫，除非 prompt 明确要求。
- 不做自动投递。
- 不做邮件/日历提醒。
- 不做多用户系统。
- 不引入 Playwright / Selenium。
- 不引入大型依赖。
- 不做数据库大改。
- 不做无关 README 大改。
- 不重写历史。
- 不 force push。

## 任务执行模板

收到任务后：

1. 读取 prompt 中指定文件。
2. 确认当前分支。
3. 只修改允许范围内的文件。
4. 实现最小功能。
5. 增加或更新必要测试。
6. 运行指定测试。
7. 修复失败。
8. `git diff --stat` 自检。
9. commit。
10. push。
11. 按固定 6 项格式汇报。

## jobagent 当前项目边界

jobagent 当前优先目标不是功能越多越好，而是把已有求职闭环做扎实：

```text
岗位来源
-> 搜索结果
-> JobImportCandidate
-> ApplicationRecord
-> 单岗位分析
-> 简历优化 / 项目追问 / 报告
-> tracker 复盘
```

后续开发应优先补闭环断点，而不是提前扩展 AI Interview、RAG、多站点爬虫等大功能。

## 极简示例

```text
branch: codex/candidate-to-tracker
commit: cd0724fd
changed files:
- app/services/job_import_candidate_service.py
- app/api/routes_job_import_candidates.py
- tests/test_routes_job_import_candidates.py
tests:
- .venv\Scripts\python.exe -m pytest tests\test_routes_job_import_candidates.py -> 12 passed
status: pushed
notes: Duplicate candidate import returns the existing application and keeps the original status/notes.
```
