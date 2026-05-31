# Screenshot Guide

> 用途：规划 README、作品集和答辩 PPT 所需截图，保证展示材料覆盖核心链路。

## 截图清单

| 截图 | 内容 | 用途 |
| --- | --- | --- |
| Streamlit 生成报告页 | 左侧简历输入、右侧 JD 输入、侧边栏配置 | README、答辩 PPT |
| 文件上传成功 | 上传 `.txt` / `.md` 后显示成功提示，文本填入简历输入区 | README、答辩 PPT |
| 匹配分数 | 总匹配分、技能分、项目分、关键词覆盖 | README、答辩 PPT |
| Markdown 报告 | 报告正文，突出匹配度总览和优化建议 | 作品集、答辩 PPT |
| workflow trace | 步骤数、耗时、fallback、run id 和步骤表格 | README、答辩 PPT |
| 历史记录 | 已保存分析记录列表和详情入口 | README、答辩 PPT |
| 岗位库 | 岗位列表、原始 JD、结构化 JD 分析 | 答辩 PPT |
| 简历版本 | 版本表单、版本列表、原始/定制文本详情 | 作品集、答辩 PPT |
| 投递 tracker | 岗位状态、下一步行动、简历版本关联 | 作品集、答辩 PPT |
| FastAPI docs | `/resume/parse-file`、`/analyze/full` 等接口 | README、答辩 PPT |

## 建议截图顺序

1. 先截 Streamlit 生成报告页，证明工具第一屏可用。
2. 再截文件上传成功，展示 txt/md 简历文件解析。
3. 生成报告后截匹配分数和 Markdown 报告。
4. 截 workflow trace，突出可观察性。
5. 截历史记录和岗位库，展示保存与复盘。
6. 截简历版本和投递 tracker，展示求职准备闭环。
7. 最后截 FastAPI docs，说明能力可被 API 调用。

## 截图注意事项

- 使用样例数据，不要展示真实隐私简历。
- 截图里不要包含 API key、真实手机号、邮箱或招聘平台账号。
- 保留浏览器地址或页面标题，方便说明本地运行。
- README 优先放 3 到 5 张高信息密度截图。
- 答辩 PPT 可以按“输入 -> 分析 -> trace -> 复盘 -> API”组织截图。
