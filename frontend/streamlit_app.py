from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.services.llm_service import is_llm_configured
from app.services.application_service import list_applications, save_application
from app.services.resume_version_service import (
    list_saved_resume_versions,
    load_resume_version,
    save_resume_version,
)
from app.services.storage_service import (
    list_saved_analysis_records,
    list_saved_job_postings,
    load_analysis_record,
    load_job_posting,
    save_final_report,
)
from app.workflows.job_analysis_workflow import run_job_analysis_workflow


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

    tab_analyze, tab_history, tab_jobs, tab_versions, tab_tracker = st.tabs(
        ["生成报告", "历史记录", "岗位库", "简历版本", "投递跟进"]
    )

    with tab_analyze:
        render_analysis_tab(use_llm_jd=use_llm_jd, save_result=save_result)

    with tab_history:
        render_history_tab()

    with tab_jobs:
        render_jobs_tab()

    with tab_versions:
        render_resume_versions_tab()

    with tab_tracker:
        render_tracker_tab()


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
            workflow_result = run_job_analysis_workflow(
                resume_text=resume_text,
                jd_text=jd_text,
                use_llm_jd=use_llm_jd,
            )
        except ValueError as exc:
            st.error(str(exc))
            return

        result = workflow_result.final_report
        workflow_steps = [step.model_dump() for step in workflow_result.state.steps]
        record_id: int | None = None
        if save_result:
            record_id = save_final_report(result, workflow_steps=workflow_steps)
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
            st.subheader("执行轨迹")
            st.json(workflow_steps)
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

    detail_report, detail_trace, detail_json = st.tabs(["报告", "执行轨迹", "结构化详情"])
    with detail_report:
        st.markdown(record["markdown_report"])
    with detail_trace:
        workflow_steps = record.get("workflow_steps") or []
        if not workflow_steps:
            st.info("这条历史记录没有保存 workflow trace，可能来自旧版本。")
        else:
            st.dataframe(workflow_steps, hide_index=True, use_container_width=True)
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


def render_resume_versions_tab() -> None:
    st.subheader("简历版本")
    jobs = list_saved_job_postings(limit=100)

    with st.form("resume_version_form"):
        label = st.text_input("版本标签", placeholder="例如：v1-fastapi-backend")
        selected_job_id = st.selectbox(
            "目标岗位",
            options=[None] + [job["id"] for job in jobs],
            format_func=lambda job_id: _format_optional_job_option(job_id, jobs),
        )
        base_resume_text = st.text_area("原始简历文本", value=SAMPLE_RESUME, height=220)
        tailored_resume_text = st.text_area(
            "定制后简历文本",
            placeholder="可粘贴针对目标 JD 调整后的版本；不要新增未真实发生的经历。",
            height=220,
        )
        notes = st.text_area("版本备注", placeholder="记录这个版本面向的岗位、修改重点和待补充信息。")
        submitted = st.form_submit_button("保存简历版本", type="primary", use_container_width=True)

    if submitted:
        if not label.strip() or not base_resume_text.strip():
            st.warning("请填写版本标签和原始简历文本。")
        else:
            version = save_resume_version(
                label=label.strip(),
                base_resume_text=base_resume_text.strip(),
                tailored_resume_text=tailored_resume_text.strip() or None,
                target_job_id=int(selected_job_id) if selected_job_id is not None else None,
                notes=notes.strip() or None,
            )
            if version is None:
                st.error("关联岗位不存在，无法保存简历版本。")
            else:
                st.success(f"已保存简历版本：#{version['id']}")

    st.markdown("### 已保存版本")
    keyword, limit = render_search_controls("resume_versions")
    versions = list_saved_resume_versions(keyword=keyword or None, limit=limit)
    if not versions:
        st.info("还没有保存的简历版本。")
        return

    st.dataframe(versions, hide_index=True, use_container_width=True)
    selected_version_id = st.selectbox(
        "查看版本详情",
        options=[version["id"] for version in versions],
        format_func=lambda version_id: _format_resume_version_option(version_id, versions),
    )
    version = load_resume_version(int(selected_version_id))
    if version is None:
        st.warning("简历版本不存在或已被删除。")
        return

    col1, col2, col3 = st.columns(3)
    col1.metric("版本", version["label"])
    col2.metric("目标岗位", version.get("target_job_title") or "未关联")
    col3.metric("创建时间", version["created_at"])

    base_tab, tailored_tab, metadata_tab = st.tabs(["原始简历", "定制版本", "版本信息"])
    with base_tab:
        st.text_area("原始简历", value=version["base_resume_text"], height=300, disabled=True)
    with tailored_tab:
        st.text_area(
            "定制版本",
            value=version.get("tailored_resume_text") or "未填写定制后文本。",
            height=300,
            disabled=True,
        )
    with metadata_tab:
        st.json(version)


