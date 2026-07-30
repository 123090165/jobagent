"""维护确定性简历解析共用的技能词表和规范化别名。"""

from __future__ import annotations

import re

KNOWN_RESUME_SKILLS = [
    "Python",
    "C/C++",
    "C++",
    "C",
    "R",
    "Go",
    "FastAPI",
    "Flask",
    "Django",
    "Streamlit",
    "Pydantic",
    "LangGraph",
    "LangChain",
    "OpenAI API",
    "OpenAI",
    "LLM",
    "RAG",
    "MCP",
    "Ollama",
    "SQL",
    "SQLite",
    "PostgreSQL",
    "Redis",
    "Docker",
    "Git",
    "REST API",
    "pytest",
    "React",
    "TypeScript",
    "JavaScript",
    "HTML",
    "CSS",
    "Pandas",
    "NumPy",
    "PyTorch",
    "TensorFlow",
    "Transformers",
    "HuggingFace",
    "scikit-learn",
    "Librosa",
    "OpenCV",
    "CUDA",
    "Deep Learning",
    "Machine Learning",
    "audio classification",
    "ASR",
    "MFCC",
    "STFT",
    "CNN",
    "RNN",
    "ResNet",
    "VGG",
    "validation accuracy",
    "confusion matrix",
    "error analysis",
    "dataset preprocessing",
    "time-series classification",
    "STM32",
    "USART",
    "UART",
    "GPIO",
    "FreeRTOS",
    "RTOS",
    "I2C",
    "SPI",
    "CAN",
    "CAN bus",
    "DMA",
    "ADC",
    "PWM",
    "Keil",
    "CubeMX",
    "MATLAB",
    "PPG",
    "ECG",
    "ACC",
    "physiological signal processing",
    "biosignal",
    "multimodal biosignal",
    "wearable health monitoring",
    "blood oxygen",
    "heart rate",
    "blood pressure",
    "signal segmentation",
    "denoising",
    "noise analysis",
    "feature extraction",
    "time-domain analysis",
    "frequency-domain analysis",
    "health analytics",
    "data cleaning",
    "data annotation",
    "industry research",
    "market research",
    "competitor analysis",
    "competitive landscape",
    "deal memo",
    "meeting notes",
    "peer mapping",
    "financing history",
    "business model",
    "market size",
    "investment analysis",
    "FA",
    "Wind",
    "企查查",
    "Excel",
    "PowerPoint",
    "CRM",
    "机器学习",
    "数据分析",
]

_SHORT_TOKEN_CONTEXT_PATTERNS: dict[str, list[re.Pattern[str]]] = {
    "C": [
        re.compile(r"\bc/c\+\+\b", re.IGNORECASE),
        re.compile(r"\bc language\b", re.IGNORECASE),
        re.compile(
            r"\b(?:skills?|technical skills|programming|languages?)\b[^\n]{0,120}\bc\b",
            re.IGNORECASE,
        ),
    ],
    "R": [
        re.compile(r"\bR language\b", re.IGNORECASE),
        re.compile(
            r"\b(?:skills?|technical skills|programming|languages?)\b[^\n]{0,120}\br\b",
            re.IGNORECASE,
        ),
    ],
    "Go": [
        re.compile(r"\bGo language\b", re.IGNORECASE),
        re.compile(
            r"\b(?:skills?|technical skills|programming|languages?)\b[^\n]{0,120}\bgo\b",
            re.IGNORECASE,
        ),
    ],
    "CAN": [
        re.compile(r"\bcan bus\b", re.IGNORECASE),
        re.compile(r"\bcan protocol\b", re.IGNORECASE),
        re.compile(r"\bvehicle can\b", re.IGNORECASE),
        re.compile(
            r"\b(?:skills?|technical skills|embedded|protocols?)\b[^\n]{0,120}\bcan\b",
            re.IGNORECASE,
        ),
    ],
}


def canonicalize_resume_skill_token(token: str) -> str | None:
    clean_token = token.strip()
    for skill in KNOWN_RESUME_SKILLS:
        if clean_token.lower() == skill.lower():
            return skill
    return None


def extract_resume_skills(text: str) -> list[str]:
    if not text:
        return []

    found: list[str] = []
    for skill in KNOWN_RESUME_SKILLS:
        if _skill_in_text(skill, text):
            found.append(skill)
    return _dedupe(found)


def _skill_in_text(skill: str, text: str) -> bool:
    if not text:
        return False
    if skill in _SHORT_TOKEN_CONTEXT_PATTERNS:
        return any(pattern.search(text) for pattern in _SHORT_TOKEN_CONTEXT_PATTERNS[skill])
    if re.search(r"[\u4e00-\u9fff]", skill):
        return skill in text
    escaped = re.escape(skill)
    return bool(
        re.search(
            rf"(?<![A-Za-z0-9+#./-]){escaped}(?![A-Za-z0-9+#./-])",
            text,
            re.IGNORECASE,
        )
    )


def _dedupe(items: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        normalized = item.strip()
        key = normalized.lower()
        if not normalized or key in seen:
            continue
        seen.add(key)
        result.append(normalized)
    return result
