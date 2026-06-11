from __future__ import annotations


PROFILE_EVALUATION_CASES = [
    {
        "case_id": "ai_agent_backend_mixed",
        "title": "AI Agent / Backend mixed-language resume",
        "resume_text": """
Li Ming
Target: AI Agent Engineer / Backend Engineer
Skills: Python, FastAPI, Pydantic, Streamlit, LangGraph, SQL, Git
Education: B.S. Computer Science, Shenzhen University
Project: JobAgent / AI Agent project. Built a FastAPI API and Streamlit review flow using Pydantic schemas, SQL storage, and Git workflow.
Responsibilities: designed backend API evidence chain, implemented profile review endpoints, and completed pytest coverage.
实习：负责 backend API evidence chain and profile review endpoints.
Highlight: shipped deterministic evaluation reports and improved resume review reliability.
亮点：优化 resume review reliability and completed deterministic evaluation reports.
""",
        "target_roles": ["AI Agent Engineer", "Backend Engineer"],
        "expected": {
            "skills_any": ["Python", "FastAPI", "Pydantic", "Streamlit", "SQL", "Git"],
            "skills_all": ["Python", "FastAPI", "SQL"],
            "project_min_count": 1,
            "work_experience_min_count": 1,
            "education_keywords": ["Computer Science", "University"],
            "highlight_keywords": ["improved", "evaluation"],
            "expected_warning_keywords": [],
            "allowed_confidence_labels": ["strong", "medium", "limited"],
        },
        "known_limitations": [
            "Project names are often generic even when the resume includes a named project.",
        ],
    },
    {
        "case_id": "embedded_stm32_chinese",
        "title": "Embedded / STM32 Chinese resume",
        "resume_text": """
王同学
目标岗位：嵌入式软件工程师
技能：C, STM32, USART, GPIO, FreeRTOS, RTOS, Git
教育：电子信息工程 本科
嵌入式项目：基于 STM32 的环境监测系统，使用 USART 通信、GPIO 采集、FreeRTOS 任务调度。
项目职责：负责驱动调试和串口协议设计。
""",
        "target_roles": ["Embedded Software Engineer"],
        "expected": {
            "skills_any": ["STM32", "USART", "GPIO", "FreeRTOS", "C"],
            "skills_all": ["STM32", "C"],
            "project_min_count": 1,
            "work_experience_min_count": 0,
            "education_keywords": ["电子信息", "本科"],
            "highlight_keywords": ["调试", "设计"],
            "expected_warning_keywords": ["skills", "work"],
            "allowed_confidence_labels": ["weak", "limited", "medium"],
        },
        "known_limitations": [
            "Embedded vocabulary coverage is weak because KNOWN_SKILLS does not include STM32, USART, GPIO, FreeRTOS, or C.",
        ],
    },
    {
        "case_id": "ml_research_english",
        "title": "ML / Research English resume",
        "resume_text": """
Alex Chen
Target: Machine Learning Engineer / Research Assistant
Skills: Python, PyTorch, NumPy, Pandas, scikit-learn
Education: M.S. Data Science, City University
Research Assistant: built dataset cleaning pipelines and ran experiments for a paper submission.
Project: Image classification experiment using PyTorch, NumPy, Pandas, and scikit-learn.
Highlight: improved validation accuracy from 88% to 95% across 300 test cases.
""",
        "target_roles": ["Machine Learning Engineer", "Research Assistant"],
        "expected": {
            "skills_any": ["PyTorch", "NumPy", "Pandas", "scikit-learn"],
            "skills_all": ["NumPy", "Pandas"],
            "project_min_count": 1,
            "work_experience_min_count": 1,
            "education_keywords": ["Data Science", "University"],
            "highlight_keywords": ["accuracy", "experiment"],
            "expected_warning_keywords": [],
            "allowed_confidence_labels": ["strong", "medium", "limited"],
        },
        "known_limitations": [
            "English work experience may be under-detected when lines do not use current work trigger vocabulary.",
            "Highlights are keyword-based and may miss accuracy or experiment evidence.",
        ],
    },
    {
        "case_id": "weak_resume_sparse",
        "title": "Weak resume with sparse information",
        "resume_text": "I know Python and want an AI job.",
        "target_roles": [],
        "expected": {
            "skills_any": ["Python"],
            "skills_all": ["Python"],
            "project_min_count": 1,
            "work_experience_min_count": 1,
            "education_keywords": ["University"],
            "highlight_keywords": ["accuracy", "improved", "shipped"],
            "expected_warning_keywords": ["project", "work", "highlight", "target"],
            "allowed_confidence_labels": ["weak", "limited"],
        },
        "known_limitations": [
            "Fallback project detection can create a project-shaped object from very short text, so project count alone is not enough.",
        ],
    },
    {
        "case_id": "rich_resume_full_profile",
        "title": "Rich resume with education, internship, projects, certificate, and metrics",
        "resume_text": """
Zhao Rui
Target: Backend Engineer / AI Platform Engineer
Education: B.S. Software Engineering, South China University of Technology
教育：软件工程 本科 大学
Internship: Backend Intern at Example Cloud, responsible for 20 APIs, SQL schema review, and Git-based release checks.
实习：负责 20 APIs, SQL schema review, and Git-based release checks.
Projects: JobAgent profile review platform using Python, FastAPI, Pydantic, Streamlit, SQL, and pytest.
Skills: Python, FastAPI, Pydantic, Streamlit, SQL, Git, Pandas
Certificate / Awards: CET-6, University Programming Contest award
Highlight: delivered 300 test cases, improved API regression reliability, and reached 95% parser evaluation accuracy in demo data.
亮点：优化 API regression reliability, completed 300 test cases, and reached 95% parser evaluation accuracy in demo data.
""",
        "target_roles": ["Backend Engineer", "AI Platform Engineer"],
        "expected": {
            "skills_any": ["Python", "FastAPI", "Pydantic", "Streamlit", "SQL", "Git"],
            "skills_all": ["Python", "FastAPI", "Pydantic", "SQL"],
            "project_min_count": 1,
            "work_experience_min_count": 1,
            "education_keywords": ["Software Engineering", "University"],
            "highlight_keywords": ["20 APIs", "95%", "300 test cases"],
            "expected_warning_keywords": [],
            "allowed_confidence_labels": ["strong", "medium"],
        },
        "known_limitations": [
            "Education fields are not deeply parsed beyond raw text matching.",
        ],
    },
]
