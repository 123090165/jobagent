# Live Job Provider

## 1. Design Goal

This round adds a small reusable framework for public live job fetching so that JobAgent can:

- fetch a public list page
- parse site-specific job cards
- fetch a small number of public detail pages
- evaluate JD quality
- normalize results into `SearchResultItem`
- optionally cache results into `public_job_posts`

The goal is not a universal crawler. The goal is a low-risk, low-frequency framework for public HTML job sources.

## 2. Current Providers

- `mock`
  - local demo-only provider
- `local_db`
  - replays already collected jobs from `public_job_posts`
- `cuhksz_live`
  - fetches the current public CUHKSZ list page and then fetches a small number of public detail pages in real time
- `gemini_cli`
  - experimental search provider, disabled by default

## 3. Why This Is Not A Universal Crawler

JobAgent deliberately does not try to crawl every recruitment site.

Out of scope:

- login
- cookies or session replay
- captcha handling
- browser automation
- anti-bot bypass
- JavaScript-heavy authenticated flows
- automatic application submission

If a source requires these capabilities, it is outside the current boundary.

## 4. Framework Shape

Directory layout:

```text
app/services/live_job/
  __init__.py
  base.py
  fetcher.py
  provider.py
  parsers/
    __init__.py
    cuhksz.py
```

Responsibilities:

- `fetcher.py`
  - shared public HTML fetching with scheme validation, timeout, max-bytes guard, and stable error handling
- `base.py`
  - shared raw models such as `RawJobListItem` and `RawJobDetail`
- `parsers/cuhksz.py`
  - site-specific CUHKSZ parsing logic only
- `provider.py`
  - live provider orchestration: list fetch, candidate selection, detail fetch, normalization, and optional local DB write

The key split is:

- framework code handles fetch/orchestration
- parser code handles selectors and site-specific extraction

That keeps future site additions bounded to “new parser or adapter first”, instead of duplicating fetch and safety logic.

## 5. CUHKSZ Live Provider Usage

API example:

```json
{
  "query": "AI PyTorch 深圳",
  "provider": "cuhksz_live",
  "limit": 3
}
```

Python example:

```python
from app.services.job_search_service import search_jobs

result = search_jobs("AI PyTorch 深圳", provider="cuhksz_live", limit=3)
```

Optional local caching:

```python
from app.services.live_job.provider import CUHKSZLiveProvider

provider = CUHKSZLiveProvider(save_to_local_db=True)
result = provider.search_jobs("AI 深圳", limit=3)
```

When `save_to_local_db=True`, fetched detail results are upserted into `public_job_posts`.

Current `cuhksz_live` is not full-site full-text real-time search.

当前 `cuhksz_live` 不是全站全文实时搜索。它的流程是：

1. 请求 CUHKSZ 当前公开列表页；
2. 先根据列表页字段 `title` / `company` / `location` / `job_type` / `education` 对 query 做粗筛和排序；
3. 只对少量候选岗位抓取详情页；
4. 将详情页 JD 解析为 `SearchResultItem`；
5. 可选写回 `local_db`。

因此，如果关键词只出现在详情页正文而没有出现在列表页字段中，当前版本可能无法优先命中。后续可以通过 scheduler + `local_db` 缓存、详情页索引或 `GenericHtmlParser` 改进。

`cuhksz_live` uses two-stage ranking:

1. list-page ranking: `title`, `company`, `location`, `job_type`, and `education` are used to pick a small candidate set
2. detail rerank: after fetching detail pages, `jd_text` and extracted sections are used to rerank successful details before returning top results

This improves queries where the keyword appears only in the detail JD text, but it is still not full-site full-text search because only a small candidate set is fetched.

注意：二次排序只能够在已抓取的候选详情页中生效，不能替代全站索引。

## 6. Safety Boundary

- public `http/https` pages only
- request timeout is required
- response body size is capped
- no login
- no cookies
- no captcha handling
- no Playwright or Selenium
- no LLM in the fetch path
- no automatic apply
- low-frequency, small-batch detail fetching only

## 7. Current Limitations

- `cuhksz_live` only fetches the current list page
- it only fetches a small number of detail pages after lightweight query ranking
- it does not follow multi-hop flows
- it does not execute JavaScript
- low-quality or summary-like JDs are still returned with `quality_label`, `confidence`, and `warnings`, but they remain lower-trust inputs
- Streamlit still exposes `mock` and `local_db` only; `cuhksz_live` is currently API/service level

## 8. Why Keep `local_db`

`cuhksz_live` and `local_db` solve different problems:

- `cuhksz_live`
  - real-time fetch from the current public page
- `local_db`
  - stable replay of already collected jobs for demos, repeatable scoring, and offline review

Keeping both gives us:

- a real-time fetch path
- a reproducible local demo path
- a shared normalized output contract

## 9. Follow-up Ideas

- `GenericHtmlParser`
- one-hop external link fetch under the same safety rules
- optional structure enhancer after fetch
- scheduled cache refresh for safe public sources
