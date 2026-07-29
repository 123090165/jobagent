# Search Retrieval Quality V2 实施计划

## 1. 文档目的

本计划用于提升岗位搜索的召回质量、约束正确性和最终排序可信度。它不是一次 Provider 扩容，也不是工作流框架迁移；重点是重新安排查询预算和候选漏斗，让昂贵分析发生在更值得分析的候选上，并让完整 JD 证据真正决定最终分数。

本计划以当前代码和测试为基线，主要涉及：

- `app/services/job_search_intent.py`
- `app/services/job_search_planner.py`
- `app/services/job_search_execution/preview.py`
- `app/services/job_search_execution/provider_search.py`
- `app/services/job_search_providers/`
- `app/services/job_candidate_filter.py`
- `app/services/job_candidate_constraints.py`
- `app/services/job_candidate_scoring.py`
- `app/services/job_candidate_reranker.py`
- `app/services/job_search_execution/candidate_analysis.py`
- `app/services/job_search_execution/result_builder.py`
- `experiments/provider_recall_calibration.py`

## 2. 对当前实现的判断

### 2.1 纠偏后的实际实施进度（2026-07-18）

当前已直接解决以下核心痛点：

1. **Query 不再按列表取前三个**：新增 typed `PlannedQuery`，记录 `user / broad / role_domain / evidence / tool / fallback`、priority 和 rationale；执行器按类型配额确定最多 6 个 Query，并执行全部入选 Query。内部只保存 `planned_queries`，字符串 `queries` 是只读兼容视图，API 继续输出 `provider_queries`。
2. **候选池不再只有 `2 * max_results`**：召回池调整为 `30–100`，请求 10 个结果时上限为 60；候选超过 30 时先进行 deterministic pre-rank，只把 Top 30 发送给 LLM，再分析最终入选候选，避免扩大召回后形成超大 LLM payload。
3. **明确硬约束不再只是扣分**：confirmed Search Mission 的地点、work arrangement、employment type、excluded roles 和明确的 internship/seniority 条件进入 deterministic hard filter；只有出现明确冲突证据时 reject，缺字段仍按 unknown/accepted 进入后续排序。拒绝码和 evidence 写入 Candidate Filter trace。
4. **Provider 不再共享同一执行参数**：执行器把 Multi-source 展开为 source-specific tasks。CUHKSZ 使用短标题词，LinkedIn 使用完整 query 并覆盖多个地点，RemoteOK 每轮只执行一个 feed 本地过滤任务，Browser Helper 只消费一次捕获 payload。
5. **来源与地点不再按单一嵌套循环抢占**：各来源任务 round-robin 执行；Search Engine 的第一条 query 先覆盖所有有效地点，再使用剩余任务补充 query 类型。
6. **跨来源转载不再重复占位**：对规范化 title/company/location 完全一致、但来源不同的候选进行保守聚类，并保留 JD 证据更完整的代表。`cross_source_repost` 的 `Duplicate@5` 已从 1 降为 0。
7. **JD Analysis 已进入最终评分**：Filter scorecard 仅作为 `recall_score`；匹配阶段使用结构化 JD evidence 重新生成 `final_match_score`，Job Card 的 `match_score` 等于最终分，不再原样复用召回预估分。
8. **不同来源现在有界并发执行**：同一来源内的多个 query 仍保持顺序，避免并发改写 Provider 缓存或限流状态；不同来源最多 4 路并发，完成后按原 task 顺序合并，因此 partial failure、去重、排序和 trace 仍然稳定。
9. **Hard Filter 已补成三态决策**：明确冲突为 `rejected`，明确满足为 `accepted`，约束字段缺失为 `unknown`；unknown 候选继续进入低成本排序，trace 单独记录缺失字段，不再与明确满足约束混为一类。
10. **最终排序增加有限多样性调整**：只在 5 分窗口内优先尚未出现的公司和来源，不允许明显低分岗位越过高分岗位；trace 记录发生调整的候选数量。

主执行路径中的 `queries[:3]`、召回后提前占满即停止和直接复用 recall scorecard 的分支已经移除。`MultiSourceJobSearchProvider.search_jobs()` 的独立顺序聚合接口仍由 provider 校准实验直接调用，因此保留；搜索运行主路径已经展开为 provider-specific tasks，不会走该旧聚合入口。

