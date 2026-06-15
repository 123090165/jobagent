from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import streamlit as st

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.services.jd_url_service import JDUrlImportError, import_jd_from_url
from app.services.llm_provider import DEFAULT_LLM_PROVIDER, resolve_llm_provider
from app.services.batch_brief_service import build_brief_from_search
from app.services.application_service import list_applications, save_application
from app.services.errors import JobAgentError
from app.services.search_query_service import generate_search_queries_from_resume
from app.services.resume_version_service import (
    list_saved_resume_versions,
    load_resume_version,
    save_resume_version,
)
from app.services.resume_file_service import ResumeFileParseError, extract_text_from_resume_file
from app.services.storage_service import (
    list_saved_analysis_records,
    list_saved_job_postings,
    load_analysis_record,
    load_job_posting,
    save_final_report,
)
from app.schemas.brief import JobBriefReport
from app.schemas.job_import_candidate import JobImportCandidate
from app.workflows.job_analysis_workflow import run_job_analysis_workflow
from app.workflows.langgraph_job_analysis_workflow import run_langgraph_job_analysis_workflow
from frontend.profile_review_flow import (
    render_profile_review_flow_tab,
    request_job_brief_from_api,
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

DEFAULT_API_BASE_URL = os.getenv("JOBAGENT_API_BASE_URL", "http://127.0.0.1:8000")
DEFAULT_API_TIMEOUT_SECONDS = 30
SCORING_QUALITY_LABELS = {
    "full_jd": "完整 JD",
    "partial_jd": "部分 JD",
    "external_link_only": "外链详情",
    "snippet_only": "摘要评估",
    "invalid": "无效 JD",
}


def main() -> None:
    st.set_page_config(page_title="JobAgent", page_icon="JA", layout="wide")

    st.title("JobAgent")
    st.caption("Profile creation first, then JD search and later matching.")

    with st.sidebar:
        st.subheader("Current Stage")
        st.write("Build the candidate profile first. JD search and later analysis come after profile confirmation.")
        provider_options = ["ollama", "deepseek"]
        current_provider = st.selectbox(
            "Model provider",
            options=provider_options,
            index=provider_options.index(
                st.session_state.get("profile_flow_selected_provider", DEFAULT_LLM_PROVIDER)
                if st.session_state.get("profile_flow_selected_provider", DEFAULT_LLM_PROVIDER) in provider_options
                else DEFAULT_LLM_PROVIDER
            ),
            key="global_model_provider",
        )
        provider_resolution = resolve_llm_provider(current_provider)
        st.caption(f"provider: {provider_resolution.provider}")
        st.caption(f"model: {provider_resolution.model or 'N/A'}")
        st.caption(f"base_url: {provider_resolution.base_url or 'N/A'}")
        st.caption(f"configured: {'yes' if provider_resolution.configured else 'no'}")
        st.caption(
            f"reason: {provider_resolution.reason or 'provider ready or uses deterministic fallback'}"
        )
        st.caption("mock is internal fallback only and is not shown as a primary user option.")
    use_langgraph_workflow = False
    save_result = True

    (
        tab_profile_flow,
        tab_brief,
        tab_analyze,
        tab_history,
        tab_jobs,
        tab_versions,
        tab_tracker,
    ) = st.tabs(
        ["Profile Setup", "岗位搜索", "生成报告", "历史记录", "岗位库", "简历版本", "投递跟进"]
    )

    with tab_profile_flow:
        render_profile_review_flow_tab(
            sample_resume=SAMPLE_RESUME,
            selected_provider=current_provider,
        )

    with tab_brief:
        st.info("Recommended: complete Profile Setup first, then continue to later search and brief stages.")
        render_job_brief_tab(use_llm_jd=False)

    with tab_analyze:
        st.info("Recommended: complete Profile Setup first, then continue to downstream analysis.")
        render_analysis_tab(
            use_llm_jd=False,
            use_llm_resume_optimize=False,
            use_llm_project_challenge=False,
            use_langgraph_workflow=use_langgraph_workflow,
            save_result=save_result,
        )

    with tab_history:
        st.info("Recommended: complete Profile Setup first, then review saved history here.")
        render_history_tab()

    with tab_jobs:
        st.info("Recommended: complete Profile Setup first, then browse later-stage saved jobs here.")
        render_jobs_tab()

    with tab_versions:
        st.info("Recommended: complete Profile Setup first, then work with resume versions here.")
        render_resume_versions_tab()

    with tab_tracker:
        st.info("Recommended: complete Profile Setup first, then use tracker features here.")
        render_tracker_tab()


def request_brief_run_from_api(
    *,
    resume_text: str,
    query: str,
    provider: str,
    limit: int,
    use_llm_jd: bool,
    api_base_url: str = DEFAULT_API_BASE_URL,
    timeout_seconds: int = DEFAULT_API_TIMEOUT_SECONDS,
) -> tuple[str, JobBriefReport]:
    payload = json.dumps(
        {
            "resume_text": resume_text,
            "query": query,
            "provider": provider,
            "limit": limit,
            "use_llm_jd": use_llm_jd,
        }
    ).encode("utf-8")
    request = Request(
        f"{api_base_url.rstrip('/')}/brief/runs/from-search",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            response_body = response.read().decode("utf-8")
    except HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        error_payload = _load_json_payload(error_body)
        raise JobAgentError(
            str(error_payload.get("detail", f"/brief/runs/from-search failed with status {exc.code}")),
            str(error_payload.get("error_code", "brief_api_request_failed")),
        ) from exc
    except URLError as exc:
        raise JobAgentError(
            "无法连接 FastAPI 后端，请先启动 .venv\\Scripts\\python.exe -m uvicorn app.main:app --reload",
            "brief_api_unavailable",
        ) from exc

    body = _load_json_payload(response_body)
    run_id = str(body.get("run_id", "")).strip()
    if not run_id:
        raise JobAgentError("Job Brief run API returned an empty run_id", "brief_run_api_invalid_json")
    return run_id, JobBriefReport.model_validate(body.get("brief") or {})


def request_brief_rerank_from_api(
    *,
    run_id: str,
    require_full_jd: bool,
    exclude_external_link_only: bool,
    location_keywords: list[str],
    include_keywords: list[str],
    exclude_keywords: list[str],
    min_fit_score: float | None,
    limit: int | None,
    api_base_url: str = DEFAULT_API_BASE_URL,
    timeout_seconds: int = DEFAULT_API_TIMEOUT_SECONDS,
) -> JobBriefReport:
    payload = json.dumps(
        {
            "require_full_jd": require_full_jd,
            "exclude_external_link_only": exclude_external_link_only,
            "location_keywords": location_keywords,
            "include_keywords": include_keywords,
            "exclude_keywords": exclude_keywords,
            "min_fit_score": min_fit_score,
            "limit": limit,
        }
    ).encode("utf-8")
    request = Request(
        f"{api_base_url.rstrip('/')}/brief/runs/{run_id}/rerank",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            response_body = response.read().decode("utf-8")
    except HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        error_payload = _load_json_payload(error_body)
        raise JobAgentError(
            str(error_payload.get("detail", f"/brief/runs/{run_id}/rerank failed with status {exc.code}")),
            str(error_payload.get("error_code", "brief_api_request_failed")),
        ) from exc
    except URLError as exc:
        raise JobAgentError(
            "无法连接 FastAPI 后端，请先启动 .venv\\Scripts\\python.exe -m uvicorn app.main:app --reload",
            "brief_api_unavailable",
        ) from exc

    return JobBriefReport.model_validate(_load_json_payload(response_body))


def request_job_candidate_from_brief_run_api(
    *,
    run_id: str,
    rank: int | None = None,
    item_id: int | None = None,
    api_base_url: str = DEFAULT_API_BASE_URL,
    timeout_seconds: int = DEFAULT_API_TIMEOUT_SECONDS,
) -> JobImportCandidate:
    payload = json.dumps(
        {
            "run_id": run_id,
            "rank": rank,
            "item_id": item_id,
        }
    ).encode("utf-8")
    request = Request(
        f"{api_base_url.rstrip('/')}/job-candidates/from-brief-run",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            response_body = response.read().decode("utf-8")
    except HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        error_payload = _load_json_payload(error_body)
        raise JobAgentError(
            str(error_payload.get("detail", f"/job-candidates/from-brief-run failed with status {exc.code}")),
            str(error_payload.get("error_code", "job_candidate_api_request_failed")),
        ) from exc
    except URLError as exc:
        raise JobAgentError(
            "无法连接 FastAPI 后端，请先启动 .venv\\Scripts\\python.exe -m uvicorn app.main:app --reload",
            "job_candidate_api_unavailable",
        ) from exc

    payload_object = _load_json_payload(response_body)
    return JobImportCandidate.model_validate(payload_object.get("candidate") or {})


def request_list_job_candidates_from_api(
    *,
    status: str | None = None,
    limit: int = 20,
    api_base_url: str = DEFAULT_API_BASE_URL,
    timeout_seconds: int = DEFAULT_API_TIMEOUT_SECONDS,
) -> list[JobImportCandidate]:
    query_parts = [f"limit={int(limit)}"]
    if status:
        query_parts.append(f"status={status}")
    request = Request(
        f"{api_base_url.rstrip('/')}/job-candidates?{'&'.join(query_parts)}",
        method="GET",
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            response_body = response.read().decode("utf-8")
    except HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        error_payload = _load_json_payload(error_body)
        raise JobAgentError(
            str(error_payload.get("detail", f"/job-candidates failed with status {exc.code}")),
            str(error_payload.get("error_code", "job_candidate_api_request_failed")),
        ) from exc
    except URLError as exc:
        raise JobAgentError(
            "无法连接 FastAPI 后端，请先启动 .venv\\Scripts\\python.exe -m uvicorn app.main:app --reload",
            "job_candidate_api_unavailable",
        ) from exc

    payload_object = _load_json_payload(response_body)
    return [
        JobImportCandidate.model_validate(item)
        for item in payload_object.get("candidates") or []
        if isinstance(item, dict)
    ]


def request_update_job_candidate_from_api(
    *,
    candidate_id: str,
    status: str,
    user_notes: str | None = None,
    api_base_url: str = DEFAULT_API_BASE_URL,
    timeout_seconds: int = DEFAULT_API_TIMEOUT_SECONDS,
) -> JobImportCandidate:
    payload = json.dumps(
        {
            "status": status,
            "user_notes": user_notes,
        }
    ).encode("utf-8")
    request = Request(
        f"{api_base_url.rstrip('/')}/job-candidates/{candidate_id}",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="PATCH",
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            response_body = response.read().decode("utf-8")
    except HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        error_payload = _load_json_payload(error_body)
        raise JobAgentError(
            str(error_payload.get("detail", f"/job-candidates/{candidate_id} failed with status {exc.code}")),
            str(error_payload.get("error_code", "job_candidate_api_request_failed")),
        ) from exc
    except URLError as exc:
        raise JobAgentError(
            "无法连接 FastAPI 后端，请先启动 .venv\\Scripts\\python.exe -m uvicorn app.main:app --reload",
            "job_candidate_api_unavailable",
        ) from exc

    payload_object = _load_json_payload(response_body)
    return JobImportCandidate.model_validate(payload_object.get("candidate") or {})


def _load_json_payload(raw_text: str) -> dict[str, object]:
    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise JobAgentError("Job Brief API returned invalid JSON", "brief_api_invalid_json") from exc

    if not isinstance(payload, dict):
        raise JobAgentError("Job Brief API returned an invalid response object", "brief_api_invalid_json")
    return payload


def render_analysis_tab(
    *,
    use_llm_jd: bool,
    use_llm_resume_optimize: bool,
    use_llm_project_challenge: bool,
    use_langgraph_workflow: bool,
    save_result: bool,
) -> None:
    if "analysis_resume_text" not in st.session_state:
        st.session_state["analysis_resume_text"] = SAMPLE_RESUME
    if "analysis_jd_text" not in st.session_state:
        st.session_state["analysis_jd_text"] = SAMPLE_JD

    left, right = st.columns(2)
    with left:
        uploaded_resume = st.file_uploader(
            "上传简历文件（.txt / .md）",
            type=["txt", "md"],
            key="analysis_resume_file",
        )
        if uploaded_resume is not None:
            resume_file_bytes = uploaded_resume.getvalue()
            resume_file_fingerprint = (
                f"{uploaded_resume.name}:{hashlib.sha256(resume_file_bytes).hexdigest()}"
            )
            if st.session_state.get("analysis_resume_file_fingerprint") != resume_file_fingerprint:
                try:
                    extracted_resume_text = extract_text_from_resume_file(
                        uploaded_resume.name,
                        resume_file_bytes,
                    )
                except ResumeFileParseError as exc:
                    st.error(str(exc))
                else:
                    st.session_state["analysis_resume_text"] = extracted_resume_text
                    st.session_state["analysis_resume_file_fingerprint"] = resume_file_fingerprint
                    st.success(f"已读取简历文件：{uploaded_resume.name}")
        resume_text = st.text_area("简历文本", key="analysis_resume_text", height=320)
    with right:
        jd_url = st.text_input(
            "JD URL",
            key="analysis_jd_url",
            placeholder="https://example.com/job",
        )
        if st.button("从 URL 导入 JD", use_container_width=True):
            try:
                imported_jd_text = import_jd_from_url(jd_url)
            except JDUrlImportError as exc:
                st.error(str(exc))
            else:
                st.session_state["analysis_jd_text"] = imported_jd_text
                st.success("已从 URL 导入 JD 文本")
        st.caption("安全边界：只支持公开 http/https 网页文本提取，失败时请手动粘贴 JD。")
        jd_text = st.text_area("目标岗位 JD", key="analysis_jd_text", height=320)

    if st.button("生成分析报告", type="primary", use_container_width=True):
        if not resume_text.strip() or not jd_text.strip():
            st.warning("请先填写简历文本和 JD 文本。")
            return

        try:
            workflow_runner = (
                run_langgraph_job_analysis_workflow
                if use_langgraph_workflow
                else run_job_analysis_workflow
            )
            workflow_result = workflow_runner(
                resume_text=resume_text,
                jd_text=jd_text,
                use_llm_jd=use_llm_jd,
                use_llm_resume_optimize=use_llm_resume_optimize,
                use_llm_project_challenge=use_llm_project_challenge,
            )
        except (RuntimeError, ValueError) as exc:
            st.error(str(exc))
            return

        result = workflow_result.final_report
        workflow_steps = [step.model_dump() for step in workflow_result.state.steps]
        workflow_type = "langgraph_prototype" if use_langgraph_workflow else "default_python"
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
            st.caption(f"当前 workflow 类型：{workflow_type}")
            render_workflow_trace(workflow_steps)
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


def render_job_brief_tab(*, use_llm_jd: bool) -> None:
    st.subheader("岗位批量推荐 / Job Brief")
    st.caption("最小演示版支持 mock 和 local_db；不在前端触发采集，不加入 tracker。")

    if "brief_resume_text" not in st.session_state:
        st.session_state["brief_resume_text"] = SAMPLE_RESUME
    if "brief_query_text" not in st.session_state:
        st.session_state["brief_query_text"] = "python backend llm jobs"
    if "brief_generated_queries" not in st.session_state:
        st.session_state["brief_generated_queries"] = []
    if "brief_last_report" not in st.session_state:
        st.session_state["brief_last_report"] = None
    if "brief_last_run_id" not in st.session_state:
        st.session_state["brief_last_run_id"] = ""
    if "brief_candidate_flash" not in st.session_state:
        st.session_state["brief_candidate_flash"] = ""

    left, right = st.columns([2, 1])
    with left:
        resume_text = st.text_area(
            "简历文本",
            key="brief_resume_text",
            height=240,
        )
        if st.button("Generate search queries from resume", use_container_width=True):
            try:
                st.session_state["brief_generated_queries"] = generate_search_queries_from_resume(
                    resume_text=resume_text,
                    max_queries=5,
                )
            except JobAgentError as exc:
                st.session_state["brief_generated_queries"] = []
                st.error(str(exc))

        generated_queries = st.session_state.get("brief_generated_queries") or []
        if generated_queries:
            st.markdown("**Recommended Search Queries**")
            selected_generated_query = st.selectbox(
                "Choose a query to fill into the search box",
                options=generated_queries,
                key="brief_generated_query_selection",
            )
            if st.button("Use selected query", use_container_width=True):
                st.session_state["brief_query_text"] = selected_generated_query
                st.rerun()

        query = st.text_input(
            "搜索 query",
            key="brief_query_text",
            placeholder="例如：python backend llm jobs",
        )
    with right:
        provider = st.selectbox(
            "Provider",
            options=["mock", "local_db"],
            index=0,
            help="mock 使用演示岗位；local_db 从本地 public_job_posts 搜索已采集真实岗位。",
        )
        if provider == "local_db":
            st.info("local_db：从本地 public_job_posts 岗位库搜索真实已采集岗位。请先运行 CUHKSZ collector。")
        limit = st.select_slider(
            "推荐岗位数量",
            options=list(range(1, 11)),
            value=5,
        )
        use_llm_jd_for_brief = st.checkbox(
            "启用 LLM JD 分析",
            value=use_llm_jd,
            help="只影响岗位 brief 内部的 JDAnalysisAgent；其他 agent 仍保持 mock。",
            key="brief_use_llm_jd",
        )
        save_as_run = st.checkbox(
            "Save this brief as a run",
            value=False,
            help="Saves this brief to SQLite so it can be reranked later without re-searching.",
            key="brief_save_as_run",
        )

    if st.button("生成 Job Brief", type="primary", use_container_width=True):
        try:
            run_id = ""
            if save_as_run:
                run_id, report = request_brief_run_from_api(
                    resume_text=resume_text,
                    query=query,
                    provider=provider,
                    limit=limit,
                    use_llm_jd=use_llm_jd_for_brief,
                )
            elif provider == "local_db":
                report = request_job_brief_from_api(
                    resume_text=resume_text,
                    query=query,
                    provider=provider,
                    limit=limit,
                    use_llm_jd=use_llm_jd_for_brief,
                )
            else:
                report = build_brief_from_search(
                    resume_text=resume_text,
                    query=query,
                    provider=provider,
                    limit=limit,
                    use_llm_jd=use_llm_jd_for_brief,
                )
        except JobAgentError as exc:
            if provider == "local_db" and exc.error_code == "brief_jobs_empty":
                st.error("本地岗位库为空，请先运行 python scripts/collect_cuhksz_jobs.py --limit 10")
            else:
                st.error(str(exc))
            return

        st.session_state["brief_last_report"] = report.model_dump(mode="json")
        st.session_state["brief_last_run_id"] = run_id
        st.success(f"已生成 {report.total_jobs} 个岗位的推荐 Brief")
        if run_id:
            st.info(f"Saved brief run: {run_id}")

    stored_report = st.session_state.get("brief_last_report")
    if stored_report:
        render_job_brief_report(
            JobBriefReport.model_validate(stored_report),
            run_id=st.session_state.get("brief_last_run_id") or None,
        )

    st.markdown("---")
    st.markdown("### Brief Run Rerank")
    rerank_run_id = st.text_input(
        "Run ID",
        value=st.session_state.get("brief_last_run_id", ""),
        key="brief_rerank_run_id",
        placeholder="Paste a saved run_id",
    )
    rerank_col1, rerank_col2 = st.columns(2)
    with rerank_col1:
        require_full_jd = st.checkbox("Require full_jd", value=False, key="brief_rerank_require_full_jd")
        exclude_external_link_only = st.checkbox(
            "Exclude external_link_only",
            value=False,
            key="brief_rerank_exclude_external",
        )
        min_fit_score_value = st.number_input(
            "Min fit score",
            min_value=0.0,
            max_value=100.0,
            value=0.0,
            step=1.0,
            key="brief_rerank_min_fit_score",
        )
    with rerank_col2:
        rerank_limit = st.select_slider(
            "Rerank result count",
            options=list(range(1, 11)),
            value=5,
            key="brief_rerank_limit",
        )
        location_keywords_text = st.text_input(
            "Location keywords",
            value="",
            key="brief_rerank_location_keywords",
            placeholder="e.g. Shenzhen, Remote",
        )
        include_keywords_text = st.text_input(
            "Include keywords",
            value="",
            key="brief_rerank_include_keywords",
            placeholder="e.g. PyTorch, biosignal",
        )
        exclude_keywords_text = st.text_input(
            "Exclude keywords",
            value="",
            key="brief_rerank_exclude_keywords",
            placeholder="e.g. sales, internship",
        )

    if st.button("Rerank saved brief run", use_container_width=True):
        normalized_run_id = rerank_run_id.strip()
        if not normalized_run_id:
            st.warning("请先输入 run_id。")
            return

        try:
            reranked_report = request_brief_rerank_from_api(
                run_id=normalized_run_id,
                require_full_jd=require_full_jd,
                exclude_external_link_only=exclude_external_link_only,
                location_keywords=_split_keywords(location_keywords_text),
                include_keywords=_split_keywords(include_keywords_text),
                exclude_keywords=_split_keywords(exclude_keywords_text),
                min_fit_score=min_fit_score_value if min_fit_score_value > 0 else None,
                limit=rerank_limit,
            )
        except JobAgentError as exc:
            st.error(str(exc))
            return

        st.session_state["brief_last_report"] = reranked_report.model_dump(mode="json")
        st.session_state["brief_last_run_id"] = normalized_run_id
        st.success(f"已完成 rerank：{normalized_run_id}")
        render_job_brief_report(reranked_report, run_id=normalized_run_id)

    render_job_candidates_section()


def render_job_brief_report(report: JobBriefReport, *, run_id: str | None = None) -> None:
    if run_id:
        st.caption(f"Run ID：{run_id}")

    col1, col2 = st.columns(2)
    col1.metric("岗位总数", report.total_jobs)
    col2.metric("Top Skills", len(report.top_skills))

    st.markdown("### Market Summary")
    st.write(report.market_summary)
    if report.scoring_quality_summary:
        st.caption(report.scoring_quality_summary)

    if report.top_skills:
        st.markdown("### Top Skills")
        st.write(", ".join(report.top_skills))

    st.markdown("### 推荐岗位")
    table_rows = [
        {
            "rank": item.rank,
            "title": item.job.title,
            "company": item.job.company,
            "location": item.job.location,
            "fit_score": item.fit_score,
            "scoring_quality": format_scoring_quality(item.scoring_quality),
            "advice": item.advice,
        }
        for item in report.recommended_jobs
    ]
    st.dataframe(table_rows, hide_index=True, use_container_width=True)

    for item in report.recommended_jobs:
        with st.expander(f"#{item.rank} {item.job.title} | {item.job.company}"):
            st.markdown(f"**URL:** {item.job.url or 'N/A'}")
            st.markdown(f"**Fit Score:** {item.fit_score:.1f}")
            st.markdown(f"**Scoring Quality:** {format_scoring_quality(item.scoring_quality)}")
            if item.scoring_quality == "external_link_only":
                st.caption("该岗位主要是外链摘要，当前评分仅供参考。")
            if run_id:
                if st.button("Save as Candidate", key=f"save_candidate_{run_id}_{item.rank}", use_container_width=True):
                    try:
                        candidate = request_job_candidate_from_brief_run_api(run_id=run_id, rank=item.rank)
                    except JobAgentError as exc:
                        st.error(str(exc))
                    else:
                        st.session_state["brief_candidate_flash"] = f"Saved candidate: {candidate.candidate_id}"
                        st.success(st.session_state["brief_candidate_flash"])
            st.markdown(f"**Advice:** {item.advice}")
            st.markdown("**Fit Reasons**")
            for reason in item.fit_reasons:
                st.markdown(f"- {reason}")
            st.markdown("**Risk Points**")
            for risk in item.risk_points:
                st.markdown(f"- {risk}")
            st.markdown("**Matched Points**")
            for point in item.match_report.matched_points:
                st.markdown(f"- {point}")
            st.markdown("**Missing Points**")
            for point in item.match_report.missing_points:
                st.markdown(f"- {point}")
            st.markdown("**Short-term Suggestions**")
            for suggestion in item.match_report.short_term_suggestions:
                st.markdown(f"- {suggestion}")

    markdown_brief = build_job_brief_markdown(report)
    st.markdown("### Markdown Brief")
    st.text_area("Brief Markdown", value=markdown_brief, height=320)
    st.download_button(
        label="下载 Job Brief Markdown",
        data=markdown_brief,
        file_name="job_brief.md",
        mime="text/markdown",
    )


def render_job_candidates_section() -> None:
    st.markdown("---")
    st.markdown("### Job Candidates")
    flash_message = st.session_state.get("brief_candidate_flash") or ""
    if flash_message:
        st.success(flash_message)

    status_filter = st.selectbox(
        "Candidate status filter",
        options=["all", "draft", "reviewed", "ready_for_tracker", "ready_for_analysis", "rejected"],
        index=0,
        key="brief_candidate_status_filter",
    )

    try:
        candidates = request_list_job_candidates_from_api(
            status=None if status_filter == "all" else status_filter,
            limit=20,
        )
    except JobAgentError as exc:
        st.info(f"Job Candidates unavailable: {exc}")
        return

    if not candidates:
        st.caption("还没有保存的 candidates。先从某个 brief run 推荐项点击 Save as Candidate。")
        return

    for candidate in candidates:
        with st.expander(f"{candidate.title} | {candidate.company or 'N/A'} | {candidate.status}"):
            st.markdown(f"**Candidate ID:** {candidate.candidate_id}")
            st.markdown(f"**Location:** {candidate.location or 'N/A'}")
            st.markdown(f"**Fit Score:** {candidate.fit_score if candidate.fit_score is not None else 'N/A'}")
            st.markdown(f"**Quality:** {candidate.quality_label or 'N/A'}")
            if candidate.jd_text_preview:
                st.caption(candidate.jd_text_preview[:500])
            new_status = st.selectbox(
                "Update Status",
                options=["reviewed", "ready_for_tracker", "ready_for_analysis", "rejected"],
                index=0,
                key=f"candidate_status_{candidate.candidate_id}",
            )
            if st.button("Update Candidate Status", key=f"candidate_update_{candidate.candidate_id}"):
                try:
                    updated = request_update_job_candidate_from_api(
                        candidate_id=candidate.candidate_id,
                        status=new_status,
                        user_notes=candidate.user_notes,
                    )
                except JobAgentError as exc:
                    st.error(str(exc))
                else:
                    st.session_state["brief_candidate_flash"] = f"Updated candidate: {updated.candidate_id} -> {updated.status}"
                    st.rerun()


def _split_keywords(value: str) -> list[str]:
    keywords: list[str] = []
    for item in value.replace("\n", ",").split(","):
        normalized = item.strip()
        if normalized and normalized not in keywords:
            keywords.append(normalized)
    return keywords


def build_job_brief_markdown(report: JobBriefReport) -> str:
    lines = [
        f"# Job Brief: {report.query}",
        "",
        f"- Provider: {report.provider}",
        f"- Total Jobs: {report.total_jobs}",
        f"- Top Skills: {', '.join(report.top_skills) if report.top_skills else 'N/A'}",
        f"- Scoring Quality Summary: {report.scoring_quality_summary or 'N/A'}",
        "",
        "## Market Summary",
        report.market_summary,
        "",
        "## Application Strategy",
    ]
    lines.extend(f"- {item}" for item in report.application_strategy)
    lines.append("")
    lines.append("## Recommendations")

    for item in report.recommended_jobs:
        lines.extend(
            [
                "",
                f"### #{item.rank} {item.job.title}",
                f"- Company: {item.job.company}",
                f"- Location: {item.job.location}",
                f"- Fit Score: {item.fit_score:.1f}",
                f"- Scoring Quality: {format_scoring_quality(item.scoring_quality)}",
                f"- Advice: {item.advice}",
                "- Fit Reasons:",
            ]
        )
        lines.extend(f"  - {reason}" for reason in item.fit_reasons)
        lines.append("- Risk Points:")
        lines.extend(f"  - {risk}" for risk in item.risk_points)

    return "\n".join(lines).strip() + "\n"


def format_scoring_quality(value: str) -> str:
    return SCORING_QUALITY_LABELS.get(value, value)


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
        render_workflow_trace(workflow_steps)
    with detail_json:
        st.json(record)


def render_workflow_trace(workflow_steps: list[dict]) -> None:
    if not workflow_steps:
        st.info("这条记录没有保存 workflow trace，可能来自旧版本。")
        return

    workflow_run_id = workflow_steps[0].get("workflow_run_id") or "未记录"
    total_duration_ms = sum(float(step.get("duration_ms") or 0.0) for step in workflow_steps)
    fallback_count = sum(1 for step in workflow_steps if step.get("mode") == "fallback")

    col1, col2, col3 = st.columns(3)
    col1.metric("步骤数", len(workflow_steps))
    col2.metric("总耗时", f"{total_duration_ms:.1f} ms")
    col3.metric("Fallback", fallback_count)
    st.caption(f"Workflow Run ID：{workflow_run_id}")

    rows = []
    for index, step in enumerate(workflow_steps, start=1):
        guardrails = step.get("guardrails") or []
        rows.append(
            {
                "序号": index,
                "Agent": step.get("name"),
                "模式": step.get("mode"),
                "状态": step.get("status"),
                "耗时(ms)": round(float(step.get("duration_ms") or 0.0), 1),
                "Fallback 原因": step.get("fallback_reason") or "",
                "摘要": step.get("summary"),
                "Guardrails": "；".join(guardrails),
            }
        )
    st.dataframe(rows, hide_index=True, use_container_width=True)


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
