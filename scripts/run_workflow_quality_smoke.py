from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.schemas.match import MatchReport, ProjectChallengeReport, ResumeOptimizationResult
from app.schemas.report import AnalysisQualityReport, FinalReport
from app.services.storage_service import load_analysis_record, save_final_report
from app.workflows.job_analysis_workflow import WorkflowStepTrace, run_job_analysis_workflow

DATABASE_PATH = Path("data/workflow_quality_smoke.sqlite3")
REPORT_PATH = Path("docs/demo_outputs/workflow_quality_smoke_report.md")
QUALITY_DOC_PATH = Path("docs/WORKFLOW_QUALITY_SMOKE_TEST.md")

RESUME_TEXT = """
Candidate: Alex Chen
Target: AI Agent / Backend Engineer Intern

Education:
- BEng Computer Science, Shenzhen Institute of Technology, expected 2027

Skills:
- Python, FastAPI, SQLite, LangGraph, LLM API integration, Docker, GitHub Actions
- REST API design, Pydantic models, pytest, Git, Markdown documentation

Projects:
1. JobAgent-style Resume/JD Matching System
   Built a Python and FastAPI backend that parses resume text, extracts JD requirements,
   compares evidence, stores SQLite analysis records, and emits Markdown reports.
   Added pytest coverage and GitHub Actions for repeatable validation.

2. Semantic Search Job Crawler Prototype
   Implemented a local job crawler prototype with keyword filtering, simple semantic
   ranking, deduplication, and SQLite persistence for collected postings.

3. Embedded Networking Course Project
   Implemented an STM32-based sensor gateway and documented serial communication,
   reliability tradeoffs, and debugging steps.

Experience:
- Backend Engineering Intern, Campus AI Studio
  Built small FastAPI services, wrote integration tests, and reviewed model outputs
  for factuality and evidence grounding.
""".strip()

JD_TEXT = """
Role: AI Agent Backend Intern
Company: Example AI Lab
Location: Shenzhen / Remote

Responsibilities:
- Build Python backend services for AI agent workflow demos.
- Implement FastAPI endpoints, Pydantic schemas, and SQLite-backed persistence.
- Connect LLM or agent workflow components while keeping deterministic fallbacks.
- Write tests, documentation, and quality checks for generated model outputs.
- Review workflow outputs for evidence grounding, missing information, and hallucination risk.

Requirements:
- Python backend development experience.
- FastAPI or similar web framework experience.
- LLM / agent workflow experience, including LangGraph or equivalent orchestration.
- SQL database experience, preferably SQLite for prototypes.
- Ability to evaluate model output quality and explain improvement priorities.
- Git, testing, and documentation habits.

Preferred:
- Docker and GitHub Actions.
- Experience with job search, resume analysis, or recommendation systems.
""".strip()


def main() -> None:
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    if DATABASE_PATH.exists():
        DATABASE_PATH.unlink()

    workflow_result = run_job_analysis_workflow(
        resume_text=RESUME_TEXT,
        jd_text=JD_TEXT,
        use_llm_jd=False,
        use_llm_resume_optimize=False,
        use_llm_project_challenge=False,
    )
    workflow_steps = [step.model_dump() for step in workflow_result.state.steps]
    record_id = save_final_report(
        workflow_result.final_report,
        workflow_steps=workflow_steps,
        database_path=DATABASE_PATH,
    )
    loaded_record = load_analysis_record(record_id, database_path=DATABASE_PATH)
    if loaded_record is None:
        raise RuntimeError(f"Failed to load saved analysis record {record_id}")

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        build_demo_report(
            record_id=record_id,
            workflow_run_id=workflow_result.state.workflow_run_id,
            generated_at=generated_at,
            final_report=workflow_result.final_report,
            loaded_record=loaded_record,
        ),
        encoding="utf-8",
    )
    QUALITY_DOC_PATH.write_text(
        build_quality_doc(
            record_id=record_id,
            workflow_run_id=workflow_result.state.workflow_run_id,
            generated_at=generated_at,
            final_report=workflow_result.final_report,
            steps=workflow_result.state.steps,
        ),
        encoding="utf-8",
    )

    print(f"record_id: {record_id}")
    print(f"workflow_run_id: {workflow_result.state.workflow_run_id}")
    print(f"report: {REPORT_PATH}")
    print(f"quality_doc: {QUALITY_DOC_PATH}")