离线 corpus 中原有的 internship seniority 和 Remote/onsite 两个 strict violation 已从 Top 5 中剔除，当前 8-case baseline 的 `ConstraintViolation@5` 均为 0。Search Plan 现在会保留 location、work arrangement、employment type、seniority 和 excluded role 的结构化约束；旧 run 的自由文本仅通过保守兼容规则解析。

当前没有真实用户行为数据。因此本阶段明确不建设 save/dismiss/apply 驱动的在线自适应策略，也不为它预先增加表、权重服务或学习框架。质量判断以人工设计的代表性 fixtures、冻结 baseline、deterministic replay 和运行 trace 为主；真实反馈闭环只在未来积累足够样本后重新立项。

对照文件分别保留为 `legacy_v1.json` 和 `v2_iteration1.json`；默认 replay 只更新当前 V2 文件，不会再覆盖冻结的 legacy 基线。

外部分析指出的主矛盾成立，下面保留的是改造开始前的基线问题，用于解释本计划的设计取舍；它们不再代表当前代码状态。

初始基线的关键事实如下：

| 初始问题 | 改造前代码行为 | 影响 |
| --- | --- | --- |
| Query Plan 无类型 | `JobSearchPlan.queries` 是 `list[str]` | 无法按查询类型、来源和价值分配预算 |
| 执行查询固定截断 | `MAX_PROVIDER_QUERIES_PER_RUN = 3` | domain/evidence query 经常只进入 trace，不进入召回 |
| 输入查询前插 | 用户 query 和 focused query 位于 intent queries 之前 | 列表顺序替代了显式选择策略 |
| 所有来源共享调用参数 | Multi-source 将相同 query/location/limit 顺序传给内部来源 | 来源特性没有在 Planner 与执行器之间表达 |
| 候选池较窄 | `candidate_pool_cap = max_results * 2`，单次 limit 最大为 5 | 无法为去重、硬约束和质量筛选保留余量 |
| 达量即停止 | query/location 双循环在 pool 满后 break | 靠前 query、location 和 source 获得结构性优势 |
| 约束主要是扣分 | mission constraints 进入 `must_have_signals`，excluded roles 进入 `avoid_signals` | 明确违反底线的岗位仍可能进入 Top N |
| 去重以 canonical URL 为主 | 无 URL 时才退化为 title/company/location | 跨平台转载和标题轻微改写无法识别 |
| JD 未重算最终分 | `_match_candidates()` 优先复用 Filter scorecard | 更完整证据不能纠正早期预估 |
| 已有观测但无真实反馈样本 | trace、source stats 和校准实验已存在；用户行为数据尚未形成 | 当前只能做离线评估，不能训练或调节在线策略 |

外部建议中有三点不宜直接照搬：

1. 不应先把候选池直接扩大到 100。没有预算、评估和分层 payload 控制时，只会放大延迟与成本。应先建立基线，再把默认召回池逐步提高到 `4–6 * max_results`，并设置绝对上限。
2. Hard Filter 不应只有 accept/reject。地点、届别、工作类型等字段经常缺失，需要 `accepted / rejected / unknown` 三态；只有存在明确证据时才能硬拒绝。
3. Near duplicate 不应直接删除。模糊匹配可能合并不同职级或不同地点的真实岗位，应先聚类，再从同一 cluster 中选择证据质量最好的代表，同时保留成员和判断依据。

## 3. 目标与非目标

### 3.1 目标

- 每个已执行查询都有类型、来源、地点、预算、优先级和选择理由。
- 每个选中来源至少获得合理的召回机会，不因循环顺序被提前饿死。
- 明确违反用户硬约束的候选不会出现在最终结果中。
- 召回分与最终匹配分分离；最终分必须使用 JD Analysis 产生的结构化证据。
- LLM 请求规模有上限，扩大候选池不会形成单次超大 JSON 排序请求。
- 当前通过离线标注和运行 trace 衡量搜索质量；真实用户反馈是未来补充证据。
- 保持当前 API、JobSearchRun 生命周期和六个顶层 trace step 兼容，采用渐进迁移。

