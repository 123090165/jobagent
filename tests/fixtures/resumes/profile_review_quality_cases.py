from __future__ import annotations

from pydantic import BaseModel, Field


class ProfileReviewQualityCase(BaseModel):
    case_id: str
    title: str
    resume_text: str
    target_roles: list[str] = Field(default_factory=list)
    expected_focus: list[str] = Field(default_factory=list)
    expected_skills: list[str] = Field(default_factory=list)
    expected_sections: list[str] = Field(default_factory=list)
    should_have_warnings: bool
    expected_confidence_without_llm: str | None = None


PROFILE_REVIEW_QUALITY_CASES = [
    ProfileReviewQualityCase(
        case_id="ai_agent_backend",
        title="AI Agent / Backend product resume",
        resume_text="""
Li Ming
Target Roles: AI Agent Engineer / Backend Engineer
Skills: Python, FastAPI, Streamlit, SQLite, LangGraph, LangChain, Pydantic, pytest, Git
Education: B.S. Computer Science, Shenzhen University
Projects:
JobAgent - built a FastAPI and Streamlit workflow for resume review, persistence, and evaluation artifacts.
- Designed profile review endpoints and SQLite persistence payloads.
- Shipped 20 APIs and completed 300 tests.
AgentOps Demo Platform - built LangGraph agent orchestration with LLM evaluation reports.
Experience:
Backend Intern, Example AI Lab
- Implemented API routes, fixed parser edge cases, and reviewed deterministic evaluation output.
Highlights: Improved profile review reliability and released reproducible evaluation reports.
""",
        target_roles=["AI Agent Engineer", "Backend Engineer"],
        expected_focus=["api", "workflow", "agent", "evaluation"],
        expected_skills=[
            "Python",
            "FastAPI",
            "Streamlit",
            "SQLite",
            "LangGraph",
        ],
        expected_sections=["projects", "work_experiences", "education", "highlights"],
        should_have_warnings=False,
        expected_confidence_without_llm="strong",
    ),
    ProfileReviewQualityCase(
        case_id="embedded_stm32",
        title="Embedded STM32 course-project resume",
        resume_text="""
Wang Lei
Target Role: Embedded Software Engineer
Skills: C, C++, STM32, USART, UART, GPIO, DMA, ADC, PWM, Keil, CubeMX, Git
Education: B.Eng. Electronic Information Engineering, South China University
Projects:
STM32 Environment Monitor System
- Used STM32, ADC, PWM, GPIO, and USART to collect sensor data and drive alarms.
- Responsible for board bring-up, serial protocol design, and embedded driver debugging.
Lab Project: Smart Car Controller using UART, DMA, and CubeMX configuration.
Highlights: Completed lab integration and improved hardware debugging efficiency.
""",
        target_roles=["Embedded Software Engineer"],
        expected_focus=["stm32", "uart", "driver", "debugging"],
        expected_skills=["C", "STM32", "USART", "GPIO", "DMA", "ADC", "PWM"],
        expected_sections=["projects", "education", "highlights"],
        should_have_warnings=False,
        expected_confidence_without_llm="medium",
    ),
    ProfileReviewQualityCase(
        case_id="ml_audio_asr",
        title="ML Audio / ASR resume",
        resume_text="""
Alex Chen
Target Roles: Machine Learning Engineer / AI Engineer
Skills: Python, PyTorch, Librosa, NumPy, Pandas, CNN, ResNet, VGG, MFCC, STFT
Education: M.S. Data Science, City University
Projects:
Audio Classification Benchmark
- Built PyTorch CNN and ResNet models using MFCC and STFT features on an environmental sound dataset.
- Reached 95% validation accuracy on 300 evaluation clips.
ASR Error Analysis Tool
- Used Librosa and Pandas to inspect transcription failures and dataset labeling issues.
Experience:
Research Assistant, Audio Intelligence Lab
- Ran dataset experiments and compared VGG and CNN baselines for speech tasks.
Highlights: Improved model accuracy and documented dataset quality issues.
""",
        target_roles=["Machine Learning Engineer", "AI Engineer"],
        expected_focus=["pytorch", "audio", "asr", "accuracy"],
        expected_skills=["PyTorch", "Librosa", "MFCC", "STFT", "CNN"],
        expected_sections=["projects", "work_experiences", "education", "highlights"],
        should_have_warnings=False,
        expected_confidence_without_llm="strong",
    ),
    ProfileReviewQualityCase(
        case_id="finance_fa_analysis",
        title="Finance / FA analysis resume",
        resume_text="""
Zhao Xin
Target Roles: Business Analyst / Investment Analyst
Skills: Excel, PowerPoint, Wind, CRM, market research, competitor analysis
Education: B.A. Finance, CUHKSZ
Experience:
FA Intern, Horizon Capital
- Used Wind and Qichacha for industry research, peer mapping, and deal memo support.
- Prepared CRM updates, meeting notes, and competitor analysis summaries.
Projects:
New Energy Sector Research
- Analyzed market size, business models, and competitive landscape for listed companies.
Highlights: Completed investor meeting notes and delivered structured research reports.
""",
        target_roles=["Business Analyst", "Investment Analyst"],
        expected_focus=["research", "industry", "competitive", "crm"],
        expected_skills=["Wind", "CRM", "market research", "competitor analysis"],
        expected_sections=["projects", "work_experiences", "education", "highlights"],
        should_have_warnings=False,
        expected_confidence_without_llm="medium",
    ),
    ProfileReviewQualityCase(
        case_id="mixed_language_resume",
        title="Mixed Chinese and English resume",
        resume_text="""
Liu Jia
Target Roles: Backend Engineer / Research Engineer
Education
B.S. Software Engineering, Xidian University
Experience
Research Assistant, Vision Lab
- Built experiment tooling and dataset scripts in Python.
项目经历
图像检索系统：使用 FastAPI、SQLite 和 Streamlit 搭建 demo，负责接口设计与测试。
技能
Python, FastAPI, SQLite, Streamlit, Git
亮点
完成 120 tests，并整理 evaluation notes。
""",
        target_roles=["Backend Engineer", "Research Engineer"],
        expected_focus=["mixed-language", "research", "backend"],
        expected_skills=["Python", "FastAPI", "SQLite", "Streamlit"],
        expected_sections=["projects", "work_experiences", "education", "highlights"],
        should_have_warnings=False,
        expected_confidence_without_llm="medium",
    ),
    ProfileReviewQualityCase(
        case_id="weak_resume",
        title="Weak sparse resume",
        resume_text="""
I know Python and want an AI job.
""",
        target_roles=[],
        expected_focus=["warnings", "missing info"],
        expected_skills=["Python"],
        expected_sections=["projects"],
        should_have_warnings=True,
        expected_confidence_without_llm="weak",
    ),
]
