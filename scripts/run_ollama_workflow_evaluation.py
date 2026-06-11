from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.agents.jd_analysis_agent import JD_ANALYSIS_SYSTEM_PROMPT
from app.agents.project_challenge_agent import PROJECT_CHALLENGE_SYSTEM_PROMPT
from app.agents.resume_optimize_agent import RESUME_OPTIMIZE_SYSTEM_PROMPT
from app.schemas.report import FinalReport
from app.services.llm_service import LLMConfig, LLMService, LLMServiceError, parse_json_object
from app.workflows.job_analysis_workflow import JobAnalysisWorkflowResult, run_job_analysis_workflow
from scripts.run_workflow_quality_smoke import JD_TEXT, RESUME_TEXT

OUTPUT_DIR = Path("docs/demo_outputs/ollama_workflow_eval")
SUMMARY_DOC_PATH = Path("docs/OLLAMA_LLM_WORKFLOW_EVALUATION.md")

LLM_REQUIRED_ENV = [
    "JOBAGENT_LLM_BASE_URL",
    "JOBAGENT_LLM_API_KEY",
    "JOBAGENT_LLM_MODEL",
]

MODE_CONFIGS: dict[str, dict[str, bool]] = {
    "mock": {
        "use_llm_jd": False,
        "use_llm_resume_optimize": False,
        "use_llm_project_challenge": False,
    },
    "ollama-jd-only": {
        "use_llm_jd": True,
        "use_llm_resume_optimize": False,
        "use_llm_project_challenge": False,
    },
    "ollama-resume-optimize-only": {
        "use_llm_jd": False,
        "use_llm_resume_optimize": True,
        "use_llm_project_challenge": False,
    },
    "ollama-project-challenge-only": {
        "use_llm_jd": False,
        "use_llm_resume_optimize": False,
        "use_llm_project_challenge": True,
    },
    "ollama-all-llm": {
        "use_llm_jd": True,
        "use_llm_resume_optimize": True,
        "use_llm_project_challenge": True,
    },
}
ALL_MODES = list(MODE_CONFIGS)


@dataclass
class UsageRecord:
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


@dataclass
class ModeEvaluation:
    mode: str
    generated_at: str
    config: LLMConfig
    workflow_result: JobAnalysisWorkflowResult
    token_rows: list[dict[str, Any]]
    usage_records: dict[str, UsageRecord] = field(default_factory=dict)

    @property
    def final_report(self) -> FinalReport:
        return self.workflow_result.final_report

    @property
    def fallback_count(self) -> int:
        return sum(1 for step in self.workflow_result.state.steps if step.mode == "fallback")

    @property
    def estimated_input_tokens(self) -> int:
        return sum(int(row["estimated_input_tokens"]) for row in self.token_rows)

    @property
    def estimated_output_tokens(self) -> int:
        return sum(int(row["estimated_output_tokens"]) for row in self.token_rows)

    @property
    def estimated_total_tokens(self) -> int:
        return sum(int(row["estimated_total_tokens"]) for row in self.token_rows)