### 3.2 非目标

- 不新增 Provider 作为本里程碑的主要工作。
- 不迁移到 LangGraph、LangChain 或通用 agent orchestrator。
- 不自动申请岗位，不绕过登录、验证码或站点限制。
- 不在第一阶段建立复杂在线学习或不可解释的黑盒 query optimizer。
- 不把缺少 JD、地点或发布日期自动视为不合格。

## 4. 目标流水线

~~~text
Confirmed Profile + Search Mission + 本次输入
  -> Intent extraction
  -> Typed logical query plan
  -> Provider-specific task translation
  -> Budgeted query/source scheduler
  -> Provider recall
  -> Exact dedupe + near-duplicate clustering
  -> Hard constraint decision (accept / reject / unknown)
  -> Cheap recall pre-rank
  -> JD enrichment and evidence extraction
  -> Final evidence-based scoring
  -> Diversity-aware result assembly
  -> Offline metrics and runtime trace
~~~

对于 `max_results = 10`，初始建议漏斗为：

~~~text
40–60 raw candidates
  -> 30–45 accepted/unknown candidates
  -> 20–30 pre-ranked candidates
  -> 12–20 JD-enriched candidates
  -> 10 final results
~~~

这些数字是预算默认值，不是产品承诺。最终值应由 Phase 0 的校准结果决定，并按 Provider 设置独立上限。

## 5. 核心设计

### 5.1 逻辑 Query 与可执行 Search Task 分离

不建议只在一个 `PlannedQuery` 中同时塞入多个 sources 和 locations，因为执行时仍需展开组合，配额和 trace 会变得含糊。采用两层模型：

~~~python
class LogicalQuery(BaseModel):
    query_id: str
    text: str
    query_type: Literal["broad", "role_domain", "evidence", "tool", "fallback"]
    priority: float
    rationale: str
    expected_recall: Literal["high", "medium", "low"]
    role_family: str | None = None
    domain_signals: list[str] = Field(default_factory=list)
    evidence_signals: list[str] = Field(default_factory=list)


class ProviderSearchTask(BaseModel):
    task_id: str
    logical_query_id: str
    source: str
    provider_query: str
    location: str | None
    requested_limit: int
    priority: float
    selection_reason: str
~~~

`LogicalQuery` 表达用户意图，`ProviderSearchTask` 才是执行单位。这样可以明确表达：同一个意图在 CUHKSZ 使用短中文职位词，在 LinkedIn/Serper 使用完整职位名和地点，而 RemoteOK 可能只执行一次 feed 获取并本地过滤。

迁移期间保留 `JobSearchPlan.queries`，将其作为 logical queries 的兼容投影；执行器逐步切换到 `search_tasks`，避免一次性改动 API 和所有测试。

### 5.2 Query Selector 与预算策略

第一版 Selector 必须 deterministic，LLM 只负责提供候选意图，不能直接决定无限制外部调用。

选择顺序：

1. 过滤空查询、低价值单词和高度相似查询。
2. 保证最小类型覆盖：至少一个 broad，以及在信号存在时至少一个 role-domain 或 evidence query。
3. 保证来源覆盖：每个 selected source 至少一个适配任务。
4. 对剩余预算按 query priority、source suitability 和 novelty 分配。
5. 达到预算时停止创建任务，而不是执行中由靠前结果抢满全局池。

第一版 priority 使用可解释规则：

- 用户本次明确输入有加权，但不无条件排第一。
- role + domain 的组合高于仅含 generic tool 的组合。
- evidence signal 只有在不把查询收窄到几乎无召回时才加分。
- 与已选 query token/alias 高度重叠时降低 novelty 分。
- 来源历史空结果率、重复率和详情覆盖率仅作为后续可选修正，不能在没有足够样本时使用。

### 5.3 Provider-specific Translation

每个 Provider 声明轻量 capability，而不是让 Planner 硬编码全部适配逻辑：

~~~python
class ProviderSearchCapabilities(BaseModel):
    query_style: Literal["short_title", "web_search", "feed_filter", "browser_ui"]
    supports_location: bool
    max_terms: int | None
    preferred_languages: list[str]
    supports_parallel_calls: bool
