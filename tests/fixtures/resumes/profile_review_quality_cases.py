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
    ProfileReviewQualityCase(
        case_id="anker_ai_health_algorithm",
        title="Realistic AI health algorithm internship resume",
        resume_text="""
Synthetic Resume for Product Testing Only
Name: Test Candidate
Location: Shenzhen, China
Target Role: AI Health Algorithm Intern / Physiological Signal Processing Intern / Biomedical AI Intern

SUMMARY
Undergraduate student in information engineering and computer science with project experience in physiological signal processing, AI health analytics, and deep learning model development. Familiar with PPG, ECG, and motion-sensor time-series data, including data cleaning, annotation, preprocessing, denoising, feature extraction, model training, evaluation, and technical documentation.

Interested in applying AI algorithms to wearable health monitoring, blood oxygen estimation, heart rate analysis, blood pressure trend analysis, multimodal biosignal modeling, and real-time health data analysis. Available for a stable internship in Shenzhen.

EDUCATION
B.Eng. in Information Engineering / Computer Science
University in Shenzhen
Expected Graduation: 2027

Relevant Coursework:
Digital Signal Processing, Machine Learning, Deep Learning, Biomedical Signal Processing, Probability and Statistics, Data Structures and Algorithms, Python Programming.

TECHNICAL SKILLS
Programming: Python, MATLAB, C/C++
Deep Learning: PyTorch, TensorFlow, CNN, RNN, model fine-tuning, data augmentation, supervised learning, time-series classification
Signal Processing: PPG signal processing, ECG signal processing, ACC motion signal analysis, filtering, denoising, signal segmentation, noise analysis, feature extraction, time-domain and frequency-domain analysis
Data Processing: data cleaning, data annotation, preprocessing pipeline design, missing value handling, statistical analysis, visualization
Tools: NumPy, Pandas, SciPy, scikit-learn, Matplotlib, Jupyter Notebook, Git

PROJECT EXPERIENCE
Physiological Signal Processing for Heart Rate and Blood Oxygen Estimation

- Processed PPG and ECG signals for wearable health monitoring scenarios.
- Completed signal preprocessing, noise filtering, data cleaning, and signal segmentation.
- Extracted time-domain and frequency-domain features from physiological signals.
- Analyzed how motion artifacts and sensor noise affect heart rate and blood oxygen estimation.
- Built Python scripts for signal preprocessing, quality inspection, and visualization using NumPy, Pandas, SciPy, and Matplotlib.

Deep Learning Model for Multimodal Biosignal Classification

- Built a PyTorch-based deep learning pipeline for multimodal physiological signal classification.
- Used PPG, ECG, and ACC-style time-series features to train and evaluate neural network models.
- Applied data augmentation and model fine-tuning to improve robustness under noisy signal conditions.
- Compared model performance under different preprocessing and feature extraction strategies.
- Evaluated model results with accuracy, confusion matrix, and error case analysis.

AI Health Analytics Mini Prototype

- Designed a small AI health analysis prototype for real-time physiological data monitoring.
- Implemented data cleaning, abnormal signal detection, missing value handling, and simple health trend analysis logic.
- Explored how machine learning models can support health monitoring and early warning scenarios.
- Collaborated with peers to define data format, preprocessing steps, and evaluation criteria.

SELECTED TECHNICAL EXPERIENCE
Data Cleaning and Annotation

- Cleaned noisy physiological and time-series data.
- Removed invalid segments and handled missing or abnormal values.
- Prepared structured datasets for model training and evaluation.

Model Training and Optimization

- Trained deep learning models using PyTorch and TensorFlow.
- Practiced model fine-tuning, data augmentation, and hyperparameter adjustment.
- Compared performance across preprocessing methods and model structures.

INTERNSHIP AVAILABILITY
Available for a stable internship period.
Preferred location: Shenzhen.
Open to roles related to AI health algorithms, physiological signal processing, wearable device algorithms, biomedical AI, data preprocessing, and deep learning model development.

ROLE MATCHING KEYWORDS
AI health algorithm, physiological signal processing, PPG, ECG, ACC, blood oxygen, heart rate, blood pressure, deep learning, PyTorch, TensorFlow, data cleaning, data annotation, data preprocessing, data augmentation, model fine-tuning, feature engineering, wearable health monitoring, multimodal biosignal analysis, health data analytics, technical documentation, cross-functional collaboration.
""",
        target_roles=[
            "AI Health Algorithm Intern",
            "Physiological Signal Processing Intern",
            "Biomedical AI Intern",
        ],
        expected_focus=[
            "physiological signal processing",
            "wearable health monitoring",
            "PPG",
            "ECG",
            "ACC",
            "blood oxygen",
            "heart rate",
            "deep learning",
            "time-series classification",
            "data cleaning",
            "feature extraction",
            "Shenzhen",
        ],
        expected_skills=[
            "Python",
            "MATLAB",
            "C/C++",
            "PyTorch",
            "TensorFlow",
            "CNN",
            "RNN",
            "PPG",
            "ECG",
            "ACC",
            "data cleaning",
            "data annotation",
            "feature extraction",
            "signal segmentation",
            "denoising",
            "NumPy",
            "Pandas",
            "SciPy",
            "scikit-learn",
            "Matplotlib",
            "Git",
        ],
        expected_sections=["projects", "education", "highlights"],
        should_have_warnings=False,
        expected_confidence_without_llm="strong",
    ),
    ProfileReviewQualityCase(
        case_id="realistic_noisy_chinese_resume",
        title="Realistic noisy Chinese resume without clean headings",
        resume_text="""
我主要想找 AI Agent / 后端 / 数据分析 相关实习。学校是电子信息方向本科，比较希望深圳或杭州。
之前做过一个求职分析工具，用 FastAPI、Streamlit、SQLite 做过接口和页面，也写过一些测试。这个项目主要是把简历解析、岗位分析、匹配报告和可视化页面串起来，我负责后端接口、前端展示和测试数据整理。
还做过课程里的音频分类实验，用 PyTorch、Librosa、MFCC、STFT 做特征和模型训练，比过 CNN 和 VGG 的效果，验证准确率最高大概 75%。另外也写过一些 Python 数据处理脚本，会用 Pandas、NumPy 和 Git。
""",
        target_roles=["AI Agent Intern", "Backend Engineer Intern", "Data Analyst Intern"],
        expected_focus=["ai agent", "backend", "data analysis", "Shenzhen", "Hangzhou"],
        expected_skills=[
            "Python",
            "FastAPI",
            "Streamlit",
            "SQLite",
            "PyTorch",
            "Librosa",
            "MFCC",
            "STFT",
            "CNN",
            "Pandas",
            "NumPy",
            "Git",
        ],
        expected_sections=["projects", "education"],
        should_have_warnings=True,
        expected_confidence_without_llm="medium",
    ),
    ProfileReviewQualityCase(
        case_id="realistic_business_resume_unstructured",
        title="Realistic unstructured business / FA resume",
        resume_text="""
我在某 FA 团队支持过新材料项目，主要用 Wind、企查查、Excel、PowerPoint 收集公司和行业信息，整理竞争格局、融资历史和潜在合作方。
工作内容包括维护 CRM 项目跟进表，记录客户需求，写会议纪要，跟进投资人反馈，识别高意向潜在客户。也参与过新材料行业研究，整理市场空间、商业模式、产业链上下游和竞品情况。
目标方向是 Business Analyst、Investment Analyst、FA Intern 或者行业研究相关实习，希望能在深圳、香港或杭州做商业分析、投资分析、行业研究相关工作。
""",
        target_roles=["Business Analyst", "Investment Analyst", "FA Intern"],
        expected_focus=["industry research", "competitive landscape", "CRM", "deal memo"],
        expected_skills=[
            "Wind",
            "企查查",
            "Excel",
            "PowerPoint",
            "CRM",
            "industry research",
            "competitor analysis",
            "meeting notes",
        ],
        expected_sections=["work_experiences", "highlights"],
        should_have_warnings=True,
        expected_confidence_without_llm="medium",
    ),
]
