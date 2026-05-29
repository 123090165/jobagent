from __future__ import annotations

from app.services.mock_pipeline import run_mock_pipeline


def analyze_resume_and_jd(resume_text: str, jd_text: str):
    """Run the current v0.1 mock analysis pipeline."""
    return run_mock_pipeline(resume_text=resume_text, jd_text=jd_text)


def main() -> None:
    sample_resume = "Python 后端开发，做过 FastAPI、Pydantic、Streamlit 项目。"
    sample_jd = "招聘 Python 后端工程师，要求 FastAPI、SQL、REST API，有 LLM 应用经验优先。"
    result = analyze_resume_and_jd(sample_resume, sample_jd)
    print(result.markdown_report)


if __name__ == "__main__":
    main()