~~~

Provider translator 根据 capability 生成任务：

- CUHKSZ：短 title term、中文 alias、实习类别；地点通常不进入请求。
- LinkedIn/Serper：完整职位名、领域和地点；由 adapter 继续负责站点限定和 URL 解析。
- RemoteOK：每次 run 最多获取一次 feed，多个 logical query 转为本地匹配信号，避免重复下载。
- Browser Helper：只使用用户当前浏览上下文允许的任务，不假设后端可以替用户登录或翻页。

### 5.4 Query/source 配额与停止条件

调度器先生成完整的 bounded task list，再执行任务。全局 pool 满时，不立即取消尚未获得最低配额的来源。

建议的第一版规则：

- 全局召回目标：默认 `4 * max_results`，校准后可提高到 `6 * max_results`。
- 全局绝对 cap：初始为 60。
- 单来源最低任务数：1；单来源最大候选数和调用数可配置。
- 单任务 limit 由来源能力决定，不再全局固定为 5。
- 先执行 coverage round，再执行 fill round。
- fill round 只分配给仍能贡献新增候选的 query/source。
- 停止依据同时考虑预算耗尽、来源覆盖完成、新增率过低和 wall-clock deadline，而不是只看候选数量。

多来源并发放在配额调度稳定之后实施。并发必须有全局和 per-source 上限；`source_attempts` 等可变诊断数据需改为每个任务返回独立结果后再合并，避免线程共享写入。

### 5.5 Hard Constraint Filter

先将 Search Mission 中的自由文本约束规范化为受控类型：

~~~python
class SearchConstraint(BaseModel):
    kind: Literal[
        "location", "work_type", "seniority", "role_exclusion",
        "graduation_eligibility", "experience", "authorization", "expiry"
    ]
    operator: Literal["required", "excluded"]
    values: list[str]
    strict: bool
    source_text: str
~~~

约束解析可以由 LLM 辅助，但结构校验、alias 归一化和最终决定必须 deterministic。无法可靠归类的 mission 文本继续作为 ranking signal，不能静默升级为硬约束。

候选决策结构：

~~~python
class HardFilterDecision(BaseModel):
    status: Literal["accepted", "rejected", "unknown"]
    rejection_codes: list[str]
    evidence: list[str]
    unknown_fields: list[str]
~~~

规则原则：

- 只有候选文本或结构化 metadata 提供明确冲突证据时才 `rejected`。
- 缺少地点、届别、工作类型或发布日期时为 `unknown`，进入低置信候选池或优先 enrichment。
- `manager` 只在职位标题、任职资格或明确岗位级别中作为 seniority 证据；“report to manager”不能触发拒绝。
- “已过期”只有在来源给出可靠截止日期或状态时触发。
- 每个 rejected candidate 都必须在 trace 中按 code 聚合，并能在调试信息中追溯证据。

### 5.6 去重与岗位聚类

采用两层身份：

1. Exact identity：继续使用 canonical URL，并补充已知平台 job id。
2. Semantic cluster identity：规范化 company、role family、seniority、work type 和 location 后生成 cluster 候选。

Near-duplicate 判断应使用 token/alias 相似度和受控规则，不在第一版使用 LLM。聚类后保留：

- detail 最完整的候选作为 representative；
- 原始 source URLs 和 source providers；
- cluster confidence 与匹配依据；
- 可能属于不同岗位时不合并，只记录 suspected duplicate。

最终结果按 cluster 去重，而不是在 recall 阶段不可逆地删除所有相似项。

### 5.7 Recall score 与 Final score 分离

定义两个不同合同：

- `RecallScorecard`：基于 title、snippet、source quality、基础 role/location fit，用于决定哪些候选值得 enrichment。
- `FinalScorecard`：基于完整 JD 的 required/preferred skills、seniority、education、authorization、responsibilities、profile evidence 和 mission constraints，用于最终展示。

`FinalScorecard` 不能复制 recall score。JD Analysis 应先输出统一的 `CandidateEvidence`，Final Scorer 再消费该结构：

