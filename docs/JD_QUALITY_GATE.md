# JD Quality Gate

## 1. Why JobAgent Needs A JD Quality Gate

Once `local_db` starts replaying previously collected public jobs, not every stored record has the same value for matching and reranking.

Some jobs contain a real structured JD.
Some only keep list-page summaries.
Some mainly point to external links such as WeChat articles.
Some pages are clearly invalid, such as login pages or error pages.

The JD Quality Gate standardizes this difference so the system can:

- rank stronger JD sources earlier
- expose confidence more honestly in Batch Job Brief
- avoid treating thin summaries as equal to full job descriptions

## 2. Quality Labels

### `full_jd`

Use when the text looks like a complete JD.

Typical signals:

- long enough body text
- responsibility section
- requirement section
- some metadata or structured context
- skills / degree / experience style signals

### `partial_jd`

Use when there is meaningful job body content, but the JD is incomplete.

Typical signals:

- some responsibility or requirement text exists
- useful for matching
- still missing part of the expected structure

### `external_link_only`

Use when the current page mainly points to an external detail page.

Typical signals:

- `mp.weixin.qq.com`
- `docs.qq.com`
- `jinshuju`
- “详见” / “请查看”

These roles are still valid leads, but the current page is not the real JD body.

### `snippet_only`

Use when the text mostly contains title / company / location / publish time / short summary, but no real JD sections.

### `invalid`

Use when the page is clearly not a usable JD.

Typical signals:

- login page
- captcha page
- access denied / forbidden / 403 / 404
- empty or near-empty text without meaningful JD signals

## 3. CUHKSZ Examples

- 安克创新：`full_jd`
  Reason: structured responsibility + requirement content with enough body text.

- 小鹏汽车微信外链：`external_link_only`
  Reason: the current page mainly points to a WeChat detail page.

- 东北证券微信外链：`external_link_only`
  Reason: the useful content is mainly outside the current page.

## 4. Effect On Batch Job Brief

The quality label now affects:

- `local_db` ranking priority
- `SearchResultItem.confidence`
- `SearchResultItem.is_full_jd`
- Batch Job Brief `scoring_quality`
- Streamlit quality display text

Current quality order:

1. `full_jd`
2. `partial_jd`
3. `external_link_only`
4. `snippet_only`
5. `invalid`

Batch Job Brief now makes it clearer when recommendations come from:

- complete JDs
- partial JDs
- external-link-only roles
- snippet-only roles

## 5. Current Limits

- This is a heuristic rule set, not an LLM-based validator.
- JobAgent does not fetch WeChat article bodies.
- The gate is not guaranteed to be 100% accurate.
- A later round could add optional LLM review, but this MVP intentionally does not.