def render_tracker_tab() -> None:
    st.subheader("投递跟进")
    jobs = list_saved_job_postings(limit=100)
    if not jobs:
        st.info("还没有岗位。请先保存一次分析，岗位会出现在这里。")
        return

    with st.form("application_form"):
        selected_job_id = st.selectbox(
            "选择岗位",
            options=[job["id"] for job in jobs],
            format_func=lambda job_id: _format_job_option(job_id, jobs),
        )
        status = st.selectbox(
            "状态",
            options=["interested", "applied", "interviewing", "rejected", "offer", "archived"],
            format_func=_format_status_label,
        )
        resume_versions = list_saved_resume_versions(limit=100)
        selected_resume_version_id = st.selectbox(
            "关联简历版本",
            options=[None] + [version["id"] for version in resume_versions],
            format_func=lambda version_id: _format_optional_resume_version_option(
                version_id,
                resume_versions,
            ),
        )
        if selected_resume_version_id is None:
            resume_version_label = st.text_input("简历版本标签", placeholder="例如：v1-fastapi-backend")
        else:
            resume_version_label = None
        next_action = st.text_input("下一步行动", placeholder="例如：今晚定制简历并投递")
        notes = st.text_area("备注", placeholder="记录岗位偏好、投递渠道、面试反馈等")
        submitted = st.form_submit_button("保存跟进状态", type="primary", use_container_width=True)

    if submitted:
        manual_resume_version_label = (resume_version_label.strip() or None) if resume_version_label else None
        selected_version_id = (
            int(selected_resume_version_id)
            if selected_resume_version_id is not None
            else None
        )
        record = save_application(
            job_id=int(selected_job_id),
            status=status,
            notes=notes.strip() or None,
            next_action=next_action.strip() or None,
            resume_version_id=selected_version_id,
            resume_version_label=manual_resume_version_label,
        )
        if record is None:
            st.error("岗位不存在，无法保存跟进记录。")
        else:
            st.success(f"已保存跟进记录：#{record['id']}")

    st.markdown("### 当前跟进列表")
    status_filter = st.selectbox(
        "按状态筛选",
        options=["全部", "interested", "applied", "interviewing", "rejected", "offer", "archived"],
        format_func=lambda value: "全部" if value == "全部" else _format_status_label(value),
    )
    applications = list_applications(
        status=None if status_filter == "全部" else status_filter,
        limit=100,
    )
    if not applications:
        st.info("还没有跟进记录。")
        return
    st.dataframe(applications, hide_index=True, use_container_width=True)


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


def _format_optional_job_option(job_id: int | None, jobs: list[dict]) -> str:
    if job_id is None:
        return "不关联岗位"
    return _format_job_option(job_id, jobs)


def _format_resume_version_option(version_id: int, versions: list[dict]) -> str:
    version = next((item for item in versions if item["id"] == version_id), None)
    if not version:
        return str(version_id)
    target = version.get("target_job_title") or "未关联岗位"
    return f"#{version_id} | {version['label']} | {target}"


def _format_optional_resume_version_option(version_id: int | None, versions: list[dict]) -> str:
    if version_id is None:
        return "不关联版本，手动填写标签"
    return _format_resume_version_option(version_id, versions)


def _format_status_label(status: str) -> str:
    labels = {
        "interested": "感兴趣",
        "applied": "已投递",
        "interviewing": "面试中",
        "rejected": "已拒绝",
        "offer": "Offer",
        "archived": "归档",
    }
    return labels.get(status, status)


if __name__ == "__main__":
    main()
