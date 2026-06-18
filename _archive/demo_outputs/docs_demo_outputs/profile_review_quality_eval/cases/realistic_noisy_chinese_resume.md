# Realistic noisy Chinese resume without clean headings

## Resume summary
- case_id: realistic_noisy_chinese_resume
- target_roles: AI Agent Intern, Backend Engineer Intern, Data Analyst Intern

## Baseline parsed result
- baseline_confidence_label: strong
- baseline_quality_warnings: -
- baseline_missing_info_questions: -
- parsed_skills: Python, FastAPI, Streamlit, SQLite, Git, Pandas, NumPy, PyTorch, Librosa, MFCC, STFT, CNN, VGG, 数据分析
- parsed_project_count: 1
- parsed_work_experience_count: 2
- parsed_education_count: 1
- parsed_highlights: 之前做过一个求职分析工具，用 FastAPI、Streamlit、SQLite 做过接口和页面，也写过一些测试。这个项目主要是把简历解析、岗位分析、匹配报告和可视化页面串起来，我负责后端接口、前端展示和测试数据整理。, 还做过课程里的音频分类实验，用 PyTorch、Librosa、MFCC、STFT 做特征和模型训练，比过 CNN 和 VGG 的效果，验证准确率最高大概 75%。另外也写过一些 Python 数据处理脚本，会用 Pandas、NumPy 和 Git。

## Profile draft summary
- draft: {"skill_count": 14, "project_count": 1, "work_experience_count": 2, "education_count": 1, "highlight_count": 2, "target_roles": ["AI Agent Intern", "Backend Engineer Intern", "Data Analyst Intern"]}

## LLM enrichment result
- enrichment_enabled: True
- enrichment_suggestion_count: 0
- enrichment_llm_success_count: 4
- enrichment_fallback_count: 0
- enrichment_discarded_suggestion_count: 4
- enrichment_quality_warnings: discarded ungrounded profile enrichment suggestion

## Simulated user decisions
- accepted_suggestion_count: 0
- edited_suggestion_count: 0
- rejected_suggestion_count: 0

## Confirmed profile result
- confirmed_confidence_label: strong
- confirmed_skill_count: 14
- confirmed_project_count: 1
- confirmed_work_experience_count: 2
- confirmed_remaining_warnings: -

## Save payload readiness
- save_payload_ready: True

## Quality verdict
- quality_verdict: strong

## Reviewer notes
- discarded 4 unsupported enrichment suggestions
