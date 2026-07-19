from __future__ import annotations

import hashlib
import json
from typing import Any


def stable_digest(payload: object) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def finalize_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    stable = dict(payload)
    stable.pop("manifest_digest", None)
    return {**stable, "manifest_digest": stable_digest(stable)}


def render_markdown(manifest: dict[str, Any]) -> str:
    lines = [
        "# Search Quality Baseline",
        "",
        f"Baseline: `{manifest['baseline_id']}`",
        f"Runtime profile: `{manifest['runtime_profile']}`",
        f"Fixture: `{manifest['fixture_version']}`",
        f"Cases: {manifest['case_count']}",
        f"Digest: `{manifest['manifest_digest']}`",
        "",
        "| Case | Pool recall | Eligible recall | Precision@5 | nDCG@5 | Violations | Duplicates |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for case in manifest["cases"]:
        metrics = case["metrics"]
        lines.append(
            "| "
            + " | ".join(
                [
                    case["case_id"],
                    _metric(metrics["pool_recall"]),
                    _metric(metrics["eligible_pool_recall"]),
                    _metric(metrics["precision_at_5"]),
                    _metric(metrics["ndcg_at_5"]),
                    str(metrics["constraint_violation_at_5"]["numerator"]),
                    str(metrics["duplicate_at_5"]["numerator"]),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "This baseline is deterministic and offline. Timing, absolute paths, URLs, and generated timestamps are excluded from equality checks.",
            "",
        ]
    )
    return "\n".join(lines)


def _metric(value: dict[str, float]) -> str:
    return f"{value['value']:.3f} ({value['numerator']:.0f}/{value['denominator']:.0f})"
