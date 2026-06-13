from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.profile_review_quality_evaluation import (
    FakeProfileReviewLLMService,
    ProfileReviewQualityRunOutputs,
    compare_profile_review_quality_suites,
    run_profile_review_quality_suite,
    write_profile_review_quality_outputs,
)

DEFAULT_OUTPUT_DIR = Path("docs/demo_outputs/profile_review_quality_eval")


def run(
    *,
    mode: str = "both",
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    use_fake_llm: bool = True,
    real_llm: bool = False,
) -> ProfileReviewQualityRunOutputs:
    outputs = ProfileReviewQualityRunOutputs()
    llm_service = None if real_llm else FakeProfileReviewLLMService()

    if mode in {"deterministic", "both"}:
        outputs.deterministic = run_profile_review_quality_suite(
            use_llm_enrichment=False,
            simulate_user_decisions=True,
        )
    if mode in {"llm", "both"}:
        outputs.llm_enriched = run_profile_review_quality_suite(
            use_llm_enrichment=True,
            simulate_user_decisions=True,
            llm_service=None if real_llm else llm_service,  # type: ignore[arg-type]
        )
    if outputs.deterministic and outputs.llm_enriched:
        outputs.comparisons = compare_profile_review_quality_suites(
            outputs.deterministic,
            outputs.llm_enriched,
        )

    write_profile_review_quality_outputs(outputs, output_dir)
    return outputs


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        choices=["deterministic", "llm", "both"],
        default="both",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
    )
    parser.add_argument(
        "--use-fake-llm",
        action="store_true",
        default=True,
    )
    parser.add_argument(
        "--real-llm",
        action="store_true",
        help="Use configured real LLM service instead of the default fake LLM.",
    )
    args = parser.parse_args()

    outputs = run(
        mode=args.mode,
        output_dir=args.output_dir,
        use_fake_llm=not args.real_llm,
        real_llm=args.real_llm,
    )
    summary = {
        "mode": args.mode,
        "deterministic_cases": (
            outputs.deterministic.total_cases if outputs.deterministic else 0
        ),
        "llm_cases": outputs.llm_enriched.total_cases if outputs.llm_enriched else 0,
        "comparison_count": len(outputs.comparisons),
    }
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
