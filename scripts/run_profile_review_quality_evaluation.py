from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.llm_provider import normalize_llm_provider, resolve_llm_provider
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
    llm_provider: str = "mock",
    real_llm: bool = False,
) -> ProfileReviewQualityRunOutputs:
    outputs = ProfileReviewQualityRunOutputs()
    normalized_provider = normalize_llm_provider(llm_provider)
    provider_resolution = resolve_llm_provider(normalized_provider)

    if real_llm and normalized_provider != "mock":
        llm_service = provider_resolution.service
    else:
        llm_service = FakeProfileReviewLLMService()

    if mode in {"deterministic", "both"}:
        outputs.deterministic = run_profile_review_quality_suite(
            use_llm_enrichment=False,
            simulate_user_decisions=True,
        )
    if mode in {"llm", "both"}:
        outputs.llm_enriched = run_profile_review_quality_suite(
            use_llm_enrichment=True,
            simulate_user_decisions=True,
            llm_service=llm_service,  # type: ignore[arg-type]
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
        "--llm-provider",
        choices=["mock", "ollama", "deepseek"],
        default="mock",
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
        llm_provider=args.llm_provider,
        real_llm=args.real_llm,
    )
    summary = {
        "mode": args.mode,
        "llm_provider": args.llm_provider,
        "real_llm": args.real_llm,
        "deterministic_cases": (
            outputs.deterministic.total_cases if outputs.deterministic else 0
        ),
        "llm_cases": outputs.llm_enriched.total_cases if outputs.llm_enriched else 0,
        "comparison_count": len(outputs.comparisons),
    }
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
