# Python Backend Skill

> 用途：约束 JobAgent 的 Python 后端实现方式，保持目录清晰、类型清晰、职责清晰。

## 技术栈

- Python 3.11+
- FastAPI
- Pydantic
- SQLite first, PostgreSQL later
- pytest

## 目录约定

- `app/api/`：API routes，只处理请求和响应。
- `app/schemas/`：Pydantic models。
- `app/services/`：业务逻辑和流程编排。
- `app/agents/`：Agent 节点、prompt 和 LLM 调用。
- `app/tools/`：可复用工具函数。
- `app/storage/`：数据库连接、模型和仓储。
- `tests/`：测试。

## 编码规则

1. API route 不写复杂业务逻辑。
2. services 负责业务编排。
3. agents 负责 LLM / Agent 逻辑。
4. tools 负责可复用工具。
5. schemas 定义所有核心输入输出。
6. 函数必须有类型标注。
7. 对外接口要有清晰错误处理。
8. 新功能尽量配一个最小测试。
9. 不引入重型依赖，除非确实必要。
10. mock 实现也要遵守真实 schema。

## 推荐实现顺序

1. 定义 schema。
2. 写 service 或 mock pipeline。
3. 写报告生成逻辑。
4. 写 UI 或 API 调用入口。
5. 写最小测试。
6. 再考虑真实 LLM、数据库和 LangGraph。
