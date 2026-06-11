from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.resume_profile_evaluation import (
    ResumeProfileEvaluationSuiteResult,
    evaluate_profile_review_suite,
)
from tests.fixtures.resumes.profile_cases import PROFILE_EVALUATION_CASES


DEFAULT_OUTPUT_DIR = Path("docs/demo_outputs/resume_profile_parser_eval")


def write_evaluation_outputs(
    result: ResumeProfileEvaluationSuiteResult,
    output_dir: Path,
) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "summary.json"
    md_path = output_dir / "summary.md"

    json_path.write_text(
        json.dumps(result.model_dump(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    md_path.write_text(_render_markdown_summary(result), encoding="utf-8")
    return json_path, md_path


def run(output_dir: Path = DEFAULT_OUTPUT_DIR) -> ResumeProfileEvaluationSuiteResult:
    result = evaluate_profile_review_suite(PROFILE_EVALUATION_CASES)
    write_evaluation_outputs(result, output_dir)
    return result


def main() -> None:
    result = run()
    print(
        "Resume profile parser evaluation complete: "
        f"{result.total_cases} cases, "
        f"{result.strong_cases} strong, "
        f"{result.medium_cases} medium, "
        f"{result.limited_cases} limited, "
        f"{result.weak_cases} weak"
    )


def _render_markdown_summary(result: ResumeProfileEvaluationSuiteResult) -> str:
    lines = [
        "# Resume Profile Parser Evaluation Summary",
        "",
        "## Overall",
        f"- total_cases: {result.total_cases}",
        f"- strong_cases: {result.strong_cases}",
        f"- medium_cases: {result.medium_cases}",
        f"- limited_cases: {result.limited_cases}",
        f"- weak_cases: {result.weak_cases}",
        "",
        "## Case Table",
        "| case_id | title | confidence_label | evaluation_label | passed | failed | project_count | work_experience_count | skills_hit |",
        "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- |",
    ]

    for case in result.cases:
        lines.append(
            "| "
            + " | ".join(
                [
                    case.case_id,
                    case.title,
                    case.confidence_label,
                    case.overall_label,
                    str(len(case.passed_checks)),
                    str(len(case.failed_checks)),
                    str(case.project_count),
                    str(case.work_experience_count),
                    ", ".join(case.skill_hits) or "-",
                ]
            )
            + " |"
        )

    lines.extend(["", "## Known Limitations"])
    if result.known_limitations:
        lines.extend(f"- {item}" for item in result.known_limitations)
    else:
        lines.append("- None")

    lines.extend(["", "## Detailed Case Results"])
    for case in result.cases:
        lines.extend(
            [
                "",
                f"### {case.case_id}: {case.title}",
                f"- failed_checks: {_format_list(case.failed_checks)}",
                f"- warnings: {_format_list(case.warnings)}",
                f"- missing_info_questions: {_format_list(case.missing_info_questions)}",
                f"- skill_hits: {_format_list(case.skill_hits)}",
                f"- missing_expected_skills: {_format_list(case.missing_expected_skills)}",
            ]
        )

    return "\n".join(lines) + "\n"


def _format_list(items: list[str]) -> str:
    return ", ".join(items) if items else "-"


if __name__ == "__main__":
    main()
