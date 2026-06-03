# Real Local Job Brief Demo

## 1. Goal

This demo turns previously collected public jobs in `public_job_posts` into a real `local_db` Job Brief run.

It is intentionally local-only:

- no real-time web search
- no login
- no cookies
- no anti-bot bypass
- no front-end collection trigger

## 2. Step 1: Collect Public Jobs First

Run the CUHKSZ collector before using `local_db`:

```powershell
python scripts/collect_cuhksz_jobs.py --limit 10
```

If you use the project virtual environment:

```powershell
.venv\Scripts\python.exe scripts\collect_cuhksz_jobs.py --limit 10
```

## 3. Step 2: Generate A Real Local Job Brief

Run the local brief demo script:

```powershell
python scripts/demo_real_local_job_brief.py --resume-file data/samples/sample_resume.md --query "AI PyTorch 生理信号 深圳" --limit 5 --publish-sanitized
```

If you use the project virtual environment:

```powershell
.venv\Scripts\python.exe scripts/demo_real_local_job_brief.py --resume-file data/samples/sample_resume.md --query "AI PyTorch 生理信号 深圳" --limit 5 --publish-sanitized
```

Raw local outputs:

```text
demo_runs/real_local_job_brief/<timestamp>/
  brief_summary.json
  recommended_jobs.json
  README.md
```

Sanitized publish outputs:

```text
docs/demo_runs/real_local_job_brief_<timestamp>/
  README.md
  brief_summary.json
  recommended_jobs_preview.json
```

## 4. Streamlit Usage

1. 打开岗位批量推荐页面。
2. provider 选择 `local_db`。
3. 输入简历和 query。
4. 生成 Brief。

Provider note:

- `local_db`：从本地 `public_job_posts` 岗位库搜索真实已采集岗位。请先运行 CUHKSZ collector。
- `local_db` 会优先排序 `full_jd`，其次是 `partial_jd`，再往后是外链或摘要型岗位。

If the local job store is empty, Streamlit will prompt:

```text
本地岗位库为空，请先运行 python scripts/collect_cuhksz_jobs.py --limit 10
```

## 5. Sanitization Rules

For `docs/demo_runs` outputs:

- do not store full `resume_text`
- do not store full `jd_text`
- keep `jd_text_preview` at 500 characters or fewer
- allowed preview fields include `title`, `company`, `source_url`, `fit_score`, `scoring_quality`, `is_full_jd`, `confidence`, and `advice`

## 6. Current Limits

- `local_db` is not real-time web search.
- It only uses already collected jobs.
- `partial_jd` results have lower confidence.
- Some WeChat/external-link style jobs may only keep summary-like content.
- The current JD quality gate is heuristic and not guaranteed to be 100% accurate.