~~~text
RawJobCandidate
  -> CandidateEvidence
     - normalized role/seniority/work type/location
     - required and preferred skills
     - education/experience/authorization
     - responsibilities
     - supporting JD quotes
     - missing/uncertain fields
  -> FinalScorecard
~~~

为控制 LLM payload：

- pre-rank 对全部 hard-filter 后候选运行 deterministic score。
- 只对 Top 12–20 做 JD analysis。
- LLM evidence extraction 以单候选请求或小并发运行，失败只影响单条。
- Final scoring 优先采用“结构化证据 + deterministic rubric”；如增加 LLM rerank，只对小窗口运行，并保留 deterministic baseline。
- 不再把完整 Profile、完整 Plan 和 60–100 个 Raw Candidate 放进一次请求。

### 5.8 结果多样性

最终排序先按 `final_match_score`，再做有限的 diversity pass，避免 Top 10 被同一 cluster、同一公司或同一来源占满。多样性只能用于接近分数候选的重排，不能让明显低质量岗位越过高质量岗位。

## 6. 分阶段任务

### Phase 0：评估基线与安全护栏

目的：先知道改造是否真的提升质量，并为后续预算变化建立成本边界。

任务：

1. 扩展 `provider_recall_calibration.py`，记录 query type、source、raw/new/duplicate counts、详情覆盖率、耗时和错误。
2. 建立离线案例集：复用当前 multidomain fixtures，并增加硬约束、跨平台转载、JD 缺失、中文/英文 alias、多个地点等案例。
3. 为案例标注 relevant、constraint violation、duplicate cluster 和期望 Top K。
4. 记录当前 baseline：Precision@5、Recall@candidate-pool、nDCG@5、Top K constraint violation、详情覆盖、LLM 请求数、p50/p95 latency。
5. 在离线报告中记录 provider calls、候选数和耗时；运行时预算等 Scheduler 落地时在所属模块统一实现，不提前污染搜索主链。

验收：

- 离线评估可在无网络、无真实 LLM 下运行。
- live calibration 仍为显式命令，不进入默认测试。
- 当前实现有一份可重复生成的 baseline report。

### Phase 1：Typed Query Plan 与 Shadow Selector

目的：先引入新合同并观测选择结果，不立即改变生产召回行为。

任务：

1. 增加 `LogicalQuery`、`ProviderSearchTask` 和 provider capability 模型。
2. Intent 生成阶段保留 query type，不再只在拼接时丢失类别。
3. 实现 deterministic query selector、相似度去重和 coverage/fill 配额计算。
4. 实现各 Provider translator。
5. Preview 同时展示 logical queries、selected tasks、skipped queries 和原因。
6. 执行阶段继续使用旧 `queries[:3]`，新计划只写 trace，进行 shadow comparison。

验收：

- 相同输入产生稳定的 task plan。
- broad/domain/evidence/source coverage 有单元测试。
- 没有 API、数据库和真实 provider 行为变化。
- shadow trace 能解释每个 query 为什么执行或跳过。

### Phase 2：Hard Filter 与 Duplicate Clustering

目的：在扩大召回前，先获得低成本、可解释的候选清理能力。

任务：

1. 增加 constraint normalization 和三态 `HardFilterDecision`。
2. 将明确 excluded role、seniority、work type、location 等规则从风险扣分中提取为独立阶段逻辑。
3. 保留 unknown candidate，并把缺失字段传给 enrichment priority。
4. 在 exact dedupe 后增加 near-duplicate clustering。
5. trace 记录 rejection code counts、unknown counts、cluster counts 和 representative selection。
6. Candidate Filter 保留旧 scorecard 行为，但只消费 accepted/unknown candidates。

验收：

- 明确违反 strict constraint 的岗位不进入后续分析。
- metadata 缺失不会自动拒绝。
- 跨来源重复可聚类，疑似但不确定的岗位不会误删。
- 每个拒绝决定均有 evidence 和稳定 code。

### Phase 3：Budgeted Provider Scheduler 与扩大召回

目的：让 typed plan 真正控制执行，并消除顺序抢占。

任务：

