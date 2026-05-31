# JD URL Import

## 功能用途

这个功能让用户在保留手动粘贴 JD 的前提下，多一个更省事的入口：

- 输入一个公开 JD URL
- 系统尝试抓取页面响应
- 做一次简单文本提取
- 把提取结果返回给 API，或填入 Streamlit 的 JD 输入框

它的定位是“公开网页文本提取工具”，不是爬虫系统。

## 安全边界

当前实现严格限制在以下范围内：

- 只允许 `http` / `https`
- 不处理登录
- 不处理验证码
- 不绕过反爬
- 不执行 JavaScript
- 不模拟浏览器行为
- 不抓需要认证的网站
- 不做批量抓取
- 不做定时抓取
- 请求失败时，提示用户手动粘贴 JD

## 数据流

```text
JD URL
  -> validate_jd_url
  -> fetch once with timeout + size limit
  -> content-type check
  -> text/plain or simple HTML extraction
  -> whitespace cleanup
  -> extracted_text
  -> API response or Streamlit JD textbox
```

核心逻辑都放在：

- `app/services/jd_url_service.py`

页面和 route 只负责调用，不重复实现抓取逻辑。

## API 示例

接口：

```text
POST /jobs/import-url
```

请求：

```json
{
  "url": "https://example.com/job"
}
```

成功响应：

```json
{
  "url": "https://example.com/job",
  "extracted_text": "岗位标题... 岗位职责... 任职要求...",
  "warning": null
}
```

失败响应：

```json
{
  "detail": "Failed to fetch JD URL. Please paste the JD manually.",
  "error_code": "jd_url_fetch_failed"
}
```

## Streamlit 使用方式

在“生成报告”页的 JD 区域：

1. 输入公开 JD URL
2. 点击“从 URL 导入 JD”
3. 成功后，提取文本会填入现有 JD 文本框
4. 失败时会显示清晰错误，用户仍然可以继续手动粘贴 JD

这不会替换现有手动输入流程，只是增加一个可选入口。

## 错误码

- `jd_url_invalid`
- `jd_url_scheme_unsupported`
- `jd_url_fetch_failed`
- `jd_url_response_too_large`
- `jd_url_content_type_unsupported`
- `jd_url_text_too_short`

## 当前限制

- 默认超时是 8 秒
- 默认最大响应体积是 512KB
- 最大响应体积可通过 `JOBAGENT_MAX_JD_URL_BYTES` 配置
- 仅支持 `text/html` 和 `text/plain`
- HTML 提取只做简单去标签，不做复杂正文识别
- 不执行 JavaScript，所以依赖前端渲染的页面可能提取失败
- 提取文本过短时会拒绝，并建议手动粘贴

## 后续可扩展方向

在不突破当前安全边界的前提下，后续可以考虑：

1. 更稳一点的正文区域识别
2. 更细的 warning 提示
3. 对少量常见公开招聘页做更温和的文本清洗规则
4. 与历史岗位库做去重提示
