from __future__ import annotations

import argparse
import asyncio
import json
import os
import sqlite3
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config.env_loader import load_local_env
from app.repositories.resume_profile_repository import resume_profile_repository
from app.repositories.saved_job_repository import saved_job_repository
from experiments.preparation_eval.agent import PreparationEvaluationAgent
from experiments.preparation_eval.model import OpenAICompatibleEvaluationModel
from experiments.preparation_eval.schemas import PreparationEvaluationReport


def main() -> int:
    args = parse_args()
    load_local_env(args.env_file)
    source_db = Path(os.getenv("JOBAGENT_DB_PATH", "data/jobagent.sqlite3")).resolve()
    if args.list_context:
        print_context(source_db)
        return 0
    if not args.profile_id or not args.saved_job_id:
        raise SystemExit("--profile-id and --saved-job-id are required unless --list-context is used")

    user_id = resolve_shared_owner(source_db, args.profile_id, args.saved_job_id)
    model = OpenAICompatibleEvaluationModel()
    with tempfile.TemporaryDirectory(prefix="jobagent-preparation-eval-") as temp_dir:
        shadow_db = Path(temp_dir) / "evaluation.sqlite3"
        backup_database(source_db, shadow_db)
        with evaluation_database(shadow_db):
            profile = resume_profile_repository.get(
                user_id=user_id,
                resume_profile_id=args.profile_id,
            )
            job = saved_job_repository.get(
                user_id=user_id,
                saved_job_id=args.saved_job_id,
            )
            if profile is None or job is None:
                raise RuntimeError("Profile or saved job disappeared from the evaluation snapshot")
            profile_memory = profile.model_dump(
                mode="json",
                exclude={"raw_resume_text"} if not args.include_raw_resume else set(),
            )
            job_context = job.model_dump(mode="json", exclude={"latest_analysis"})
            agent = PreparationEvaluationAgent(
                model,
                preparation_provider=args.preparation_provider,
                persona_archetype=args.persona_archetype,
                pause_after=args.pause_after,
                finish_session=not args.stop_without_summary,
            )
            report = asyncio.run(agent.run(
                user_id=user_id,
                profile_id=args.profile_id,
                saved_job_id=args.saved_job_id,
                profile_memory=profile_memory,
                job_context=job_context,
            ))

    json_path, markdown_path = write_report(report, Path(args.output_dir))
    print(f"Wrote JSON report: {json_path}")
    print(f"Wrote Markdown report: {markdown_path}")
    return 0 if report.passed else 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a persona-centered agent evaluation against an existing profile and saved job."
    )
    parser.add_argument("--profile-id")
    parser.add_argument("--saved-job-id")
    parser.add_argument("--list-context", action="store_true")
    parser.add_argument("--persona-archetype", default="calibrated but imperfect")
    parser.add_argument("--preparation-provider", choices=["mock", "ollama", "deepseek"], default="deepseek")
    parser.add_argument("--pause-after", type=int, default=2)
    parser.add_argument("--stop-without-summary", action="store_true")
    parser.add_argument("--include-raw-resume", action="store_true")
    parser.add_argument("--env-file", default=".env.deepseek.local")
    parser.add_argument(
        "--output-dir",
        default=str(PROJECT_ROOT / "experiments" / "output"),
    )
    return parser.parse_args()


def resolve_shared_owner(database_path: Path, profile_id: str, saved_job_id: str) -> str:
    if not database_path.exists():
        raise FileNotFoundError(f"JobAgent database not found: {database_path}")
    with sqlite3.connect(database_path) as connection:
        profile = connection.execute(
            "SELECT user_id FROM resume_profiles WHERE resume_profile_id = ?",
            (profile_id,),
        ).fetchone()
        job = connection.execute(
            "SELECT user_id FROM saved_jobs WHERE saved_job_id = ?",
            (saved_job_id,),
        ).fetchone()
    if profile is None or job is None:
        raise ValueError("Profile or saved job ID was not found")
    if profile[0] != job[0]:
        raise ValueError("Profile and saved job must belong to the same user")
    return str(profile[0])