1. `_run_provider_search()` 从 `ProviderSearchTask` 执行，不再截取字符串列表前三项。
2. 实现 coverage round 与 fill round。
3. 支持 per-source query/candidate/time budgets 和全局 deadline。
4. RemoteOK 在一次 run 内复用 feed；其他来源按 capability 控制调用。
5. 默认 pool 从 `2 * max_results` 提升到 `4 * max_results`，绝对 cap 初始为 60；用 feature flag 或配置保留旧策略回退。
6. 配额稳定后，再为独立来源加入 bounded concurrency 和 partial failure 合并。
7. Preview 的请求成本估算改用真实 task plan。

验收：

- 每个 selected source 获得最低配额，除非未配置、失败或预算明确不足。
- 后续 query 不再因第一个 query 快速返回而完全跳过。
- pool 扩大后单次 LLM filter payload 不增加。
- latency、error rate 和 provider request count 不超过 Phase 0 设定的预算。

### Phase 4：三级漏斗与 JD-informed Final Scoring

目的：完成搜索质量 V2 的核心闭环。

任务：

1. 将现有 Candidate Filter 拆为 cheap pre-rank 和 final scorer；保留兼容 facade 直至调用方迁移完成。
2. 增加 `RecallScorecard`、`CandidateEvidence`、`FinalScorecard`。
3. hard-filter 后候选全部走 deterministic pre-rank，只选 Top 20–30。
4. JD Analysis 只处理 Top 12–20，并输出结构化证据与 missing fields。
5. Final Scorer 使用 JD evidence 重算分数，不复用 pre-rank score。
6. 单候选 LLM 失败时使用 deterministic evidence fallback，不触发整批回退。
7. 结果组装只展示 `final_match_score`，并保留 recall score 供 trace/debug 使用。
8. 增加小幅 diversity pass 和 cluster-level result dedupe。

验收：

- 修改 JD 中的明确 required skill、seniority 或 work type 会影响 final score/decision。
- pre-rank 和 final score 在 trace 中可区分。
- 60 个候选不会进入一次 LLM 排序请求。
- 任一候选分析失败不影响其他候选完成。
- Top K constraint violation 为零，前提是 JD 有明确冲突证据。

### Phase 5：离线校准与可观测性（当前替代方案）

目的：在没有真实用户行为数据的阶段，用可复现的离线证据校准查询、来源和排序规则，避免伪造“智能反馈闭环”。

任务：

1. 继续维护少量代表性 fixtures，覆盖 query diversity、strict constraints、跨来源重复和 JD 重评分。
2. 聚合不依赖用户行为的 query/source 指标：zero-result rate、unique yield、duplicate rate、detail coverage 和 latency。
3. Selector priority 保持 deterministic；任何权重调整必须先通过冻结 baseline replay。
4. trace 解释本轮为什么选择这些 query/source，以及哪些候选因何被拒绝。
5. 仅定义未来反馈接入所需的最小指标语义，不新增存储和在线学习代码。

验收：

- 同一 fixture 输入产生稳定结果。
- 约束违规、重复和排序回归能由少量高价值 replay case 捕获。
- 权重变化可解释，并可通过冻结 baseline 比较。

未来只有在存在足量、可区分原因的 save/dismiss/apply 数据后，才考虑用户级时间窗口、衰减和有界权重修正；该能力不属于当前 V2 完成条件。

### Phase 6：清理、文档与默认启用

任务：

1. 在指标达标后删除旧的 `queries[:3]` 执行分支和 scorecard 复用路径。
2. 更新 `SEARCH_PROVIDER.md`、`ARCHITECTURE.md`、preview/API 文档和前端 trace 展示。
3. 固化 migration notes、配置默认值和回滚开关。
4. 完成全量 backend tests、Vue build 和显式 provider smoke tests。

验收：

- 新旧 API response shape 保持兼容，或有明确版本化迁移。
- 六个顶层 trace step 顺序保持稳定，V2 子阶段通过 details 展示。
- 默认路径完全使用 final JD-informed score。
- 旧 feature flag 至少保留一个私测观察周期后再移除。

## 7. 测试与评估矩阵

