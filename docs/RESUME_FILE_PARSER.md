# Resume File Parser MVP

> 用途：记录当前简历文件解析能力的范围、数据流、错误边界和后续计划。

## 1. 当前目标

用户可以继续粘贴简历文本，也可以上传 `.txt` 或 `.md` 简历文件。文件解析只负责把受支持文件转换成 UTF-8 纯文本，然后复用现有 `ResumeParseAgent` 生成 `ResumeProfile`。

当前稳定支持：

- `.txt`
- `.md`

暂不支持：

- `.pdf`
- `.docx`

PDF/DOCX 放到后续计划，不在当前 MVP 引入大型文档解析依赖。

## 2. 数据流

```text
UploadFile bytes
-> resume_file_service 校验文件名和扩展名
-> UTF-8 解码
-> 空内容校验
-> extracted_text
-> ResumeParseAgent
-> ResumeProfile
```

API 返回：

- `filename`
- `file_type`
- `extracted_text`
- `resume_profile`

## 3. 代码位置

```text
app/services/resume_file_service.py
app/api/routes_resume.py
frontend/streamlit_app.py
tests/test_resume_file_service.py
tests/test_api.py
```

## 4. 设计边界

- service 不调用 UI。
- service 不写数据库。
- API route 保持薄封装，只做上传接收、错误映射和响应组装。
- Streamlit 只调用 service，把提取文本填入现有简历输入区。
- 文件解析不会编造经历、公司、项目、数据或技术栈。
- `ResumeProfile` 仍由 `ResumeParseAgent` 负责。

## 5. 错误处理

- 空文件或纯空白文件：`resume file cannot be empty`
- 不支持的扩展名：`unsupported resume file type`
- 非 UTF-8 内容：`resume file must be UTF-8 text`
- 缺少文件名：`filename is required`

这些错误在 API 中映射为 HTTP 400，方便前端和调用方直接展示。

## 6. 后续计划

- 增加 PDF 文本提取时，先评估依赖体积、提取质量和隐私风险。
- 增加 DOCX 文本提取时，优先复用轻量、稳定的文档读取能力。
- 对 PDF/DOCX 继续保持“只提取已有文本，不生成不存在内容”的边界。
- 如需保存上传历史，应单独设计 storage schema，不把文件处理逻辑塞进 route 或 UI。
