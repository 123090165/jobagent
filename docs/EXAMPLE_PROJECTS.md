# Example Projects Analysis

> 用途：整理竞品和参考项目类型，反推 JobAgent 的需求边界和功能优先级。

## 1. Resume-JD Matching

典型功能：

- 上传简历。
- 输入 JD。
- 生成匹配建议。
- 输出简历优化方向。

JobAgent 吸收：

- 简历和 JD 双输入。
- 结构化匹配报告。
- 简历优化建议。

JobAgent 扩展：

- 增加项目追问。
- 后续增加岗位库、投递记录和面试准备。

## 2. LangGraph Job Search Assistant

典型功能：

- 简历解析。
- 岗位搜索。
- 推荐报告。
- 多步骤 Agent workflow。

JobAgent 吸收：

- 多 Agent 工作流。
- 结构化状态传递。
- Pydantic 输出模型。

JobAgent 取舍：

- v0.1 不接 LangGraph。
- v0.1 不依赖实时岗位搜索。
- 等 mock pipeline 稳定后再迁移。

## 3. Resume Screener / RAG 系统

典型功能：

- 使用向量数据库匹配简历和岗位。
- 检索历史岗位。
- 统计技能关键词。

JobAgent 吸收：

- 岗位 JD 入库。
- 历史岗位检索。
- 技能趋势分析。

JobAgent 取舍：

- v0.1 不接向量库。
- 先保存原始文本和结构化结果，为后续 RAG 做准备。

## 4. Auto Apply Agent

典型功能：

- 自动搜索岗位。
- 自动填表。
- 自动投递。
- 浏览器自动化。

JobAgent 吸收：

- 求职流程阶段划分。
- 后期可考虑半自动投递助手。

JobAgent 暂不做：

- 自动登录。
- 自动提交申请。
- 验证码处理。
- 复杂反爬。

## 5. CareerOps

典型功能：

- 用户画像。
- 求职 tracker。
- 简历版本管理。
- 长期行动计划。

JobAgent 吸收：

- 求职操作系统思路。
- profile 和 tracker 的长期管理能力。
- AI coding friendly 的项目组织。

JobAgent 取舍：

- v0.1 不做重配置。
- 优先做可演示的 Streamlit MVP。

## 6. 结论

JobAgent 的第一阶段不追求功能最多，而是追求：

- 端到端跑通。
- 输出结构化。
- 建议可执行。
- 不编造简历事实。
- 架构能自然扩展到岗位库、LLM、LangGraph、RAG、MCP 和 tracker。