| 层级 | 必测内容 |
| --- | --- |
| Unit | query typing、selector quotas、provider translation、constraint 三态、alias/token matching、cluster identity、score calculation |
| Integration | typed task plan 到 fake multi-source recall；hard filter 到 JD analysis；analysis 到 final scoring |
| Contract | preview、trace details、JobSearchResult、run recovery 和 fallback 行为 |
| Regression | 当前 planner、provider、candidate filter、JD quality、result assembly 测试 |
| Offline evaluation | Precision@5、nDCG@5、candidate-pool recall、constraint violations、duplicate clusters |
| Live smoke | 每个真实 Provider 的 unique yield、detail coverage、latency、error 和限流行为 |

核心质量指标定义：

- `Precision@5`：Top 5 中标注 relevant 的比例。
- `Recall@pool`：标注相关岗位中进入 hard-filter 前候选池的比例。
- `ConstraintViolation@K`：Top K 中有明确证据违反 strict constraint 的比例，目标为 0。
- `UniqueYield`：每个 query/source 新增 exact identity 或新 cluster 的数量。
- `DetailCoverage`：进入 final scoring 的候选中具有可用完整 JD 的比例。
- `Duplicate@K`：Top K 中属于同一 confirmed duplicate cluster 的额外结果比例。
- `FallbackRate`：planning、analysis 和 scoring 各阶段独立 fallback 比例。
- 成本指标：provider calls、LLM calls、输入 token、p50/p95 latency。

不能只以“候选数更多”作为成功标准。V2 默认启用至少需要满足：

- Precision@5 或 nDCG@5 相对 baseline 有稳定提升；
- ConstraintViolation@5 不劣于 baseline，且明确约束案例为 0；
- Duplicate@5 下降；
- LLM payload 和调用数在预算内；
- p95 latency 没有超过私测可接受阈值。

## 8. 迁移、兼容与回滚

- 先 shadow、后切流：Phase 1 只记录 V2 plan；Phase 3 才改变 recall；Phase 4 才改变展示分数。
- 初期不要求数据库 migration。typed plan、task stats、hard-filter summary 可先写入现有 trace `details`。
- 保留 `JobSearchPlan.queries` 和现有 `filter_candidates()` facade，逐阶段迁移调用方。
- 保持当前六阶段顶层 trace 名称，新增子阶段统计，避免破坏历史和前端。
- 使用配置开关区分 legacy recall、V2 recall 和 V2 final scoring，支持按 run 回退。
- 任何 LLM 输出都通过 schema、索引、证据和分数边界校验；fallback 是受支持结果，不是异常终态。
- 并发只用于相互独立、线程安全的 Provider task 或单候选 analysis；必须有上限和 deadline。

## 9. 推荐交付顺序

建议拆成三个可独立验收的里程碑，而不是一次大改：

1. **V2-A：可观测的查询计划** — Phase 0–1。交付 typed plan、shadow selector 和 baseline，不改变搜索结果。
2. **V2-B：公平召回与约束正确性** — Phase 2–3。交付 hard filter、cluster、source quotas 和扩大的候选池。
3. **V2-C：证据驱动的最终排序** — Phase 4–6。交付三级漏斗、JD-informed score、离线校准和默认启用；真实用户反馈闭环延期。

优先级上，V2-A 和 V2-B 应先于新增 Provider；V2-C 应先于引入通用工作流框架。只有在系统确实需要自动 query rewrite loop、跨阶段回跳或持久化 checkpoint 时，再重新评估 LangGraph 一类编排方案。

## 10. 完成定义

Search Retrieval Quality V2 完成时，应同时满足：

- 搜索执行不再依赖 `search_plan.queries[:3]` 的列表顺序。
- 每次 Provider 调用都能追溯到 typed logical query、source quota 和选择理由。
- strict hard constraint 有三态、证据和稳定 rejection code。
- 候选池足以支持筛选，但 provider/LLM/time budget 始终有界。
- 跨来源 duplicate cluster 不会重复占据最终结果。
- JD Analysis 输出被 Final Scorer 消费，最终卡片不再沿用 recall 预估分。
- 大候选池不会进入单次全量 LLM filter payload。
- 当前由离线指标和运行 trace 验证质量变化；真实用户反馈待数据成熟后接入。
- 当前 API、安全边界、fallback 和 run recovery 行为保持可控兼容。
