# Batch Job Brief

## 1. 功能目标

`Batch Job Brief MVP` 把当前的“单岗位简历 + JD 分析”升级为“批量岗位推荐 brief”：

- 输入一份简历文本
- 输入一个搜索 query
- 通过 `SearchProvider` 获取多个岗位
- 对每个岗位复用现有 workflow 生成 `match_report`
- 按 `fit_score` 排序
- 输出推荐岗位、理由、风险点和投递策略

第一版重点是把链路跑通，不把 mock 搜索包装成真实联网抓取系统。

## 2. 为什么先用 MockSearchProvider

第一版先使用 `MockSearchProvider`，原因很直接：

- 先验证 `SearchResultItem -> workflow -> MatchReport -> JobBriefReport` 这条结构化数据流
- 不引入真实招聘网站登录、Cookie、验证码、反爬等复杂边界
- 可以稳定测试排序、风险点汇总、`scoring_quality` 解释和 Streamlit 展示
- 为后续 `SearchResult -> JobImportCandidate` 和 JD 获取质量升级预留边界

## 3. 请求示例

API:

```json
{
  "resume_text": "Python FastAPI SQL LLM ...",
  "query": "python backend llm jobs",
  "provider": "mock",
  "limit": 5,
  "use_llm_jd": false
}
```

Endpoint:

```text
POST /brief/from-search
```

## 4. 返回字段说明

`JobBriefReport`:

- `query`
- `provider`
- `total_jobs`
- `recommended_jobs`
- `top_skills`
- `market_summary`
- `application_strategy`
- `scoring_quality_summary`

`JobRecommendationItem`:

- `rank`
- `job`
- `match_report`
- `fit_score`
- `advice`
- `scoring_quality`
- `fit_reasons`
- `risk_points`

说明：

- `fit_score` 直接来自 `MatchReport.overall_score`
- `fit_reasons` 直接来自 `MatchReport.matched_points`
- `risk_points` 来自 `MatchReport.risks + MatchReport.missing_points`
- `advice` 优先复用 `MatchReport.apply_recommendation`

## 5. scoring_quality 解释

`scoring_quality` 不是岗位质量，而是本次评分输入材料的完整度：

- `full_jd`
  - `job.is_full_jd = true`
  - 说明当前岗位文本更接近完整 JD
- `partial_jd`
  - 有 `job.jd_text`
  - 但 `job.is_full_jd = false`
  - 说明拿到了更丰富的 JD-like 文本，但还不能当作完整 JD
- `snippet_only`
  - 没有 `job.jd_text`
  - 只依赖 `snippet`
  - 说明这次匹配分可信度更低，应先补完整 JD

## 6. 与 Slate 的区别

当前 `Batch Job Brief MVP` 明确不做这些事：

- 不登录招聘网站
- 不读取 Cookie
- 不处理验证码
- 不做自动投递
- 不把 mock 搜索包装成真实搜索

它只是一个本地推荐和排序工具，不是招聘网站自动化系统。

## 7. 后续计划

后续更合理的扩展顺序：

- `SearchResult -> JobImportCandidate`
- 真实 JD 获取质量增强
- 保存 Brief 到历史记录
- 把高优先级岗位加入 tracker

## 8. Resume -> Query Generator

Batch Job Brief now supports a small rule-based preparation step before search:

- start from `resume_text`
- generate a few English search queries
- pick one query manually
- run `provider="mock"` to produce the brief

This keeps the current MVP safe and explicit:

- no real networking in tests
- no hidden public scraping
- no automatic import into storage

Later rounds can connect the same query generation step to public no-login job sources.