def build_demo_report(
    *,
    record_id: int,
    workflow_run_id: str,
    generated_at: str,
    final_report: FinalReport,
    loaded_record: dict[str, Any],
) -> str:
    return "\n".join(
        [
            "# Workflow Quality Smoke Test Report",
            "",
            f"- record_id: {record_id}",
            f"- workflow_run_id: {workflow_run_id}",
            f"- generated_at: {generated_at}",
            "",
            "## Final Markdown Report",
            "",
            loaded_record["markdown_report"].strip(),
            "",
            "## Workflow Steps",
            "",
            build_steps_table(loaded_record["workflow_steps"]),
            "",
            "## Saved Record Check",
            "",
            f"- loaded_record_id: {loaded_record['id']}",
            f"- loaded_overall_score: {loaded_record['match_report']['overall_score']}",
            f"- loaded_markdown_chars: {len(loaded_record['markdown_report'])}",
            f"- in_memory_markdown_chars: {len(final_report.markdown_report)}",
            "",
        ]
    )


def build_quality_doc(
    *,
    record_id: int,
    workflow_run_id: str,
    generated_at: str,
    final_report: FinalReport,
    steps: list[WorkflowStepTrace],
) -> str:
    match_report = final_report.match_report
    optimization = final_report.optimization_result
    challenges = final_report.project_challenge_report
    quality = final_report.analysis_quality
    rewrite_count = len(optimization.rewrite_suggestions)
    challenge_count = count_challenge_questions(challenges)

    return "\n".join(
        [
            "# Workflow Quality Smoke Test",
            "",
            "## Purpose",
            "",
            (
                "This document records a repeatable smoke test for manually reviewing the "
                "current JobAgent workflow output quality. It uses deterministic mock agents, "
                "so it does not require an API key and can be rerun during review."
            ),
            "",
            "## Run Command",
            "",
            "```bash",
            r".venv\Scripts\python.exe scripts\run_workflow_quality_smoke.py",
            "```",
            "",
            "Outputs:",
            "",
            f"- Demo report: `{REPORT_PATH.as_posix()}`",
            f"- Quality analysis: `{QUALITY_DOC_PATH.as_posix()}`",
            f"- Local smoke database: `{DATABASE_PATH.as_posix()}` (not committed)",
            "",
            "## Test Input",
            "",
            (
                "Resume summary: Alex Chen targets an AI Agent / Backend Engineer Intern role "
                "and presents Python, FastAPI, SQLite, LangGraph, LLM API, Docker, GitHub "
                "Actions, testing, and documentation experience. The resume includes a "
                "JobAgent-like matching system, a semantic search job crawler prototype, an "
                "STM32 networking course project, and a small backend internship."
            ),
            "",
            (
                "JD summary: Example AI Lab is hiring an AI Agent Backend Intern to build "
                "Python/FastAPI services, SQLite persistence, LLM or agent workflow components, "
                "tests, documentation, and quality checks for evidence grounding and "
                "hallucination risk."
            ),
            "",
            "## Workflow Result Summary",
            "",
            f"- generated_at: {generated_at}",
            f"- workflow_run_id: {workflow_run_id}",
            f"- saved analysis_record_id: {record_id}",
            f"- overall_score: {match_report.overall_score}",
            f"- analysis_quality: {quality.overall_quality_label}",
            f"- parsed project count: {len(final_report.resume_profile.projects)}",
            f"- parsed work experience count: {len(final_report.resume_profile.work_experiences)}",
            f"- number of rewrite suggestions: {rewrite_count}",
            f"- number of project challenge questions: {challenge_count}",
            "",
            "Matched strengths:",
            "",
            bullet_list(match_report.matched_points),
            "",
            "Major gaps:",
            "",
            bullet_list(match_report.missing_points or match_report.risks),
            "",
            "Analysis quality details:",
            "",
            bullet_list(format_quality_details(quality)),
            "",
            "Workflow steps:",
            "",
            build_steps_table([step.model_dump() for step in steps]),
            "",
            "## Quality Review",
            "",
            "### 1. What works well",
            "",
            build_what_works(match_report, optimization, challenges),
            "",
            "### 2. What looks weak or generic",
            "",
            build_weak_points(match_report, optimization, challenges),
            "",
            "### 3. Where evidence grounding is good",
            "",
            build_grounding_notes(match_report, optimization, challenges),
            "",
            "### 4. Where hallucination risk exists",
            "",
            build_hallucination_notes(match_report, optimization, quality),
            "",
            "### 5. Which agent should be improved first",
            "",
            build_agent_priority(match_report, optimization, challenges),
            "",
            "## Next Improvement Candidates",
            "",
            "- Make ResumeParseAgent preserve project names, technologies, and evidence spans more explicitly.",
            "- Make MatchAgent separate strong evidence from broad keyword overlap in its scoring explanation.",
            "- Make ResumeOptimizeAgent produce fewer template-like bullets and cite the source project for every suggestion.",
            "- Make ProjectInterviewAgent ask deeper follow-up questions for the highest-value matched requirement.",
            "- Add stable quality metrics for report specificity, evidence coverage, and unsupported claims.",
            "",
        ]
    )


