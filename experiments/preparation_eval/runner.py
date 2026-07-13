from __future__ import annotations

import argparse
import asyncio
import json
import os
import sqlite3
import sys
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
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
    if not args.saved_job_id:
        raise SystemExit("--saved-job-id is required unless --list-context is used")

    context = resolve_evaluation_context(source_db, args.saved_job_id, args.profile_id)
    model = OpenAICompatibleEvaluationModel()
    with tempfile.TemporaryDirectory(prefix="jobagent-preparation-eval-") as temp_dir:
        shadow_db = Path(temp_dir) / "evaluation.sqlite3"
        backup_database(source_db, shadow_db)
        with evaluation_database(shadow_db):
            profile = resume_profile_repository.get(
                user_id=context.user_id,
                resume_profile_id=context.profile_id,
            )
            job = saved_job_repository.get(
                user_id=context.user_id,
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
                user_id=context.user_id,
                profile_id=context.profile_id,
                saved_job_id=args.saved_job_id,
                saved_job_origin_id=context.origin_id,
                association_method=context.association_method,
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


@dataclass(frozen=True)
class EvaluationContext:
    user_id: str
    profile_id: str
    origin_id: str | None
    association_method: str


def resolve_evaluation_context(
    database_path: Path,
    saved_job_id: str,
    profile_id: str | None = None,
) -> EvaluationContext:
    if not database_path.exists():
        raise FileNotFoundError(f"JobAgent database not found: {database_path}")
    with sqlite3.connect(database_path) as connection:
        job = connection.execute(
            "SELECT user_id FROM saved_jobs WHERE saved_job_id = ?",
            (saved_job_id,),
        ).fetchone()
        if job is None:
            raise ValueError("Saved job ID was not found")
        user_id = str(job[0])
        has_origins = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'saved_job_origins'"
        ).fetchone() is not None
        association = None
        if has_origins:
            association = connection.execute(
                """
                SELECT o.saved_job_origin_id, o.resume_profile_id
                FROM saved_job_origins o
                JOIN resume_profiles p ON p.resume_profile_id = o.resume_profile_id
                WHERE o.user_id = ? AND o.saved_job_id = ?
                  AND p.archived_at IS NULL
                  AND (? IS NULL OR o.resume_profile_id = ?)
                ORDER BY o.created_at DESC
                LIMIT 1
                """,
                (user_id, saved_job_id, profile_id, profile_id),
            ).fetchone()
        if association is not None:
            return EvaluationContext(
                user_id=user_id,
                profile_id=str(association[1]),
                origin_id=str(association[0]),
                association_method="saved_job_origin",
            )
        legacy = connection.execute(
            """
            SELECT a.resume_profile_id
            FROM saved_job_analyses a
            JOIN resume_profiles p ON p.resume_profile_id = a.resume_profile_id
            WHERE a.user_id = ? AND a.saved_job_id = ?
              AND p.archived_at IS NULL
              AND (? IS NULL OR a.resume_profile_id = ?)
            ORDER BY a.created_at DESC
            LIMIT 1
            """,
            (user_id, saved_job_id, profile_id, profile_id),
        ).fetchone()
        if legacy is not None:
            return EvaluationContext(
                user_id=user_id,
                profile_id=str(legacy[0]),
                origin_id=None,
                association_method="legacy_saved_job_analysis",
            )
    requested = f" for profile {profile_id}" if profile_id else ""
    raise ValueError(f"Saved job has no usable profile association{requested}")


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
        f"- Association: `{report.association_method}`",
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