def backup_database(source: Path, destination: Path) -> None:
    with sqlite3.connect(source) as source_connection, sqlite3.connect(destination) as destination_connection:
        source_connection.backup(destination_connection)


@contextmanager
def evaluation_database(path: Path):
    previous_db = os.environ.get("JOBAGENT_DB_PATH")
    previous_graph = os.environ.get("JOBAGENT_LANGGRAPH_DB_PATH")
    os.environ["JOBAGENT_DB_PATH"] = str(path)
    os.environ["JOBAGENT_LANGGRAPH_DB_PATH"] = str(path.with_name("evaluation.langgraph.sqlite3"))
    try:
        yield
    finally:
        _restore_env("JOBAGENT_DB_PATH", previous_db)
        _restore_env("JOBAGENT_LANGGRAPH_DB_PATH", previous_graph)


def print_context(database_path: Path) -> None:
    if not database_path.exists():
        raise FileNotFoundError(f"JobAgent database not found: {database_path}")
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        profiles = connection.execute(
            "SELECT resume_profile_id, user_id, name, summary FROM resume_profiles WHERE archived_at IS NULL ORDER BY updated_at DESC"
        ).fetchall()
        jobs = connection.execute(
            "SELECT saved_job_id, user_id, title, company FROM saved_jobs WHERE archived_at IS NULL ORDER BY updated_at DESC"
        ).fetchall()
    print("Profiles:")
    for row in profiles:
        print(f"  {row['resume_profile_id']}  user={row['user_id']}  {row['name']}  {row['summary'][:80]}")
    print("Saved jobs:")
    for row in jobs:
        print(f"  {row['saved_job_id']}  user={row['user_id']}  {row['title']}  {row['company'] or ''}")


def write_report(report: PreparationEvaluationReport, output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = report.generated_at.strftime("%Y%m%dT%H%M%SZ")
    stem = f"{timestamp}_{report.evaluation_id}_preparation_persona_eval"
    json_path = output_dir / f"{stem}.json"
    markdown_path = output_dir / f"{stem}.md"
    json_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    markdown_path.write_text(render_markdown(report), encoding="utf-8")
    return json_path, markdown_path


def render_markdown(report: PreparationEvaluationReport) -> str:
    assessment = report.self_assessment
    lines = [
        "# Preparation Persona Evaluation",
        "",
        f"- Evaluation: `{report.evaluation_id}`",
        f"- Profile: `{report.profile_id}`",
        f"- Saved job: `{report.saved_job_id}`",
        f"- Evaluation model: `{report.evaluation_model}`",
        f"- Preparation provider: `{report.preparation_provider}`",
        f"- Result: `{'PASS' if report.passed else 'FAIL'}`",
        "",
        "## Candidate Persona",
        "",
        report.persona_memory.internal_summary,
        "",
        "## Self-Assessment",
        "",
        f"- Felt understood: {assessment.felt_understood}/5",
        f"- Truthfulness: {assessment.truthfulness}/5",
        f"- Learning value: {assessment.learning_value}/5",
        f"- Interview value: {assessment.interview_value}/5",
        f"- Actionability: {assessment.actionability}/5",
        "",
        assessment.candidate_reflection,
        "",
        "## Deterministic Checks",
        "",
    ]
    lines.extend(
        f"- {'PASS' if check.passed else 'FAIL'} — **{check.name}**: {check.detail}"
        for check in report.rule_checks
    )
    lines.extend(["", "## Episodic Memory", ""])
    lines.extend(
        f"- **{turn.skill}** → `{turn.experience_level}`: {turn.private_reason}"
        for turn in report.episodic_memory
    )
    return "\n".join(lines) + "\n"


def _restore_env(name: str, previous: str | None) -> None:
    if previous is None:
        os.environ.pop(name, None)
    else:
        os.environ[name] = previous


if __name__ == "__main__":
    raise SystemExit(main())