def build_steps_table(steps: list[dict[str, Any]]) -> str:
    rows = [
        "| step | agent_name | mode | summary | duration_ms | fallback_reason |",
        "| --- | --- | --- | --- | ---: | --- |",
    ]
    for index, step in enumerate(steps, start=1):
        rows.append(
            "| {step} | {agent_name} | {mode} | {summary} | {duration_ms:.3f} | {fallback_reason} |".format(
                step=index,
                agent_name=escape_table_cell(step.get("name", "")),
                mode=escape_table_cell(step.get("mode", "")),
                summary=escape_table_cell(step.get("summary", "")),
                duration_ms=float(step.get("duration_ms") or 0.0),
                fallback_reason=escape_table_cell(step.get("fallback_reason") or ""),
            )
        )
    return "\n".join(rows)


def count_challenge_questions(report: ProjectChallengeReport) -> int:
    return (
        len(report.basic_questions)
        + len(report.technical_deep_dive_questions)
        + len(report.architecture_questions)
        + len(report.tradeoff_questions)
        + len(report.grounded_questions)
    )


def format_quality_details(quality: AnalysisQualityReport) -> list[str]:
    details = [
        f"resume_quality_label: {quality.resume_quality_label}",
        f"jd_quality_label: {quality.jd_quality_label}",
        f"overall_quality_label: {quality.overall_quality_label}",
    ]
    details.extend(f"warning: {warning}" for warning in quality.warnings)
    details.extend(f"confidence: {note}" for note in quality.confidence_notes)
    return details


def build_what_works(
    match_report: MatchReport,
    optimization: ResumeOptimizationResult,
    challenges: ProjectChallengeReport,
) -> str:
    matched = match_report.matched_points[:3]
    lines = [
        (
            f"- The workflow identifies {len(match_report.matched_points)} matched points "
            f"and keeps the strongest ones visible: {join_inline(matched)}."
        ),
        (
            f"- Resume optimization produced {len(optimization.rewrite_suggestions)} rewrite "
            f"suggestions and {len(optimization.jd_targeted_bullets)} JD-targeted bullets."
        ),
        (
            f"- Project challenge generation produced {len(challenges.grounded_questions)} grounded "
            "questions tied back to matched or missing requirements."
        ),
    ]
    return "\n".join(lines)


