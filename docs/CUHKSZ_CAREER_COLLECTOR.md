# CUHKSZ Career Collector MVP

## 1. 功能目标

CUHKSZ Career Collector MVP 用于从港中深职业规划与发展处公开招聘信息页采集当前列表页的前 N 条岗位，继续抓取每条岗位的公开详情页，抽取清洗后的 `jd_text`，并保存到本地 SQLite 的 `public_job_posts` 表。

本阶段重点是“公开岗位本地化存储”，后续再让 `LocalPublicJobProvider` 从本地表读取岗位并服务 Batch Job Brief。

## 2. 目标页面

默认列表页：

```text
https://career.cuhk.edu.cn/job/search/d_category/102
```

当前解析依赖的公开 HTML 结构：

- 岗位列表：`.sousuo_list ul > li`
- 公司名：`.sousuo_list_com a`
- 岗位标题与详情链接：`.sousuo_list_xx a.f18`
- 地点 / 职位性质 / 学历：`.sousuo_list_xx .mt10.mb10`
- 发布时间与结束时间：`.sousuo_list_time`
- 详情链接示例：`/job/view/id/468293`

## 3. 数据流

```text
list page -> detail page -> jd_text -> public_job_posts
```

详细流程：

1. 请求公开列表页 HTML。
2. 解析岗位卡片，得到 title、company、location、job_type、education、published_at、deadline、external_id 和 detail_url。
3. 截取当前列表页前 `--limit` 条。
4. 逐条请求公开详情页 HTML。
5. 使用 BeautifulSoup 清理脚本、样式、导航和页脚，抽取正文。
6. 评估 `is_full_jd`、`confidence` 和 warnings。
7. 非 dry-run 时 upsert 到 `public_job_posts`。
8. 写本地 raw report；可选写 docs 下的脱敏 preview。

## 4. 安全边界

本 collector 只做低频、公开页面、小批量采集：

- 只访问公开 `http/https` 页面。
- 不登录。
- 不读取或复用 Cookie。
- 不处理验证码。
- 不做反爬绕过。
- 不执行 JavaScript。
- 不使用 Playwright 或 Selenium。
- 不自动投递。
- 不抓取全部分页。
- 不保存原始 HTML、Cookie、token 或登录信息。

## 5. 运行示例

采集默认页面前 10 条，并生成 docs 脱敏报告：

```powershell
python scripts/collect_cuhksz_jobs.py ^
  --list-url "https://career.cuhk.edu.cn/job/search/d_category/102" ^
  --limit 10 ^
  --publish-sanitized
```

如果本机使用项目虚拟环境：

```powershell
.venv\Scripts\python.exe scripts\collect_cuhksz_jobs.py ^
  --list-url "https://career.cuhk.edu.cn/job/search/d_category/102" ^
  --limit 10 ^
  --publish-sanitized
```

## 6. Dry-run 示例

dry-run 会抓取和生成 report，但不写 SQLite：

```powershell
python scripts/collect_cuhksz_jobs.py ^
  --list-url "https://career.cuhk.edu.cn/job/search/d_category/102" ^
  --limit 5 ^
  --dry-run
```

本机虚拟环境版本：

```powershell
.venv\Scripts\python.exe scripts\collect_cuhksz_jobs.py ^
  --list-url "https://career.cuhk.edu.cn/job/search/d_category/102" ^
  --limit 5 ^
  --dry-run
```

## 7. 输出文件

本地 raw report：

```text
demo_runs/cuhksz_collect/<timestamp>/
  collect_summary.json
  collected_jobs.json
  errors.json
```

`collected_jobs.json` 包含完整清洗后的 `jd_text`，仅用于本地调试和验证。

可发布的脱敏输出：

```text
docs/demo_runs/cuhksz_collect_<timestamp>/
  README.md
  collect_summary.json
  collected_jobs_preview.json
```

`collected_jobs_preview.json` 不保存完整 `jd_text`，只保留最多 500 字符的 `jd_text_preview`。

## 8. 数据库字段

表名：`public_job_posts`

关键字段：

- `source`: 当前为 `cuhksz_career`
- `external_id`: 从详情链接解析，例如 `468293`
- `source_url`: 公开详情页 URL
- `title`, `company`, `location`, `job_type`, `education`
- `published_at`, `deadline`
- `snippet`: JD 预览
- `jd_text`: 清洗后的 JD 文本
- `is_full_jd`: 是否可能是完整 JD
- `confidence`: 抽取质量置信度
- `extraction_method`: 当前为 `cuhksz_html`
- `content_hash`: `title + company + source_url + jd_text` 的 hash
- `fetched_at`, `updated_at`

唯一约束：

```text
UNIQUE(source, external_id)
```

重复运行同一岗位时会 upsert，不会重复插入同一个 `source + external_id`。

## 9. 当前限制

- 只抓当前列表页前 N 条。
- 不处理分页。
- 不保证每个详情页都有完整 JD。
- 不提供实时联网 provider；当前只支持从本地 `public_job_posts` 回放的 `local_db`。
- 质量判断是轻量启发式规则，不是最终质量门禁。

## 10. 后续

- `local_db` provider 已实现：从 `public_job_posts` 读取本地真实岗位，作为 `provider="local_db"` 接入搜索抽象。
- JD Extraction Quality Gate: 更严格地区分正文、导航噪声、登录页、空页和低质量 JD。
- Real Batch Job Brief Demo: 使用本地真实岗位库跑批量岗位 brief。
