# Git Workflow

> 用途：记录 JobAgent 的版本管理方式，方便后续开发、复盘、GitHub 展示和面试说明。

## 1. 当前策略

第一阶段采用简单分支策略：

- `main`：稳定可运行版本。
- 功能开发：后续可以从 `main` 切出 `feature/<name>`。
- 小步提交：每完成一个清晰目标就提交一次。

当前项目还处于早期，一个人开发时不需要复杂 Git Flow。

## 2. 推荐提交粒度

每次提交尽量对应一个明确目标：

- 初始化文档层。
- 初始化 Mock MVP。
- 新增 JDAnalysisAgent。
- 接入 FastAPI。
- 修复某个 bug。
- 补充测试。

不要把大量不相关修改塞进同一个提交。

## 3. 提交信息格式

推荐使用简洁的 conventional commit 风格：

```text
chore: initialize project docs
feat: add mock analysis pipeline
test: cover mock pipeline
docs: add development review guide
fix: handle empty resume input
```

常用类型：

- `feat`：新增功能。
- `fix`：修复问题。
- `docs`：文档更新。
- `test`：测试相关。
- `chore`：项目配置、依赖、仓库管理。
- `refactor`：不改变行为的重构。

## 4. 每轮开发后的 Git 自查

提交前检查：

```bash
git status --short
pytest
```

确认：

- `.venv/` 没有被提交。
- `__pycache__/` 没有被提交。
- Streamlit 日志没有被提交。
- 测试通过。
- README 或 docs 记录了重要变化。

## 5. GitHub 使用建议

GitHub 仓库建议命名：

```text
jobagent
```

仓库描述可以写：

```text
A multi-agent job search workspace for resume-JD matching, resume optimization, and interview preparation.
```

建议先创建公开仓库，方便后续作为简历项目展示。如果暂时不想公开，也可以先创建私有仓库，等 README、截图和 Demo 稳定后再公开。

## 6. 面试时可以怎么讲

这个项目的 Git 管理思路是：

```text
我先把文档层、AI 辅助开发规则和 Mock MVP 分阶段提交。
每个提交对应一个清晰开发目标，并用测试保护主流程。
后续接入 LLM、FastAPI、SQLite、LangGraph 时，会继续按小步提交推进，避免一次性大改导致难以回滚。
```