def build_weak_points(
    match_report: MatchReport,
    optimization: ResumeOptimizationResult,
    challenges: ProjectChallengeReport,
) -> str:
    unsupported_rewrite_count = len([item for item in optimization.rewrite_suggestions if not item.evidence_source])
    rewrite_note = (
        f"- {unsupported_rewrite_count} rewrite suggestions have no explicit evidence source."
        if unsupported_rewrite_count
        else (
            "- Rewrite suggestions include explicit evidence sources, but several still read as "
            "generic skill-alignment bullets rather than project-specific achievements."
        )
    )
    weak_items = [
        (
            f"- The overall score is {match_report.overall_score}, but the report still needs "
            "clearer reasoning about how each subscore contributes to that number."
        ),
        rewrite_note,
        (
            "- The interview questions are useful for review, but several remain broad unless "
            "they cite the exact project detail the candidate should defend."
        ),
    ]
    if match_report.missing_points:
        weak_items.append(f"- Missing points are surfaced, but remediation is high level: {join_inline(match_report.missing_points[:2])}.")
    if not challenges.grounded_questions:
        weak_items.append("- No grounded project challenge questions were generated.")
    return "\n".join(weak_items)


def build_grounding_notes(
    match_report: MatchReport,
    optimization: ResumeOptimizationResult,
    challenges: ProjectChallengeReport,
) -> str:
    matched_requirements = [
        item.requirement
        for item in match_report.requirement_matches
        if item.match_level == "matched" and item.resume_evidence
    ]
    grounded_rewrites = [item for item in optimization.rewrite_suggestions if item.evidence_source]
    grounded_challenges = [item for item in challenges.grounded_questions if item.related_resume_evidence]
    return "\n".join(
        [
            (
                f"- Requirement matching is strongest for {len(matched_requirements)} requirements "
                f"with resume evidence, including: {join_inline(matched_requirements[:3])}."
            ),
            f"- {len(grounded_rewrites)} rewrite suggestions include evidence_source values.",
            f"- {len(grounded_challenges)} grounded interview questions include related resume evidence.",
        ]
    )


def build_hallucination_notes(
    match_report: MatchReport,
    optimization: ResumeOptimizationResult,
    quality: AnalysisQualityReport,
) -> str:
    missing_requirements = [
        item.requirement
        for item in match_report.requirement_matches
        if item.match_level == "missing"
    ]
    unsupported_rewrites = [item for item in optimization.rewrite_suggestions if not item.evidence_source]
    lines = [
        (
            f"- Hallucination risk is highest around missing requirements: "
            f"{join_inline(missing_requirements[:3]) or 'none detected'}."
        ),
        (
            f"- {len(unsupported_rewrites)} rewrite suggestions lack explicit evidence sources; "
            "these should remain framed as conditional or gap-closing suggestions."
        ),
    ]
    if quality.warnings:
        lines.append(f"- Quality warnings also constrain trust in the output: {join_inline(quality.warnings)}.")
    else:
        lines.append("- No analysis quality warnings were emitted for this smoke input.")
    return "\n".join(lines)


def build_agent_priority(
    match_report: MatchReport,
    optimization: ResumeOptimizationResult,
    challenges: ProjectChallengeReport,
) -> str:
    unsupported_rewrites = [item for item in optimization.rewrite_suggestions if not item.evidence_source]
    if unsupported_rewrites:
        return (
            "- Improve ResumeOptimizeAgent first, because unsupported rewrite suggestions are the "
            "most likely place for the workflow to overstate a candidate's experience."
        )
    if match_report.missing_points:
        return (
            "- Improve MatchAgent first, because the current gaps need sharper prioritization "
            "before downstream rewrite and interview agents can improve."
        )
    if not challenges.grounded_questions:
        return (
            "- Improve ProjectInterviewAgent first, because interview preparation needs grounded "
            "questions to be useful."
        )
    return (
        "- Improve MatchAgent first, because it controls the evidence chain used by both resume "
        "rewrite and project interview outputs."
    )


def bullet_list(items: list[str]) -> str:
    if not items:
        return "- None"
    return "\n".join(f"- {item}" for item in items)


def join_inline(items: list[str]) -> str:
    return "; ".join(items)


def escape_table_cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ").strip()


if __name__ == "__main__":
    main()
