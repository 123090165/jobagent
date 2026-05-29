from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.services.mock_pipeline import run_mock_pipeline
from app.services.llm_service import is_llm_configured


SAMPLE_RESUME = """张三
计算机科学与技术 本科
技能：Python、FastAPI、Pydantic、Streamlit、SQL、Docker、Git、LLM
项目：JobAgent 求职分析工具，使用 Streamlit 构建页面，使用 Pydantic 定义结构化输出，模拟简历和 JD 匹配流程。
负责：设计 mock pipeline、生成 Markdown 报告、补充 pytest 测试。
"""

SAMPLE_JD = """AI 应用开发工程师
职责：负责 LLM 应用后端开发，设计 REST API，参与 Agent 工作流和 RAG 能力建设。
要求：熟悉 Python、FastAPI、SQL、Pydantic，有良好的工程实践和 Git 使用经验。
加分：了解 LangGraph、RAG、OpenAI API、Docker，有 Streamlit Demo 开发经验优先。
"""


def main() -> None:
    st.set_page_config(page_title="JobAgent Mock MVP", page_icon="JA", layout="wide")

    st.title("JobAgent")
    st.caption("v0.1 Mock MVP")

    with st.sidebar:
        st.subheader("当前阶段")
        st.write("先跑通简历 + JD 到报告的最小闭环。")
        st.write("本轮只允许可选接入 JDAnalysisAgent，不接数据库、LangGraph、自动投递。")
        use_llm_jd = st.checkbox(
            "启用 LLM JD 分析",
            value=False,
            help="需要先配置 JOBAGENT_LLM_API_KEY；失败时会自动回退到 mock JD 分析。",
        )
        if use_llm_jd and not is_llm_configured():
            st.info("当前未配置 LLM API key，本次会自动回退到 mock JD 分析。")

    left, right = st.columns(2)
    with left:
        resume_text = st.text_area("简历文本", value=SAMPLE_RESUME, height=320)
    with right:
        jd_text = st.text_area("目标岗位 JD", value=SAMPLE_JD, height=320)

    if st.button("生成分析报告", type="primary", use_container_width=True):
        if not resume_text.strip() or not jd_text.strip():
            st.warning("请先填写简历文本和 JD 文本。")
            return

        try:
            result = run_mock_pipeline(
                resume_text=resume_text,
                jd_text=jd_text,
                use_llm_jd=use_llm_jd,
            )
        except ValueError as exc:
            st.error(str(exc))
            return

        match = result.match_report
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("总匹配分", f"{match.overall_score:.1f}")
        col2.metric("技能分", f"{match.skill_score:.1f}")
        col3.metric("项目分", f"{match.project_score:.1f}")
        col4.metric("关键词覆盖", f"{match.keyword_coverage:.1f}%")

        tab_report, tab_structured, tab_interview = st.tabs(["报告", "结构化结果", "项目追问"])

        with tab_report:
            st.markdown(result.markdown_report)
            st.download_button(
                label="下载 Markdown 报告",
                data=result.markdown_report,
                file_name="jobagent_report.md",
                mime="text/markdown",
            )

        with tab_structured:
            st.subheader("简历解析")
            st.json(result.resume_profile.model_dump())
            st.subheader("JD 分析")
            st.json(result.job_analysis.model_dump())
            st.subheader("匹配报告")
            st.json(result.match_report.model_dump())

        with tab_interview:
            st.subheader("面试追问")
            for group_name, questions in [
                ("基础问题", result.project_challenge_report.basic_questions),
                ("技术细节", result.project_challenge_report.technical_deep_dive_questions),
                ("架构问题", result.project_challenge_report.architecture_questions),
                ("取舍问题", result.project_challenge_report.tradeoff_questions),
            ]:
                st.markdown(f"### {group_name}")
                for item in questions:
                    st.markdown(f"- **{item.question}**")
                    st.caption(f"考察点：{item.evaluates}")


if __name__ == "__main__":
    main()
