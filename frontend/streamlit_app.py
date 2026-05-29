from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.services.mock_pipeline import run_mock_pipeline
from app.services.llm_service import is_llm_configured
from app.services.storage_service import (
    list_saved_analysis_records,
    list_saved_job_postings,
    load_analysis_record,
    load_job_posting,
    save_final_report,
)


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
    st.set_page_config(page_title="JobAgent", page_icon="JA", layout="wide")

    st.title("JobAgent")
    st.caption("Resume-JD matching, optimization, interview prep, and job history")

    with st.sidebar:
        st.subheader("当前阶段")
        st.write("当前支持分析报告、历史记录和本地岗位库。")
        st.write("暂不做 URL 抓取、自动投递、登录、验证码。")
        use_llm_jd = st.checkbox(
            "启用 LLM JD 分析",
            value=False,
            help="需要先配置 JOBAGENT_LLM_API_KEY；失败时会自动回退到 mock JD 分析。",
        )
        save_result = st.checkbox(
            "保存本次分析",
            value=True,
            help="保存到本地 SQLite，之后可在历史记录和岗位库中查看。",
        )
        if use_llm_jd and not is_llm_configured():
            st.info("当前未配置 LLM API key，本次会自动回退到 mock JD 分析。")

    tab_analyze, tab_history, tab_jobs = st.tabs(["生成报告", "历史记录", "岗位库"])

    with tab_analyze:
        render_analysis_tab(use_llm_jd=use_llm_jd, save_result=save_result)

    with tab_history:
        render_history_tab()

    with tab_jobs:
        render_jobs_tab()


def render_analysis_tab(*, use_llm_jd: bool, save_result: bool) -> None:
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

        record_id: int | None = None
        if save_result:
            record_id = save_final_report(result)
            st.success(f"已保存分析记录：#{record_id}")

        match = result.match_report
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("总匹配分", f"{match.overall_score:.1f}")
        col2.metric("技能分", f"{match.skill_score:.1f}")
        col3.metric("项目分", f"{match.project_score:.1f}")
        col4.metric("关键词覆盖", f"{match.keyword_coverage:.1f}%")

        tab_report, tab_structured, tab_interview = st.tabs(["报告", "结构化结果", "项目追问"])

        with tab_report:
            if record_id is not None:
                st.caption(f"记录 ID：{record_id}")
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


def render_history_tab() -> None:
    st.subheader("历史分析记录")
    keyword, limit = render_search_controls("history")
    records = list_saved_analysis_records(keyword=keyword or None, limit=limit)

    if not records:
        st.info("还没有保存的分析记录。请先在“生成报告”里勾选保存并生成一次报告。")
        return

    st.dataframe(records, hide_index=True, use_container_width=True)
    selected_id = st.selectbox(
        "查看记录详情",
        options=[record["id"] for record in records],
        format_func=lambda record_id: _format_record_option(record_id, records),
    )
    record = load_analysis_record(int(selected_id))
    if record is None:
        st.warning("记录不存在或已被删除。")
        return

    match = record["match_report"]
    col1, col2, col3 = st.columns(3)
    col1.metric("总匹配分", f"{match['overall_score']:.1f}")
    col2.metric("岗位", record["job_analysis"].get("job_title") or "未识别")
    col3.metric("创建时间", record["created_at"])

    detail_report, detail_json = st.tabs(["报告", "结构化详情"])
    with detail_report:
        st.markdown(record["markdown_report"])
    with detail_json:
        st.json(record)


def render_jobs_tab() -> None:
    st.subheader("岗位库")
    keyword, limit = render_search_controls("jobs")
    jobs = list_saved_job_postings(keyword=keyword or None, limit=limit)

    if not jobs:
        st.info("还没有保存的岗位 JD。保存一次分析后，岗位会出现在这里。")
        return

    st.dataframe(jobs, hide_index=True, use_container_width=True)
    selected_id = st.selectbox(
        "查看岗位详情",
        options=[job["id"] for job in jobs],
        format_func=lambda job_id: _format_job_option(job_id, jobs),
    )
    job = load_job_posting(int(selected_id))
    if job is None:
        st.warning("岗位不存在或已被删除。")
        return

    job_analysis = job["job_analysis"]
    col1, col2, col3 = st.columns(3)
    col1.metric("分析次数", job["analysis_count"])
    col2.metric("岗位", job_analysis.get("job_title") or "未识别")
    col3.metric("创建时间", job["created_at"])

    detail_jd, detail_analysis = st.tabs(["原始 JD", "结构化分析"])
    with detail_jd:
        st.text_area("原始 JD", value=job["raw_jd"], height=300, disabled=True)
    with detail_analysis:
        st.json(job_analysis)


def render_search_controls(key_prefix: str) -> tuple[str, int]:
    left, right = st.columns([3, 1])
    with left:
        keyword = st.text_input("关键词搜索", value="", key=f"{key_prefix}_keyword")
    with right:
        limit = st.number_input("最多显示", min_value=1, max_value=100, value=20, key=f"{key_prefix}_limit")
    return keyword.strip(), int(limit)


def _format_record_option(record_id: int, records: list[dict]) -> str:
    record = next((item for item in records if item["id"] == record_id), None)
    if not record:
        return str(record_id)
    title = record.get("job_title") or "未识别岗位"
    score = record.get("overall_score", 0)
    return f"#{record_id} | {title} | {score:.1f}"


def _format_job_option(job_id: int, jobs: list[dict]) -> str:
    job = next((item for item in jobs if item["id"] == job_id), None)
    if not job:
        return str(job_id)
    title = job.get("job_title") or "未识别岗位"
    count = job.get("analysis_count", 0)
    return f"#{job_id} | {title} | {count} 次分析"


if __name__ == "__main__":
    main()
