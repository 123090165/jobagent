# Resume Profile Parser Evaluation Summary

## Overall
- total_cases: 5
- strong_cases: 4
- medium_cases: 0
- limited_cases: 1
- weak_cases: 0

## Case Table
| case_id | title | confidence_label | evaluation_label | passed | failed | project_count | work_experience_count | skills_hit |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| ai_agent_backend_mixed | AI Agent / Backend mixed-language resume | strong | strong | 9 | 0 | 3 | 1 | Python, FastAPI, Pydantic, Streamlit, SQL, Git |
| embedded_stm32_chinese | Embedded / STM32 Chinese resume | strong | strong | 9 | 0 | 2 | 1 | STM32, USART, GPIO, FreeRTOS, C |
| ml_research_english | ML / Research English resume | strong | strong | 9 | 0 | 2 | 2 | PyTorch, NumPy, Pandas, scikit-learn |
| weak_resume_sparse | Weak resume with sparse information | limited | limited | 6 | 3 | 1 | 0 | Python |
| rich_resume_full_profile | Rich resume with education, internship, projects, certificate, and metrics | strong | strong | 9 | 0 | 1 | 2 | Python, FastAPI, Pydantic, Streamlit, SQL, Git |

## Known Limitations
- Project title extraction is improved, but multi-line project grouping remains shallow.
- Embedded vocabulary is covered, but embedded project evidence may still be thin without measurable outcomes.
- English research experience is detected, but title and evidence lines may become separate work items.
- Highlights are still keyword and metric based rather than semantically ranked.
- Fallback project detection can create a project-shaped object from very short text, so project count alone is not enough.
- Education school, degree, and major extraction is lightweight and still preserves raw text as source evidence.

## Detailed Case Results

### ai_agent_backend_mixed: AI Agent / Backend mixed-language resume
- failed_checks: -
- warnings: -
- missing_info_questions: -
- skill_hits: Python, FastAPI, Pydantic, Streamlit, SQL, Git
- missing_expected_skills: -

### embedded_stm32_chinese: Embedded / STM32 Chinese resume
- failed_checks: -
- warnings: project evidence may be too thin for matching
- missing_info_questions: For your strongest project, what exactly did you build, which technologies did you use, and what measurable result can you show?
- skill_hits: STM32, USART, GPIO, FreeRTOS, C
- missing_expected_skills: -

### ml_research_english: ML / Research English resume
- failed_checks: -
- warnings: -
- missing_info_questions: -
- skill_hits: PyTorch, NumPy, Pandas, scikit-learn
- missing_expected_skills: -

### weak_resume_sparse: Weak resume with sparse information
- failed_checks: work_experience_count_min, education_keyword_match, highlight_keyword_match
- warnings: resume profile has no project evidence, resume profile has no work experience evidence, target role is not explicit, resume profile has no highlights or measurable outcomes
- missing_info_questions: What target roles should this profile prioritize, such as AI Agent Engineer, Backend Engineer, or Embedded Software Engineer?, Which project best demonstrates your target role fit? Please add project goal, technologies, your responsibilities, and outcomes., Do you have internship, lab, research, or course project experience that should be treated as work-like evidence?, Can you add measurable outcomes, such as number of APIs, tests passed, latency, users, dataset size, or accuracy?
- skill_hits: Python
- missing_expected_skills: -

### rich_resume_full_profile: Rich resume with education, internship, projects, certificate, and metrics
- failed_checks: -
- warnings: -
- missing_info_questions: -
- skill_hits: Python, FastAPI, Pydantic, Streamlit, SQL, Git
- missing_expected_skills: -
