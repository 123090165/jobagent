# Resume Profile Parser Evaluation Summary

## Overall
- total_cases: 5
- strong_cases: 2
- medium_cases: 1
- limited_cases: 2
- weak_cases: 0

## Case Table
| case_id | title | confidence_label | evaluation_label | passed | failed | project_count | work_experience_count | skills_hit |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| ai_agent_backend_mixed | AI Agent / Backend mixed-language resume | strong | strong | 9 | 0 | 2 | 1 | Python, FastAPI, Pydantic, Streamlit, SQL, Git |
| embedded_stm32_chinese | Embedded / STM32 Chinese resume | strong | limited | 5 | 4 | 2 | 1 | - |
| ml_research_english | ML / Research English resume | medium | medium | 8 | 1 | 1 | 0 | NumPy, Pandas, scikit-learn |
| weak_resume_sparse | Weak resume with sparse information | limited | limited | 6 | 3 | 1 | 0 | Python |
| rich_resume_full_profile | Rich resume with education, internship, projects, certificate, and metrics | strong | strong | 9 | 0 | 1 | 1 | Python, FastAPI, Pydantic, Streamlit, SQL, Git |

## Known Limitations
- Project names are often generic even when the resume includes a named project.
- Embedded vocabulary coverage is weak because KNOWN_SKILLS does not include STM32, USART, GPIO, FreeRTOS, or C.
- English work experience may be under-detected when lines do not use current work trigger vocabulary.
- Highlights are keyword-based and may miss accuracy or experiment evidence.
- Fallback project detection can create a project-shaped object from very short text, so project count alone is not enough.
- Education fields are not deeply parsed beyond raw text matching.

## Detailed Case Results

### ai_agent_backend_mixed: AI Agent / Backend mixed-language resume
- failed_checks: -
- warnings: -
- missing_info_questions: -
- skill_hits: Python, FastAPI, Pydantic, Streamlit, SQL, Git
- missing_expected_skills: -

### embedded_stm32_chinese: Embedded / STM32 Chinese resume
- failed_checks: skills_any_match, skills_all_match, expected_warning_match, confidence_label_allowed
- warnings: project evidence may be too thin for matching
- missing_info_questions: For your strongest project, what exactly did you build, which technologies did you use, and what measurable result can you show?
- skill_hits: -
- missing_expected_skills: STM32, C

### ml_research_english: ML / Research English resume
- failed_checks: work_experience_count_min
- warnings: resume profile has no work experience evidence, resume profile has no highlights or measurable outcomes
- missing_info_questions: Do you have internship, lab, research, or course project experience that should be treated as work-like evidence?, Can you add measurable outcomes, such as number of APIs, tests passed, latency, users, dataset size, or accuracy?
- skill_hits: NumPy, Pandas, scikit-learn
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