class TrackingLLMService(LLMService):
    def __init__(
        self,
        config: LLMConfig,
        *,
        agent_name: str,
        usage_records: dict[str, UsageRecord],
    ) -> None:
        super().__init__(config)
        self.agent_name = agent_name
        self.usage_records = usage_records

    def chat_completion_json(self, *, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        if not self.config.is_configured:
            raise LLMServiceError("LLM is not configured.")

        payload = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": self.config.temperature,
            "response_format": {"type": "json_object"},
        }
        raw_response = self._post_chat_completions(payload)
        self.usage_records[self.agent_name] = extract_usage(raw_response)
        content = extract_message_content(raw_response)
        return parse_json_object(content)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run JobAgent Ollama workflow evaluation modes.")
    parser.add_argument(
        "--mode",
        choices=["all", *ALL_MODES],
        default="mock",
        help="Evaluation mode to run. Default: mock.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    selected_modes = ALL_MODES if args.mode == "all" else [args.mode]
    needs_llm = any(mode != "mock" for mode in selected_modes)

    if needs_llm and not has_required_llm_env():
        print("LLM is not configured. Set JOBAGENT_LLM_BASE_URL, JOBAGENT_LLM_API_KEY, JOBAGENT_LLM_MODEL.")
        return 0

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    config = LLMConfig.from_env()
    evaluations = [run_mode(mode, config=config, generated_at=generated_at) for mode in selected_modes]

    for evaluation in evaluations:
        report_path = OUTPUT_DIR / f"{mode_to_file_stem(evaluation.mode)}_report.md"
        report_path.write_text(build_mode_report(evaluation), encoding="utf-8")

    comparison_path = OUTPUT_DIR / "comparison_summary.md"
    comparison_path.write_text(build_comparison_summary(evaluations), encoding="utf-8")
    SUMMARY_DOC_PATH.write_text(build_summary_doc(evaluations), encoding="utf-8")

    print(f"modes: {', '.join(selected_modes)}")
    print(f"output_dir: {OUTPUT_DIR}")
    print(f"summary_doc: {SUMMARY_DOC_PATH}")
    return 0


def run_mode(mode: str, *, config: LLMConfig, generated_at: str) -> ModeEvaluation:
    mode_config = MODE_CONFIGS[mode]
    usage_records: dict[str, UsageRecord] = {}
    jd_service = (
        TrackingLLMService(config, agent_name="JDAnalysisAgent", usage_records=usage_records)
        if mode_config["use_llm_jd"]
        else None
    )
    resume_service = (
        TrackingLLMService(config, agent_name="ResumeOptimizeAgent", usage_records=usage_records)
        if mode_config["use_llm_resume_optimize"]
        else None
    )
    project_service = (
        TrackingLLMService(config, agent_name="ProjectInterviewAgent", usage_records=usage_records)
        if mode_config["use_llm_project_challenge"]
        else None
    )

    workflow_result = run_job_analysis_workflow(
        resume_text=RESUME_TEXT,
        jd_text=JD_TEXT,
        use_llm_jd=mode_config["use_llm_jd"],
        jd_llm_service=jd_service,
        use_llm_resume_optimize=mode_config["use_llm_resume_optimize"],
        resume_optimize_llm_service=resume_service,
        use_llm_project_challenge=mode_config["use_llm_project_challenge"],
        project_challenge_llm_service=project_service,
    )
    token_rows = build_token_rows(workflow_result, usage_records)
    return ModeEvaluation(
        mode=mode,
        generated_at=generated_at,
        config=config,
        workflow_result=workflow_result,
        token_rows=token_rows,
        usage_records=usage_records,
    )


def build_token_rows(
    workflow_result: JobAnalysisWorkflowResult,
    usage_records: dict[str, UsageRecord],
) -> list[dict[str, Any]]:
    state = workflow_result.state
    report = workflow_result.final_report
    resume_profile_json = json.dumps(state.resume_profile.model_dump(), ensure_ascii=False) if state.resume_profile else ""
    job_analysis_json = json.dumps(state.job_analysis.model_dump(), ensure_ascii=False) if state.job_analysis else ""
    match_report_json = json.dumps(state.match_report.model_dump(), ensure_ascii=False) if state.match_report else ""

    estimates = {
        "JDAnalysisAgent": {
            "input": f"{JD_ANALYSIS_SYSTEM_PROMPT}\n\nJob description:\n\n{JD_TEXT}",
            "output": json.dumps(report.job_analysis.model_dump(), ensure_ascii=False),
        },
        "ResumeOptimizeAgent": {
            "input": (
                f"{RESUME_OPTIMIZE_SYSTEM_PROMPT}\n\n"
                f"Original resume text:\n{RESUME_TEXT}\n\n"
                f"ResumeProfile JSON:\n{resume_profile_json}\n\n"
                f"JobAnalysis JSON:\n{job_analysis_json}\n\n"
                f"MatchReport JSON:\n{match_report_json}"
            ),
            "output": json.dumps(report.optimization_result.model_dump(), ensure_ascii=False),
        },
        "ProjectInterviewAgent": {
            "input": (
                f"{PROJECT_CHALLENGE_SYSTEM_PROMPT}\n\n"
                f"ResumeProfile JSON:\n{resume_profile_json}\n\n"
                f"JobAnalysis JSON:\n{job_analysis_json}"
            ),
            "output": json.dumps(report.project_challenge_report.model_dump(), ensure_ascii=False),
        },
    }

    rows: list[dict[str, Any]] = []
    for agent_name, values in estimates.items():
        step = find_step(workflow_result, agent_name)
        input_tokens = estimate_tokens(values["input"])
        output_tokens = estimate_tokens(values["output"])
        usage = usage_records.get(agent_name, UsageRecord())
        rows.append(
            {
                "agent": agent_name,
                "estimated_input_tokens": input_tokens,
                "estimated_output_tokens": output_tokens,
                "estimated_total_tokens": input_tokens + output_tokens,
                "mode": step.get("mode", ""),
                "fallback_reason": step.get("fallback_reason") or "",
                "actual_prompt_tokens": usage.prompt_tokens,
                "actual_completion_tokens": usage.completion_tokens,
                "actual_total_tokens": usage.total_tokens,
            }
        )
    return rows


def build_mode_report(evaluation: ModeEvaluation) -> str:
    report = evaluation.final_report
    state = evaluation.workflow_result.state
    quality_notes = build_quality_notes(evaluation)

    return "\n".join(
        [
            f"# Ollama Workflow Evaluation - {evaluation.mode}",
            "",
            "## Config",
            "",
            f"- model: {display_env_or_unconfigured('JOBAGENT_LLM_MODEL')}",
            f"- base_url: {display_env_or_unconfigured('JOBAGENT_LLM_BASE_URL')}",
            f"- temperature: {evaluation.config.temperature}",
            f"- timeout: {evaluation.config.timeout_seconds}",
            f"- mode: {evaluation.mode}",
            f"- generated_at: {evaluation.generated_at}",
            "",
            "## Workflow Steps",
            "",
            build_steps_table([step.model_dump() for step in state.steps]),
            "",
            "## Token Estimate",
            "",
            build_token_table(evaluation.token_rows),
            "",
            "## JDAnalysisAgent Output",
            "",
            f"- job_title: {report.job_analysis.job_title}",
            f"- company: {report.job_analysis.company}",
            f"- location: {report.job_analysis.location}",
            f"- required_skills: {join_list(report.job_analysis.required_skills)}",
            f"- preferred_skills: {join_list(report.job_analysis.preferred_skills)}",
            f"- responsibilities: {join_list(report.job_analysis.responsibilities)}",
            f"- keywords: {join_list(report.job_analysis.keywords)}",
            "",
            "## ResumeOptimizeAgent Output",
            "",
            f"- rewrite_suggestions_count: {len(report.optimization_result.rewrite_suggestions)}",
            f"- jd_targeted_bullets_count: {len(report.optimization_result.jd_targeted_bullets)}",
            f"- missing_info_needed: {join_list(report.optimization_result.missing_info_needed)}",
            f"- do_not_exaggerate: {join_list(report.optimization_result.do_not_exaggerate)}",
            "",
            "## ProjectChallengeAgent Output",
            "",
            f"- basic_questions_count: {len(report.project_challenge_report.basic_questions)}",
            f"- technical_deep_dive_questions_count: {len(report.project_challenge_report.technical_deep_dive_questions)}",
            f"- architecture_questions_count: {len(report.project_challenge_report.architecture_questions)}",
            f"- grounded_questions_count: {len(report.project_challenge_report.grounded_questions)}",
            "",
            "## Final Report Summary",
            "",
            f"- overall_score: {report.match_report.overall_score}",
            f"- analysis_quality: {report.analysis_quality.overall_quality_label}",
            f"- project_count: {len(report.resume_profile.projects)}",
            f"- work_experience_count: {len(report.resume_profile.work_experiences)}",
            f"- rewrite_suggestions_count: {len(report.optimization_result.rewrite_suggestions)}",
            f"- grounded_questions_count: {len(report.project_challenge_report.grounded_questions)}",
            "",
            "## Output Quality Notes",
            "",
            bullet_list(quality_notes),
            "",
            "## Final Markdown Report",
            "",
            report.markdown_report.strip(),
            "",
        ]
    )


def build_comparison_summary(evaluations: list[ModeEvaluation]) -> str:
    by_mode = {evaluation.mode: evaluation for evaluation in evaluations}
    all_llm_or_first = by_mode.get("ollama-all-llm") or evaluations[0]
    input_tokens = all_llm_or_first.estimated_input_tokens
    output_tokens = all_llm_or_first.estimated_output_tokens
    example_cost = estimate_example_cost(input_tokens, output_tokens)

    return "\n".join(
        [
            "# Ollama Workflow Evaluation Comparison",
            "",
            "## Mode Comparison Table",
            "",
            build_mode_comparison_table(evaluations),
            "",
            "## JDAnalysis Comparison",
            "",
            compare_agent_modes(
                evaluations,
                "JDAnalysisAgent",
                ["mock", "ollama-jd-only", "ollama-all-llm"],
            ),
            "",
            "## ResumeOptimize Comparison",
            "",
            compare_agent_modes(
                evaluations,
                "ResumeOptimizeAgent",
                ["mock", "ollama-resume-optimize-only", "ollama-all-llm"],
            ),
            "",
            "## ProjectChallenge Comparison",
            "",
            compare_agent_modes(
                evaluations,
                "ProjectInterviewAgent",
                ["mock", "ollama-project-challenge-only", "ollama-all-llm"],
            ),
            "",
            "## Cost Estimation",
            "",
            f"- input_tokens_per_run = {input_tokens}",
            f"- output_tokens_per_run = {output_tokens}",
            f"- total_tokens_per_run = {input_tokens + output_tokens}",
            "",
            "Cost formula:",
            "",
            "```text",
            "input_cost = input_tokens / 1_000_000 * input_price_per_1m",
            "output_cost = output_tokens / 1_000_000 * output_price_per_1m",
            "total_cost = input_cost + output_cost",
            "```",
            "",
            (
                "Example only: If input is $0.15 / 1M tokens and output is $0.60 / 1M tokens, "
                f"one run costs approximately ${example_cost:.6f}. This is an illustrative formula, not a current price claim."
            ),
            "",
            "## Recommendation",
            "",
            build_recommendation(evaluations),
            "",
        ]
    )


def build_summary_doc(evaluations: list[ModeEvaluation]) -> str:
    modes = ", ".join(evaluation.mode for evaluation in evaluations)
    return "\n".join(
        [
            "# Ollama LLM Workflow Evaluation",
            "",
            "## Purpose",
            "",
            (
                "This experiment compares the deterministic JobAgent workflow with selected local "
                "Ollama-backed LLM modes. It is an evaluation harness only; it does not change "
                "agent prompts, schemas, storage, workflow core, or product behavior."
            ),
            "",
            "## Run Commands",
            "",
            "Local Ollama example:",
            "",
            "```bash",
            "set JOBAGENT_LLM_BASE_URL=http://127.0.0.1:11434/v1",
            "set JOBAGENT_LLM_API_KEY=ollama",
            "set JOBAGENT_LLM_MODEL=qwen2.5:0.5b",
            "set JOBAGENT_LLM_TEMPERATURE=0",
            "set JOBAGENT_LLM_TIMEOUT=120",
            "",
            r".venv\Scripts\python.exe scripts\run_ollama_workflow_evaluation.py --mode all",
            "```",
            "",
            "Offline mock-only run:",
            "",
            "```bash",
            r".venv\Scripts\python.exe scripts\run_ollama_workflow_evaluation.py --mode mock",
            "```",
            "",
            "## Environment Variables",
            "",
            "- JOBAGENT_LLM_BASE_URL: OpenAI-compatible endpoint, for example `http://127.0.0.1:11434/v1`.",
            "- JOBAGENT_LLM_API_KEY: Any non-empty key accepted by the local server, for example `ollama`.",
            "- JOBAGENT_LLM_MODEL: Model name served by Ollama; the script does not hard-code this.",
            "- JOBAGENT_LLM_TEMPERATURE: Optional, defaults through LLMConfig when omitted.",
            "- JOBAGENT_LLM_TIMEOUT: Optional timeout in seconds.",
            "",
            "If an LLM mode is requested without the required variables, the script prints:",
            "",
            "```text",
            "LLM is not configured. Set JOBAGENT_LLM_BASE_URL, JOBAGENT_LLM_API_KEY, JOBAGENT_LLM_MODEL.",
            "```",
            "",
            "## Output Files",
            "",
            f"- Output directory: `{OUTPUT_DIR.as_posix()}`",
            "- Per-mode reports: `mock_report.md`, `ollama_jd_only_report.md`, `ollama_resume_optimize_only_report.md`, `ollama_project_challenge_only_report.md`, `ollama_all_llm_report.md` when those modes are run.",
            "- Comparison summary: `comparison_summary.md`.",
            f"- This summary: `{SUMMARY_DOC_PATH.as_posix()}`.",
            "",
            "## How To Read The Results",
            "",
            "- mode=mock means the deterministic fallback path ran intentionally.",
            "- mode=llm means that agent returned a schema-valid LLM result.",
            "- mode=fallback means the LLM path was requested but failed and the agent used the deterministic fallback.",
            "- fallback_reason usually identifies validation, request, parsing, or service failures.",
            "- Token estimates use `max(1, round(len(text) / 4))` and are conservative approximations, not billing records.",
            "- Actual usage fields are included only when the OpenAI-compatible response contains usage metadata.",
            "",
            "## Experiment Limits",
            "",
            "- Prompt text is not changed in this experiment.",
            "- Small local models may fail JSON schema requirements even when the workflow remains stable through fallback.",
            "- Token estimates approximate the prompt reconstruction inside each agent; they are useful for comparison, not exact accounting.",
            "- Running only `--mode mock` validates the harness but does not evaluate Ollama model quality.",
            "",
            "## Latest Local Run",
            "",
            f"- generated_modes: {modes}",
            f"- generated_at: {evaluations[0].generated_at}",
            "",
        ]
    )


def build_steps_table(steps: list[dict[str, Any]]) -> str:
    rows = [
        "| step | agent_name | mode | fallback_reason | quality_warnings | duration_ms | summary |",
        "| --- | --- | --- | --- | --- | ---: | --- |",
    ]
    for index, step in enumerate(steps, start=1):
        rows.append(
            "| {step} | {agent} | {mode} | {fallback} | {quality_warnings} | {duration:.3f} | {summary} |".format(
                step=index,
                agent=escape_table_cell(step.get("name", "")),
                mode=escape_table_cell(step.get("mode", "")),
                fallback=escape_table_cell(step.get("fallback_reason") or ""),
                quality_warnings=escape_table_cell(join_list(step.get("quality_warnings") or [])),
                duration=float(step.get("duration_ms") or 0.0),
                summary=escape_table_cell(step.get("summary", "")),
            )
        )
    return "\n".join(rows)


def build_token_table(rows: list[dict[str, Any]]) -> str:
    table = [
        "| agent | estimated_input_tokens | estimated_output_tokens | estimated_total_tokens | mode | fallback_reason | actual_prompt_tokens | actual_completion_tokens | actual_total_tokens |",
        "| --- | ---: | ---: | ---: | --- | --- | ---: | ---: | ---: |",
    ]
    for row in rows:
        table.append(
            "| {agent} | {input} | {output} | {total} | {mode} | {fallback} | {actual_prompt} | {actual_completion} | {actual_total} |".format(
                agent=escape_table_cell(row["agent"]),
                input=row["estimated_input_tokens"],
                output=row["estimated_output_tokens"],
                total=row["estimated_total_tokens"],
                mode=escape_table_cell(row["mode"]),
                fallback=escape_table_cell(row["fallback_reason"]),
                actual_prompt=format_optional_int(row["actual_prompt_tokens"]),
                actual_completion=format_optional_int(row["actual_completion_tokens"]),
                actual_total=format_optional_int(row["actual_total_tokens"]),
            )
        )
    return "\n".join(table)


def build_mode_comparison_table(evaluations: list[ModeEvaluation]) -> str:
    rows = [
        "| mode | fallback_count | overall_score | analysis_quality | estimated_input_tokens | estimated_output_tokens | estimated_total_tokens | notes |",
        "| --- | ---: | ---: | --- | ---: | ---: | ---: | --- |",
    ]
    for evaluation in evaluations:
        report = evaluation.final_report
        rows.append(
            "| {mode} | {fallback_count} | {score} | {quality} | {input} | {output} | {total} | {notes} |".format(
                mode=evaluation.mode,
                fallback_count=evaluation.fallback_count,
                score=report.match_report.overall_score,
                quality=report.analysis_quality.overall_quality_label,
                input=evaluation.estimated_input_tokens,
                output=evaluation.estimated_output_tokens,
                total=evaluation.estimated_total_tokens,
                notes=escape_table_cell(summarize_mode(evaluation)),
            )
        )
    return "\n".join(rows)


def compare_agent_modes(evaluations: list[ModeEvaluation], agent_name: str, preferred_modes: list[str]) -> str:
    by_mode = {evaluation.mode: evaluation for evaluation in evaluations}
    lines: list[str] = []
    for mode in preferred_modes:
        evaluation = by_mode.get(mode)
        if evaluation is None:
            lines.append(f"- {mode}: not run in this invocation.")
            continue
        step = find_step(evaluation.workflow_result, agent_name)
        token_row = next(row for row in evaluation.token_rows if row["agent"] == agent_name)
        lines.append(
            "- {mode}: step_mode={step_mode}, fallback_reason={fallback}, quality_warnings={quality_warnings}, estimated_total_tokens={tokens}. {note}".format(
                mode=mode,
                step_mode=step.get("mode", ""),
                fallback=step.get("fallback_reason") or "none",
                quality_warnings=join_list(step.get("quality_warnings") or []),
                tokens=token_row["estimated_total_tokens"],
                note=agent_specific_note(evaluation, agent_name),
            )
        )
    return "\n".join(lines)


def build_quality_notes(evaluation: ModeEvaluation) -> list[str]:
    report = evaluation.final_report
    jd = report.job_analysis
    optimization = report.optimization_result
    challenges = report.project_challenge_report
    missing_requirements = [
        item.requirement
        for item in report.match_report.requirement_matches
        if item.match_level == "missing"
    ]
    unsupported_rewrites = [
        item
        for item in optimization.rewrite_suggestions
        if not item.evidence_source and item.match_level != "missing"
    ]
    notes = [
        f"Workflow ran with {evaluation.fallback_count} fallback step(s).",
        f"JDAnalysisAgent extracted {len(jd.required_skills)} required skills and {len(jd.keywords)} keywords.",
        f"JDAnalysisAgent quality warnings: {join_list(find_step(evaluation.workflow_result, 'JDAnalysisAgent').get('quality_warnings') or [])}.",
        "Check required_skills for preferred-skill leakage; the report lists preferred_skills separately for manual review.",
        f"ResumeOptimizeAgent produced {len(optimization.rewrite_suggestions)} rewrite suggestions and {len(optimization.jd_targeted_bullets)} JD-targeted bullets.",
        f"{len(unsupported_rewrites)} non-missing rewrite suggestions lack explicit evidence sources.",
        f"ProjectChallengeAgent produced {len(challenges.grounded_questions)} grounded questions.",
        f"Missing requirements surfaced by MatchAgent: {join_list(missing_requirements)}.",
        f"Estimated total tokens for the three LLM-capable agents: {evaluation.estimated_total_tokens}.",
    ]
    if report.analysis_quality.warnings:
        notes.append(f"Quality warnings: {join_list(report.analysis_quality.warnings)}.")
    if evaluation.mode == "mock":
        notes.append("This run is a deterministic baseline; token counts are estimates only and not actual LLM usage.")
    elif evaluation.fallback_count:
        notes.append("At least one requested LLM step fell back, so quality should be judged as fallback output for those agents.")
    else:
        notes.append("Requested LLM steps returned schema-valid outputs; compare specificity against the mock baseline.")
    return notes


def build_recommendation(evaluations: list[ModeEvaluation]) -> str:
    if all(evaluation.mode == "mock" for evaluation in evaluations):
        return "\n".join(
            [
                "- Ollama modes were not run in this invocation, so model suitability cannot be judged yet.",
                "- The harness is ready for local model testing; next run `--mode all` after configuring Ollama.",
                "- If a 0.5B model falls back often, first try JSON repair or a larger local model before changing agent prompts.",
            ]
        )

    lines = []
    by_mode = {evaluation.mode: evaluation for evaluation in evaluations}
    for mode, agent in [
        ("ollama-jd-only", "JDAnalysisAgent"),
        ("ollama-resume-optimize-only", "ResumeOptimizeAgent"),
        ("ollama-project-challenge-only", "ProjectInterviewAgent"),
    ]:
        evaluation = by_mode.get(mode) or by_mode.get("ollama-all-llm")
        if evaluation is None:
            lines.append(f"- {agent}: not enough data from this run.")
            continue
        step = find_step(evaluation.workflow_result, agent)
        if step.get("mode") == "llm":
            lines.append(f"- {agent}: schema-valid LLM output was produced; compare specificity and evidence before enabling by default.")
        else:
            lines.append(f"- {agent}: fallback occurred ({step.get('fallback_reason') or 'unknown'}); prefer JSON repair, stricter output validation, or a larger model.")
    lines.append("- For low-risk local use, a small model may be safest for classification or extraction tasks before free-form rewrite generation.")
    return "\n".join(lines)


def agent_specific_note(evaluation: ModeEvaluation, agent_name: str) -> str:
    report = evaluation.final_report
    if agent_name == "JDAnalysisAgent":
        return f"required_skills={len(report.job_analysis.required_skills)}, keywords={len(report.job_analysis.keywords)}."
    if agent_name == "ResumeOptimizeAgent":
        return (
            f"rewrite_suggestions={len(report.optimization_result.rewrite_suggestions)}, "
            f"jd_targeted_bullets={len(report.optimization_result.jd_targeted_bullets)}."
        )
    if agent_name == "ProjectInterviewAgent":
        return (
            f"grounded_questions={len(report.project_challenge_report.grounded_questions)}, "
            f"basic_questions={len(report.project_challenge_report.basic_questions)}."
        )
    return ""


def summarize_mode(evaluation: ModeEvaluation) -> str:
    llm_steps = [step for step in evaluation.workflow_result.state.steps if step.mode == "llm"]
    if evaluation.mode == "mock":
        return "deterministic baseline"
    if evaluation.fallback_count:
        return f"{evaluation.fallback_count} fallback step(s); inspect fallback_reason"
    return f"{len(llm_steps)} LLM step(s) completed"


def find_step(workflow_result: JobAnalysisWorkflowResult, agent_name: str) -> dict[str, Any]:
    for step in workflow_result.state.steps:
        if step.name == agent_name:
            return step.model_dump()
    return {
        "name": agent_name,
        "mode": "",
        "fallback_reason": "",
        "quality_warnings": [],
        "duration_ms": 0.0,
        "summary": "",
    }


def extract_usage(raw_response: dict[str, Any]) -> UsageRecord:
    usage = raw_response.get("usage")
    if not isinstance(usage, dict):
        return UsageRecord()
    return UsageRecord(
        prompt_tokens=normalize_optional_int(usage.get("prompt_tokens")),
        completion_tokens=normalize_optional_int(usage.get("completion_tokens")),
        total_tokens=normalize_optional_int(usage.get("total_tokens")),
    )


def extract_message_content(response: dict[str, Any]) -> str:
    try:
        content = response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMServiceError("LLM response does not contain message content") from exc
    if not isinstance(content, str) or not content.strip():
        raise LLMServiceError("LLM message content is empty")
    return content


def estimate_tokens(text: str) -> int:
    return max(1, round(len(text) / 4))


def estimate_example_cost(input_tokens: int, output_tokens: int) -> float:
    return input_tokens / 1_000_000 * 0.15 + output_tokens / 1_000_000 * 0.60


def has_required_llm_env() -> bool:
    return all(os.getenv(name) for name in LLM_REQUIRED_ENV)


def display_env_or_unconfigured(name: str) -> str:
    return os.getenv(name) or "not configured"


def mode_to_file_stem(mode: str) -> str:
    return mode.replace("-", "_")


def normalize_optional_int(value: object) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def format_optional_int(value: object) -> str:
    return "" if value is None else str(value)


def bullet_list(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items) if items else "- None"


def join_list(items: list[str]) -> str:
    return ", ".join(items) if items else "None"


def escape_table_cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ").strip()


if __name__ == "__main__":
    raise SystemExit(main())
